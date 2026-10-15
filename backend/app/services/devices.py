"""Identidad, conciliación y asignaciones de dispositivos."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.connectors.base import DeviceRecord
from app.db import utcnow
from app.models import (
    Device,
    DeviceAssignment,
    DeviceExternalId,
    DeviceType,
    InventoryChange,
    ReviewCase,
    User,
)
from app.services.normalization import hostname_key, serial_key

# Solo identificadores emitidos por las plataformas sirven para conciliar sin ambigüedad.
STRONG_ID_TYPES = ("intune_device_id", "entra_device_id")
MANUAL_PRIORITY = 0

# Atributos que una fuente puede aportar. Los administrativos (departamento, ubicación,
# estado, notas) solo se cambian manualmente.
SYNC_FIELDS = (
    "hostname", "serial_number", "manufacturer", "model", "os_name", "os_version", "ram_bytes",
    "storage_total_bytes", "storage_free_bytes", "mac_wifi", "mac_ethernet", "encrypted",
    "compliance_state", "management_state", "ownership", "enrolled_at", "source_last_sync_at",
)
# Cambios que merecen quedar en el histórico (los volátiles como espacio libre, no).
TRACKED_FIELDS = {
    "hostname", "serial_number", "manufacturer", "model", "os_name", "os_version", "ram_bytes",
    "storage_total_bytes", "encrypted", "compliance_state",
}


@dataclass
class MatchOutcome:
    device: Device | None
    created: bool = False
    changes: list[InventoryChange] = field(default_factory=list)
    review_case: ReviewCase | None = None


def _open_case(db: Session, case_type: str, dedup_key: str, summary: str, data: dict, run_id: int | None) -> ReviewCase:
    existing = db.execute(
        select(ReviewCase).where(ReviewCase.dedup_key == dedup_key, ReviewCase.status == "open")
    ).scalar_one_or_none()
    if existing:
        return existing
    case = ReviewCase(case_type=case_type, dedup_key=dedup_key, summary=summary[:400], data=data, run_id=run_id)
    db.add(case)
    db.flush()
    return case


def _devices_by_serial(db: Session, serial: str) -> list[Device]:
    rows = db.execute(select(Device).where(func.upper(func.trim(Device.serial_number)) == serial)).scalars().all()
    return [d for d in rows if serial_key(d.serial_number) == serial]


def _strong_ids(device: Device) -> set[tuple[str, str]]:
    return {(e.id_type, e.value) for e in device.external_ids if e.id_type in STRONG_ID_TYPES}


def find_match(db: Session, rec: DeviceRecord, run_id: int | None = None) -> tuple[Device | None, ReviewCase | None]:
    """Devuelve el dispositivo existente que corresponde al registro, o un caso de revisión."""
    if rec.key.startswith("device:"):  # elegido explícitamente por un técnico
        return db.get(Device, int(rec.key.split(":", 1)[1])), None

    strong = [(t, v) for t, v in rec.ids.items() if t in STRONG_ID_TYPES]
    ids: set[int] = set()
    for id_type, value in strong:
        ids.update(db.execute(
            select(DeviceExternalId.device_id).where(DeviceExternalId.id_type == id_type,
                                                     DeviceExternalId.value == value)
        ).scalars())
    if len(ids) > 1:
        return None, _open_case(db, "device_match", f"ids:{sorted(strong)}",
                                f"Identificadores de {rec.hostname or rec.key} apuntan a varios dispositivos",
                                {"record": rec.raw or rec.ids, "device_ids": sorted(ids)}, run_id)
    if ids:
        return db.get(Device, ids.pop()), None

    serial = serial_key(rec.serial_number)
    if serial:
        same_serial = _devices_by_serial(db, serial)
        if len(same_serial) == 1:
            return same_serial[0], None  # mismo hardware (p.ej. reinscripción en Intune)
        if len(same_serial) > 1:
            return None, _open_case(db, "device_match", f"serial:{serial}",
                                    f"Número de serie {serial} compartido por varios dispositivos",
                                    {"serial": serial, "device_ids": [d.id for d in same_serial]}, run_id)

    hk = hostname_key(rec.hostname)
    if not hk:
        return None, None
    same_host = db.execute(select(Device).where(Device.hostname_key == hk, Device.status != "retired")).scalars().all()
    if not same_host:
        return None, None
    if len(same_host) > 1:
        return None, _open_case(db, "device_match", f"host:{hk}",
                                f"Varios dispositivos activos con el nombre {hk}",
                                {"hostname": hk, "device_ids": [d.id for d in same_host]}, run_id)
    cand = same_host[0]
    if not strong:
        return cand, None  # fuente sin identificadores fuertes (Panda): el hostname es lo único disponible
    # Fuente con identificadores fuertes: el hostname solo basta si el candidato no tiene
    # identidad propia y el número de serie no contradice.
    cand_serial = serial_key(cand.serial_number)
    if not _strong_ids(cand) and (cand_serial is None or serial is None or cand_serial == serial):
        return cand, None
    _open_case(db, "device_match", f"dup:{hk}:{sorted(strong)}",
               f"Posible duplicado: {hk} ya existe con otra identidad",
               {"hostname": hk, "existing_device_id": cand.id, "record_ids": dict(strong),
                "record_serial": rec.serial_number}, run_id)
    return None, None  # se creará un dispositivo nuevo; IT decide si fusionar


def upsert_user(db: Session, upn: str | None, display_name: str | None, source: str) -> User | None:
    if not upn:
        return None
    user = db.execute(select(User).where(User.upn == upn.lower())).scalar_one_or_none()
    if user is None:
        user = User(upn=upn.lower(), display_name=display_name, source=source)
        db.add(user)
        db.flush()
    elif display_name and not user.display_name:
        user.display_name = display_name
    return user


def current_assignment(db: Session, device_id: int) -> DeviceAssignment | None:
    return db.execute(
        select(DeviceAssignment).where(DeviceAssignment.device_id == device_id, DeviceAssignment.ended_at.is_(None))
        .order_by(DeviceAssignment.id.desc())
    ).scalars().first()


_UNSET = object()


def reassign(
    db: Session,
    device: Device,
    *,
    department_id=_UNSET,
    user_id=_UNSET,
    reason: str | None = None,
    actor: str = "system",
    source: str = "manual",
    run_id: int | None = None,
    at: datetime | None = None,
) -> list[InventoryChange]:
    """Cambia departamento y/o usuario cerrando la asignación vigente (nunca se pierde historial)."""
    new_dept = device.department_id if department_id is _UNSET else department_id
    new_user = device.primary_user_id if user_id is _UNSET else user_id
    if new_dept == device.department_id and new_user == device.primary_user_id and current_assignment(db, device.id):
        return []
    now = at or utcnow()
    changes = []
    if new_dept != device.department_id:
        changes.append(InventoryChange(run_id=run_id, change_type="department_changed", device_id=device.id,
                                       field="department_id", old_value=_s(device.department_id),
                                       new_value=_s(new_dept), source=source, detected_at=now))
    if new_user != device.primary_user_id:
        changes.append(InventoryChange(run_id=run_id, change_type="user_changed", device_id=device.id,
                                       field="primary_user_id", old_value=_s(device.primary_user_id),
                                       new_value=_s(new_user), source=source, detected_at=now))
    if (open_ := current_assignment(db, device.id)) is not None:
        open_.ended_at = now
    db.add(DeviceAssignment(device_id=device.id, department_id=new_dept, user_id=new_user, started_at=now,
                            reason=reason, actor=actor, source=source))
    device.department_id = new_dept
    device.primary_user_id = new_user
    db.add_all(changes)
    return changes


def _s(value) -> str | None:
    return None if value is None else str(value)


def device_type_id(db: Session, code: str | None) -> int | None:
    if not code:
        return None
    return db.execute(select(DeviceType.id).where(DeviceType.code == code)).scalar_one_or_none()


def apply_record(
    db: Session,
    device: Device,
    rec: DeviceRecord,
    source: str,
    priority: int,
    priorities: dict[str, int],
    run_id: int | None,
    now: datetime,
) -> list[InventoryChange]:
    """Fusiona atributos respetando prioridad de fuente. Un valor vacío nunca borra uno conocido."""
    changes = []
    sources = dict(device.field_sources or {})
    for fname in SYNC_FIELDS:
        new = getattr(rec, fname)
        if new is None or (isinstance(new, str) and not new.strip()):
            continue
        owner = sources.get(fname, {}).get("source")
        owner_priority = MANUAL_PRIORITY if owner == "manual" else priorities.get(owner, 1000)
        if owner and owner != source and priority > owner_priority:
            continue  # una fuente más fiable ya aporta este dato
        old = getattr(device, fname)
        if old != new:
            setattr(device, fname, new)
            if fname in TRACKED_FIELDS and old is not None:
                changes.append(InventoryChange(run_id=run_id, change_type="device_updated", device_id=device.id,
                                               field=fname, old_value=_s(old), new_value=_s(new), source=source,
                                               detected_at=now))
        sources[fname] = {"source": source, "at": now.isoformat(timespec="seconds")}
    device.field_sources = sources
    device.hostname_key = hostname_key(device.hostname)
    if device.device_type_id is None and rec.device_type:
        device.device_type_id = device_type_id(db, rec.device_type)
    db.add_all(changes)
    return changes


def attach_ids(db: Session, device: Device, rec: DeviceRecord, source: str, run_id: int | None, now: datetime) -> None:
    for id_type, value in rec.ids.items():
        if id_type not in STRONG_ID_TYPES:
            continue
        ext = db.execute(select(DeviceExternalId).where(
            DeviceExternalId.source == source, DeviceExternalId.id_type == id_type, DeviceExternalId.value == value
        )).scalar_one_or_none()
        if ext is None:
            other = db.execute(select(DeviceExternalId).where(
                DeviceExternalId.id_type == id_type, DeviceExternalId.value == value,
                DeviceExternalId.device_id != device.id,
            )).scalars().first()
            if other:
                _open_case(db, "device_match", f"idconflict:{id_type}:{value}",
                           f"{id_type} {value} ya pertenece a otro dispositivo",
                           {"device_id": device.id, "other_device_id": other.device_id}, run_id)
                continue
            db.add(DeviceExternalId(device_id=device.id, source=source, id_type=id_type, value=value,
                                    first_seen_at=now, last_seen_at=now))
        elif ext.device_id == device.id:
            ext.last_seen_at = now


def reconcile(
    db: Session,
    rec: DeviceRecord,
    source: str,
    priority: int,
    priorities: dict[str, int],
    run_id: int | None,
    now: datetime,
    allow_create: bool = True,
) -> MatchOutcome:
    device, case = find_match(db, rec, run_id)
    if device is None and case is not None:
        return MatchOutcome(None, review_case=case)
    created = False
    changes: list[InventoryChange] = []
    if device is None:
        if not allow_create:
            return MatchOutcome(None)
        device = Device(first_seen_at=now, status="active", field_sources={})
        db.add(device)
        db.flush()
        created = True
        changes.append(InventoryChange(run_id=run_id, change_type="device_added", device_id=device.id,
                                       new_value=rec.hostname or rec.serial_number, source=source, detected_at=now))
        db.add(changes[-1])
    elif device.status == "retired":
        changes.append(InventoryChange(run_id=run_id, change_type="retired_device_observed", device_id=device.id,
                                       new_value=rec.hostname, source=source, detected_at=now))
        db.add(changes[-1])
    changes += apply_record(db, device, rec, source, priority, priorities, run_id, now)
    attach_ids(db, device, rec, source, run_id, now)
    device.last_seen_at = now
    device.last_seen_source = source

    if rec.user_upn:
        user = upsert_user(db, rec.user_upn, rec.user_display_name, source)
        owner = (device.field_sources or {}).get("primary_user_id", {}).get("source")
        if user and user.id != device.primary_user_id and owner != "manual":
            changes += reassign(db, device, user_id=user.id, reason=f"Usuario principal según {source}",
                                actor=f"sync:{source}", source=source, run_id=run_id, at=now)
    return MatchOutcome(device, created=created, changes=changes)
