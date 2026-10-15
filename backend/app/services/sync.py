"""Motor común de sincronización.

Pipeline: extracción -> validación -> observaciones originales -> normalización ->
conciliación -> actualización operativa -> comparación -> alertas -> registro.

Garantías:
- Idempotente: reprocesar el mismo lote no duplica dispositivos, instalaciones ni alertas.
- Una extracción parcial nunca produce bajas: solo se infieren desinstalaciones en los
  equipos cuyo software se leyó íntegro, y ausencias de equipos solo con extracción completa.
- Una caída anómala de volumen respecto a la última ejecución completa degrada la ejecución
  a parcial y abre una alerta crítica.
"""
from __future__ import annotations

import hashlib
import json
import traceback
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.base import ConnectorError, ExtractResult
from app.db import utcnow
from app.models import (
    Device,
    DeviceExternalId,
    InventoryChange,
    InventoryObservation,
    InventoryRun,
    InventorySource,
    SoftwareInstallation,
)
from app.services import audit
from app.services.alerts import evaluate_unauthorized, open_alert, resolve_alerts
from app.services.devices import reconcile
from app.services.software import ProductResolver

DEVICE_DROP_THRESHOLD = 0.25
INSTALL_DROP_THRESHOLD = 0.40
DEVICE_MIN_INSTALLS = 10  # por debajo, una variación grande es normal


def _hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _obs_key(*parts: Any) -> str:
    key = "|".join("" if p is None else str(p) for p in parts)
    return key if len(key) <= 190 else hashlib.sha256(key.encode()).hexdigest()


