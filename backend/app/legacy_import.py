"""Migración de datos desde la aplicación PySide6 (tablas legacy) al modelo 2.0.

    python -m app.legacy_import --legacy-url mysql+pymysql://lector:***@host/inventario_software --dry-run
    python -m app.legacy_import --legacy-url ...            # aplica

- Solo LEE las tablas legacy: nunca las modifica. La app PySide6 puede seguir funcionando.
- Idempotente: usa los ids legacy (departments.legacy_id, devices.legacy_equipo_id) y las
  claves únicas del modelo nuevo; repetirla no duplica nada.
- --dry-run ejecuta todo en una transacción que se deshace y muestra el informe.
- Decisiones de mapeo (ver docs/migration.md):
  * El "departamento" legacy `servidores` es una categoría de hardware: sus equipos pasan a
    tipo Servidor sin departamento (IT debe asignarlo).
  * El software legacy procede de Panda: se carga como instalaciones de la fuente `panda`.
  * Cada periodo importado (YYYY-MM) genera un inventario mensual con estado `legacy`.
  * `software_autorizado` activo -> políticas `authorized` (equipo > departamento > global).
  * El catálogo ENS por departamento (`software`) aporta clasificación y observaciones al
    producto, pero NO se interpreta como autorización.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.db import session_factory, utcnow
from app.models import (
    Department,
    Device,
    InventoryRun,
    InventorySnapshot,
    InventorySnapshotItem,
    SoftwareInstallation,
    SoftwarePolicy,
    SoftwareProduct,
)
from app.services import audit
from app.services.bootstrap import ensure_reference_data
from app.services.devices import device_type_id, reassign
from app.services.normalization import hostname_key, name_key
from app.services.runs import source_by_code
from app.services.software import ProductResolver

TYPE_MAP = {"portatil": "laptop", "portátil": "laptop", "laptop": "laptop", "sobremesa": "desktop",
            "desktop": "desktop", "torre": "desktop", "servidor": "server", "server": "server", "movil": "mobile",
            "móvil": "mobile", "tablet": "mobile", "telefono": "mobile", "teléfono": "mobile"}
_SIZE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(TB|GB|MB)", re.I)


def _bytes(raw: str | None, binary: bool) -> int | None:
    m = _SIZE.search(raw or "")
    if not m:
        return None
    num = float(m.group(1).replace(",", "."))
    base = 1024 if binary else 1000
    return int(num * base ** {"MB": 2, "GB": 3, "TB": 4}[m.group(2).upper()])


def _dt(value) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


class LegacyImporter:
    def __init__(self, legacy: Connection, db: Session, actor: str = "migración legacy"):
        self.legacy, self.db, self.actor = legacy, db, actor
        self.tables = set(inspect(legacy).get_table_names())
        self.report: Counter = Counter()
        self.notes: list[str] = []
        self.dept_map: dict[int, int | None] = {}
        self.device_map: dict[int, Device] = {}
        self.now = utcnow()

    def rows(self, sql: str, **params) -> list[dict]:
        return [dict(r) for r in self.legacy.execute(text(sql), params).mappings()]

    def run(self) -> dict:
        ensure_reference_data(self.db)
        self.departments()
        self.devices()
        self.software()
        self.authorizations()
        self.ens_catalog()
        audit.record(self.db, self.actor, "migration.legacy", "migration", None, "Importación desde el sistema anterior",
                     after=dict(self.report))
        return {"counts": dict(sorted(self.report.items())), "notes": self.notes}

    # ------------------------------------------------------------------ departamentos
    def departments(self) -> None:
        for row in self.rows("SELECT id, codigo, nombre FROM departamentos ORDER BY id"):
            self.report["legacy.departamentos"] += 1
            if row["codigo"] == "servidores":
                self.dept_map[row["id"]] = None
                self.notes.append("'Servidores' no se migra como departamento: sus equipos pasan a tipo Servidor.")
                continue
            dept = self.db.execute(select(Department).where(
                (Department.legacy_id == row["id"]) | (Department.code == row["codigo"]))).scalars().first()
            if dept is None:
                dept = Department(code=row["codigo"], name=row["nombre"], legacy_id=row["id"], active=True)
                self.db.add(dept)
                self.db.flush()
                self.report["new.departments"] += 1
            elif dept.legacy_id is None:
                dept.legacy_id = row["id"]
            self.dept_map[row["id"]] = dept.id

    # ------------------------------------------------------------------ equipos
    def devices(self) -> None:
        cols = {c["name"] for c in inspect(self.legacy).get_columns("equipos")}

        def col(row, name):
            return row.get(name) if name in cols else None

        for row in self.rows("SELECT * FROM equipos ORDER BY id"):
            self.report["legacy.equipos"] += 1
            device = self.db.execute(select(Device).where(Device.legacy_equipo_id == row["id"])).scalar_one_or_none()
            if device is not None:
                self.device_map[row["id"]] = device
                self.report["skip.devices_already_migrated"] += 1
                continue
            raw_type = (col(row, "tipo_dispositivo") or "").strip().lower()
            dtype = TYPE_MAP.get(raw_type)
            dept_legacy = row.get("departamento_id")
            if col(row, "es_servidor") or (dept_legacy in self.dept_map and self.dept_map[dept_legacy] is None):
                dtype = "server"
            brand_model = col(row, "marca_modelo") or ""
            manufacturer, _, model = brand_model.partition("/")
            notes = [row.get("notas") or ""]
            if col(row, "responsable"):
                notes.append(f"Responsable (sistema anterior): {col(row, 'responsable')}")
            if col(row, "almacenamiento"):
                notes.append(f"Almacenamiento (sistema anterior): {col(row, 'almacenamiento')}")
            retired = not row.get("activo", True)
            device = Device(
                hostname=row["nombre"], hostname_key=hostname_key(row["nombre"]),
                serial_number=col(row, "num_serie") or None,
                manufacturer=(manufacturer.strip() or None) if model else None,
                model=(model.strip() or None) if model else (brand_model.strip() or None),
                os_name=col(row, "sistema_operativo"), processor=col(row, "procesador"),
                ram_bytes=_bytes(col(row, "ram"), binary=True),
                storage_total_bytes=_bytes(col(row, "almacenamiento"), binary=False),
                mac_ethernet=col(row, "mac_address"), location=col(row, "ubicacion"),
                cost=str(col(row, "coste")) if col(row, "coste") is not None else None,
                purchase_date=_dt(col(row, "fecha_adquisicion")),
                device_type_id=device_type_id(self.db, dtype),
                status="retired" if retired else "active",
                retired_at=_dt(row.get("fecha_baja")) or (self.now if retired else None),
                first_seen_at=_dt(row.get("fecha_alta")), legacy_equipo_id=row["id"],
                notes="\n".join(n for n in notes if n) or None,
                field_sources={"_origin": {"source": "legacy", "at": self.now.isoformat(timespec="seconds")}},
            )
            self.db.add(device)
            self.db.flush()
            reassign(self.db, device, department_id=self.dept_map.get(dept_legacy), user_id=None,
                     reason="Migración desde el sistema anterior", actor=self.actor, source="legacy",
                     at=_dt(row.get("fecha_alta")) or self.now)
            self.device_map[row["id"]] = device
            self.report["new.devices"] += 1
            if retired:
                self.report["new.devices_retired"] += 1
            if dtype == "server" and device.department_id is None:
                self.report["todo.servers_without_department"] += 1

    # ------------------------------------------------------------------ software
    def software(self) -> None:
        if "software_importaciones" not in self.tables:
            self.notes.append("No existe software_importaciones: no hay histórico de Panda que migrar.")
            return
        imports = self.rows("""SELECT id, equipo_id, periodo, fecha_importacion FROM software_importaciones
                               WHERE estado = 'confirmed' ORDER BY periodo, fecha_importacion, id""")
        if not imports:
            return
        panda = source_by_code(self.db, "panda")
        resolver = ProductResolver(self.db, self.now)
        by_period: dict[str, dict[int, dict]] = defaultdict(dict)
        for imp in imports:  # la última confirmada de cada equipo y periodo
            by_period[imp["periodo"]][imp["equipo_id"]] = imp
        periods = sorted(by_period)
        latest_by_device: dict[int, tuple[str, dict]] = {}
        for period in periods:
            for equipo_id, imp in by_period[period].items():
                latest_by_device[equipo_id] = (period, imp)

        for period in periods:
            flag = f"legacy:{period}"
            if self.db.execute(select(InventorySnapshot).where(InventorySnapshot.period == period,
                                                               InventorySnapshot.review_notes == flag)).first():
                self.report["skip.periods_already_migrated"] += 1
                continue
            snap = InventorySnapshot(period=period, version=self._next_version(period), status="legacy",
                                     is_complete=False, created_by=self.actor, review_notes=flag,
                                     coverage={"sources": {"panda": {"name": "Panda (sistema anterior)",
                                                                     "essential": False, "ok": True}},
                                               "complete": False, "legacy": True})
            self.db.add(snap)
            self.db.flush()
            seen = set()
            n_dev = 0
            for equipo_id, imp in by_period[period].items():
                device = self.device_map.get(equipo_id)
                if device is None:
                    self.report["warn.imports_without_device"] += 1
                    continue
                n_dev += 1
                self.db.add(InventorySnapshotItem(snapshot_id=snap.id, device_id=device.id,
                                                  department_id=device.department_id, version=""))
                is_latest = latest_by_device[equipo_id][1]["id"] == imp["id"]
                for sw in self.rows("""SELECT nombre, fabricante, version, fecha_instalacion FROM software_instalado
                                       WHERE importacion_id = :i ORDER BY source_row""", i=imp["id"]):
                    product = resolver.product(sw["nombre"], sw["fabricante"], sw["version"])
                    ver = resolver.version(product, sw["version"])
                    if (device.id, product.id, ver.version) not in seen:
                        seen.add((device.id, product.id, ver.version))
                        self.db.add(InventorySnapshotItem(snapshot_id=snap.id, device_id=device.id,
                                                          department_id=device.department_id, product_id=product.id,
                                                          version=ver.version))
                    if is_latest and not device.status == "retired":
                        self._install(device, product.id, ver.id, panda.code, _dt(imp["fecha_importacion"]),
                                      _dt(sw.get("fecha_instalacion")))
            snap.totals = {"devices": n_dev, "installations": len(seen),
                           "products": len({p for _, p, _ in seen}), "by_status": {}}
            self.report["new.legacy_snapshots"] += 1
        self.report["new.products"] += len(resolver.created)
        # Registro de la carga como ejecución (trazabilidad de procedencia)
        self.db.add(InventoryRun(source_id=panda.id, trigger="legacy", status="succeeded", requested_by=self.actor,
                                 started_at=self.now, finished_at=utcnow(), is_complete=False,
                                 stats={"legacy_imports": len(imports), "periods": periods}))

    def _install(self, device: Device, product_id: int, version_id: int, source: str,
                 seen_at: datetime | None, installed: datetime | None) -> None:
        exists = self.db.execute(select(SoftwareInstallation).where(
            SoftwareInstallation.device_id == device.id, SoftwareInstallation.product_id == product_id,
            SoftwareInstallation.version_id == version_id, SoftwareInstallation.source == source)).scalar_one_or_none()
        if exists is None:
            self.db.add(SoftwareInstallation(device_id=device.id, product_id=product_id, version_id=version_id,
                                             source=source, present=True, first_seen_at=seen_at or self.now,
                                             last_seen_at=seen_at or self.now, install_date=installed))
            self.db.flush()
            self.report["new.installations"] += 1
        if seen_at and (device.last_seen_at is None or seen_at > device.last_seen_at):
            device.last_seen_at, device.last_seen_source = seen_at, source

    def _next_version(self, period: str) -> int:
        from sqlalchemy import func

        return (self.db.execute(select(func.max(InventorySnapshot.version)).where(InventorySnapshot.period == period))
                .scalar() or 0) + 1

    # ------------------------------------------------------------------ autorizaciones
    def authorizations(self) -> None:
        if "software_autorizado" not in self.tables:
            return
        resolver = ProductResolver(self.db, self.now)
        for row in self.rows("SELECT * FROM software_autorizado WHERE activo = 1 ORDER BY id"):
            self.report["legacy.software_autorizado"] += 1
            marker = f"legacy:software_autorizado:{row['id']}"
            if self.db.execute(select(SoftwarePolicy).where(SoftwarePolicy.justification.like(f"%[{marker}]"))).first():
                self.report["skip.policies_already_migrated"] += 1
                continue
            product = resolver.product(row["nombre"], row.get("fabricante"), row.get("version"))
            device = self.device_map.get(row.get("equipo_id")) if row.get("equipo_id") else None
            dept_id = self.dept_map.get(row.get("departamento_id")) if row.get("departamento_id") else None
            scope = "device" if device else "department" if dept_id else "global"
            motivo = " / ".join(x for x in (row.get("motivo"), row.get("observaciones"), row.get("usuario_texto")) if x)
            self.db.add(SoftwarePolicy(
                product_id=product.id, scope=scope, device_id=device.id if device else None,
                department_id=dept_id if scope == "department" else None, status="authorized",
                justification=f"{motivo or 'Autorizado en el sistema anterior'} [{marker}]",
                approved_by=None, created_by=self.actor,
                valid_from=_dt(row.get("fecha_autorizacion")) or _dt(row.get("fecha_alta")) or self.now))
            if scope == "global":
                product.authorization_status = "authorized"
            self.report[f"new.policies_{scope}"] += 1

    def ens_catalog(self) -> None:
        if "software" not in self.tables:
            return
        for row in self.rows("""SELECT nombre, version_referencia, clasificacion_informacion, observaciones_elena,
                                observaciones_toni FROM software WHERE activo = 1"""):
            key = name_key(row["nombre"], row.get("version_referencia"))
            products = self.db.execute(select(SoftwareProduct).where(SoftwareProduct.name_key == key)).scalars().all()
            if len(products) != 1:
                self.report["ens.unmatched" if not products else "ens.ambiguous"] += 1
                continue
            p = products[0]
            if row.get("clasificacion_informacion") and not p.ens_classification:
                p.ens_classification = row["clasificacion_informacion"]
            obs = " | ".join(x for x in (row.get("observaciones_elena"), row.get("observaciones_toni")) if x)
            if obs and not p.notes:
                p.notes = f"ENS (sistema anterior): {obs}"
            self.report["ens.matched"] += 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--legacy-url", required=True, help="URL SQLAlchemy de la BD legacy (usuario de solo lectura)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    legacy_engine = create_engine(args.legacy_url, future=True)
    with legacy_engine.connect() as legacy, session_factory()() as db:
        result = LegacyImporter(legacy, db).run()
        if args.dry_run:
            db.rollback()
            result["dry_run"] = True
        else:
            db.commit()
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