class SyncEngine:
    def __init__(self, db: Session, connector_factory: Callable[[InventorySource, dict], Any]):
        self.db = db
        self.connector_factory = connector_factory

    # ------------------------------------------------------------------ ciclo de vida
    def execute(self, run: InventoryRun) -> InventoryRun:
        db = self.db
        source = db.get(InventorySource, run.source_id)
        run.status, run.started_at, run.log = "running", utcnow(), []
        db.commit()
        lines: list[str] = []

        def log(msg: str) -> None:
            lines.append(f"{utcnow().isoformat(timespec='seconds')} {msg}")

        params = dict(run.params or {})
        try:
            connector = self.connector_factory(source, params)
            result = connector.extract(params, log)
            self._validate(result)
            stats = self.process(run, source, result, log)
            run.stats = {**(run.stats or {}), **result.stats, **stats}
            # is_complete: extracción íntegra de todo el parque (solo así cuenta para el inventario mensual).
            # partial: hubo errores o una caída anómala; los datos recibidos se aplican, pero sin bajas.
            run.is_complete = stats["complete"]
            run.status = "partial" if (result.errors or stats["anomaly"]) else "succeeded"
            if result.errors:
                run.error = "\n".join(result.errors[:20])
            if source.kind == "api":
                if run.status == "succeeded" and run.is_complete:
                    source.last_success_at = run.finished_at = utcnow()
                    source.last_error = None
                    resolve_alerts(db, {f"sync_failed:{source.code}"}, resolution="Sincronización correcta")
                elif run.status == "partial":
                    open_alert(db, f"sync_partial:{source.code}", "sync_partial", "warning",
                               f"{source.name}: sincronización incompleta", run.error, run_id=run.id)
        except Exception as exc:  # noqa: BLE001 - se registra y la ejecución queda como fallida
            db.rollback()
            run = db.get(InventoryRun, run.id)
            source = db.get(InventorySource, run.source_id)
            kind = exc.kind if isinstance(exc, ConnectorError) else "internal"
            run.status, run.is_complete = "failed", False
            run.error = f"[{kind}] {exc}" if isinstance(exc, ConnectorError) else f"[internal] {type(exc).__name__}: {exc}"
            if not isinstance(exc, ConnectorError):
                log(traceback.format_exc(limit=5))
            source.last_error = run.error[:2000]
            open_alert(db, f"sync_failed:{source.code}", "sync_failed",
                       "critical" if kind in ("auth", "permission") else "warning",
                       f"{source.name}: la sincronización ha fallado", run.error, run_id=run.id)
        run.finished_at = utcnow()
        run.log = lines[-500:]
        audit.record(db, run.requested_by or "system", f"run.{run.status}", "inventory_run", run.id,
                     f"{source.code} {run.trigger}: {run.status}", after={"stats": run.stats, "error": run.error})
        db.commit()
        return run

    @staticmethod
    def _validate(result: ExtractResult) -> None:
        keys = [d.key for d in result.devices]
        if len(keys) != len(set(keys)):
            dup = {k for k in keys if keys.count(k) > 1}
            raise ConnectorError(f"La fuente devolvió claves de dispositivo duplicadas: {sorted(dup)[:5]}", kind="data")
        known = set(keys)
        orphans = {i.device_key for i in result.installs} - known
        if orphans:
            result.warnings.append(f"{len(orphans)} equipos con software pero sin ficha; se ignoran.")
            result.software_complete_for -= orphans
            result.installs = [i for i in result.installs if i.device_key in known]

    # ------------------------------------------------------------------ procesamiento
    def process(self, run: InventoryRun, source: InventorySource, result: ExtractResult, log) -> dict:
        db = self.db
        now = utcnow()
        priorities = {s.code: s.priority for s in db.execute(select(InventorySource)).scalars()}
        anomaly = False

        # Caída anómala respecto a la última ejecución completa de la misma fuente.
        prev = db.execute(
            select(InventoryRun).where(InventoryRun.source_id == source.id, InventoryRun.is_complete.is_(True),
                                       InventoryRun.id != run.id).order_by(InventoryRun.id.desc()).limit(1)
        ).scalar_one_or_none()
        if prev and prev.stats and result.complete and source.kind == "api":
            prev_dev, prev_inst = prev.stats.get("devices_seen", 0), prev.stats.get("installs_seen", 0)
            drop_dev = prev_dev and (prev_dev - len(result.devices)) / prev_dev > DEVICE_DROP_THRESHOLD
            drop_inst = prev_inst and (prev_inst - len(result.installs)) / prev_inst > INSTALL_DROP_THRESHOLD
            if drop_dev or drop_inst:
                anomaly = True
                msg = (f"Caída anómala: {len(result.devices)} dispositivos (antes {prev_dev}), "
                       f"{len(result.installs)} instalaciones (antes {prev_inst}). No se infieren bajas.")
                log(msg)
                result.warnings.append(msg)
                open_alert(db, f"anomalous_drop:{source.code}", "anomalous_drop", "critical",
                           f"{source.name}: caída anómala de registros", msg, run_id=run.id)

        # 1. Observaciones originales.
        seen_obs: set[tuple[str, str]] = set()
        for d in result.devices:
            self._observe(run, "device", d.key, d.raw or {"ids": d.ids, "hostname": d.hostname}, seen_obs, now)
        for i in result.installs:
            self._observe(run, "install", _obs_key(i.device_key, i.name, i.publisher, i.version),
                          {"device": i.device_key, "name": i.name, "publisher": i.publisher,
                           "version": i.version, **(i.raw or {})}, seen_obs, now)
        db.flush()

        # 2. Conciliación de dispositivos.
        device_map: dict[str, Device] = {}
        created_devices = review_cases = 0
        changes: list[InventoryChange] = []
        for rec in result.devices:
            outcome = reconcile(db, rec, source.code, source.priority, priorities, run.id, now)
            if outcome.device is None:
                review_cases += outcome.review_case is not None
                continue
            device_map[rec.key] = outcome.device
            created_devices += outcome.created
            changes += outcome.changes
            resolve_alerts(db, {f"not_observed:{source.code}:{outcome.device.id}"}, resolution="Dispositivo observado")
        db.flush()

        # 3. Software.
        resolver = ProductResolver(db, now)
        observed: dict[int, set[tuple[int, int]]] = defaultdict(set)
        new_installs: dict[int, list[SoftwareInstallation]] = defaultdict(list)
        existing = self._existing_installs(source.code, {d.id for d in device_map.values()})
        present_before = {dev: sum(1 for r in rows.values() if r.present) for dev, rows in existing.items()}
        baseline_devices = {dev_id for dev_id in {d.id for d in device_map.values()} if not existing.get(dev_id)}
        for inst in result.installs:
            device = device_map.get(inst.device_key)
            if device is None or not inst.name:
                continue
            product = resolver.product(inst.name, inst.publisher, inst.version)
            version = resolver.version(product, inst.version)
            key = (product.id, version.id)
            if key in observed[device.id]:
                continue
            observed[device.id].add(key)
            row = existing.get(device.id, {}).get(key)
            if row is None:
                row = SoftwareInstallation(device_id=device.id, product_id=product.id, version_id=version.id,
                                           source=source.code, present=True, first_seen_at=now, last_seen_at=now,
                                           last_run_id=run.id, install_date=inst.install_date)
                db.add(row)
                existing.setdefault(device.id, {})[key] = row
                new_installs[device.id].append(row)
            else:
                if not row.present:
                    row.present, row.removed_at = True, None
                    new_installs[device.id].append(row)
                row.last_seen_at, row.last_run_id = now, run.id
                row.install_date = row.install_date or inst.install_date
        db.flush()

        # 4. Desinstalaciones (solo equipos con lectura íntegra) y cambios de versión.
        # Desinstalaciones: solo en equipos cuyo software se leyó íntegro, sin errores ni anomalías.
        complete_devices = {device_map[k].id for k in result.software_complete_for if k in device_map}
        if result.errors or anomaly:
            complete_devices = set()
        complete = result.complete and not anomaly
        # Salvaguarda por equipo: si su software cae bruscamente (p.ej. pegado truncado), no se infieren bajas.
        for device_id in sorted(complete_devices):
            before = present_before.get(device_id, 0)
            now_seen = len(observed[device_id])
            if before >= DEVICE_MIN_INSTALLS and now_seen < before * (1 - INSTALL_DROP_THRESHOLD):
                complete_devices.discard(device_id)
                msg = f"Dispositivo {device_id}: {now_seen} programas frente a {before}; no se infieren desinstalaciones."
                log(msg)
                result.warnings.append(msg)
                open_alert(db, f"device_drop:{source.code}:{device_id}", "anomalous_drop", "warning",
                           "Caída anómala de software en un dispositivo", msg, device_id=device_id, run_id=run.id)
        removed_count = installed_count = version_changes = 0
        for device_id, rows in existing.items():
            removed: list[SoftwareInstallation] = []
            if device_id in complete_devices:
                for key, row in rows.items():
                    if row.present and key not in observed[device_id]:
                        row.present, row.removed_at = False, now
                        removed.append(row)
            if device_id in baseline_devices:
                if new_installs[device_id]:
                    changes.append(self._change(run, "software_baseline", device_id, None, None,
                                                str(len(new_installs[device_id])), source.code, now))
                continue
            added_by_product = {r.product_id: r for r in new_installs[device_id]}
            for row in removed:
                if row.product_id in added_by_product:
                    new = added_by_product.pop(row.product_id)
                    changes.append(self._change(run, "software_version_changed", device_id, row.product_id,
                                                row.version.version, new.version.version, source.code, now))
                    version_changes += 1
                else:
                    changes.append(self._change(run, "software_removed", device_id, row.product_id,
                                                row.version.version, None, source.code, now))
                    removed_count += 1
            for row in added_by_product.values():
                changes.append(self._change(run, "software_installed", device_id, row.product_id, None,
                                            row.version.version, source.code, now))
                installed_count += 1

        # 5. Dispositivos no observados en una extracción completa de la fuente de existencia.
        not_observed = 0
        if complete and source.kind == "api":
            seen_ids = {d.id for d in device_map.values()}
            known = db.execute(
                select(Device).join(DeviceExternalId, DeviceExternalId.device_id == Device.id)
                .where(DeviceExternalId.source == source.code, Device.status != "retired").distinct()
            ).scalars().all()
            for dev in known:
                if dev.id in seen_ids:
                    continue
                _, created = open_alert(db, f"not_observed:{source.code}:{dev.id}", "device_not_observed", "warning",
                                        f"{dev.display_name} no aparece en {source.name}",
                                        "Puede haber sido retirado de la administración. Revise y dé de baja si "
                                        "corresponde; no se da de baja automáticamente.", device_id=dev.id,
                                        run_id=run.id)
                if created:
                    changes.append(self._change(run, "device_not_observed", dev.id, None, None, None, source.code, now))
                    not_observed += 1

        # 6. Software nuevo en el catálogo (solo tras la primera carga de la fuente).
        if prev is not None:
            for product in resolver.created:
                if product.is_relevant:
                    open_alert(db, f"new_software:{product.id}", "new_software", "info",
                               f"Nuevo software pendiente de clasificar: {product.name}", product_id=product.id,
                               run_id=run.id)
        for product in resolver.created:
            changes.append(self._change(run, "software_new_product", None, product.id, None, product.name,
                                        source.code, now))

        db.flush()
        auth = evaluate_unauthorized(db, run.id)
        log(f"Procesado: {len(device_map)} dispositivos ({created_devices} nuevos), "
            f"{sum(len(v) for v in observed.values())} instalaciones, {len(resolver.created)} productos nuevos, "
            f"{installed_count} altas, {removed_count} bajas, {version_changes} cambios de versión.")
        return {
            "complete": complete,
            "anomaly": anomaly,
            "devices_seen": len(result.devices),
            "devices_matched": len(device_map),
            "devices_created": created_devices,
            "review_cases": review_cases,
            "installs_seen": len(result.installs),
            "installations_present": sum(len(v) for v in observed.values()),
            "products_created": len(resolver.created),
            "software_installed": installed_count,
            "software_removed": removed_count,
            "software_version_changed": version_changes,
            "devices_not_observed": not_observed,
            "devices_software_complete": len(complete_devices),
            "unauthorized_active": auth["active"],
            "warnings": result.warnings[:50],
            "changes": len(changes),
        }

    # ------------------------------------------------------------------ utilidades
    def _observe(self, run: InventoryRun, entity: str, key: str, payload: dict, seen: set, now: datetime) -> None:
        if (entity, key) in seen:
            return
        seen.add((entity, key))
        self.db.add(InventoryObservation(run_id=run.id, entity=entity, external_key=key[:190],
                                         payload=json.loads(json.dumps(payload, default=str)),
                                         payload_hash=_hash(payload), observed_at=now))

    def _existing_installs(self, source_code: str, device_ids: set[int]) -> dict[int, dict[tuple[int, int], SoftwareInstallation]]:
        out: dict[int, dict] = defaultdict(dict)
        if not device_ids:
            return out
        rows = self.db.execute(select(SoftwareInstallation).where(
            SoftwareInstallation.source == source_code, SoftwareInstallation.device_id.in_(device_ids)
        )).scalars()
        for row in rows:
            out[row.device_id][(row.product_id, row.version_id)] = row
        return out

    def _change(self, run, change_type, device_id, product_id, old, new, source_code, now) -> InventoryChange:
        change = InventoryChange(run_id=run.id, change_type=change_type, device_id=device_id, product_id=product_id,
                                 old_value=old, new_value=new, source=source_code, detected_at=now)
        self.db.add(change)
        return change
