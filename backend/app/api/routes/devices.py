from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.api.common import Page, export_response, not_found, paginate
from app.core.config import get_settings
from app.core.security import Admin, CurrentUser, Reader, Technician
from app.db import get_db, utcnow
from app.models import (
    AuditEvent,
    Department,
    Device,
    DeviceAssignment,
    DeviceExternalId,
    DeviceType,
    InventoryChange,
    InventoryObservation,
    InventoryRun,
    SoftwareInstallation,
    SoftwareProduct,
    SoftwareVersion,
    User,
)
from app.models.devices import DEVICE_STATUSES
from app.services import audit
from app.services.devices import reassign, upsert_user
from app.services.normalization import hostname_key
from app.services.software import PolicyEvaluator

router = APIRouter(prefix="/api/devices", tags=["Dispositivos"])

EDITABLE = ["hostname", "serial_number", "manufacturer", "model", "os_name", "os_version", "location", "notes",
            "processor", "ram_bytes", "storage_total_bytes", "purchase_date", "cost", "status", "device_type_id"]
AUDIT_FIELDS = EDITABLE + ["department_id", "primary_user_id", "retired_at"]


def freshness(device: Device, stale_days: int, now: datetime | None = None) -> str:
    """vigente | no_observado | sin_sincronizar | retirado."""
    if device.status == "retired":
        return "retired"
    if device.last_seen_at is None:
        return "never_synced"
    if (now or utcnow()) - device.last_seen_at > timedelta(days=stale_days):
        return "stale"
    return "current"


def _sources(db: Session, ids: list[int]) -> dict[int, list[str]]:
    out: dict[int, set] = {}
    for dev_id, src in db.execute(select(DeviceExternalId.device_id, DeviceExternalId.source)
                                  .where(DeviceExternalId.device_id.in_(ids)).distinct()):
        out.setdefault(dev_id, set()).add(src)
    for dev_id, src in db.execute(select(SoftwareInstallation.device_id, SoftwareInstallation.source)
                                  .where(SoftwareInstallation.device_id.in_(ids)).distinct()):
        out.setdefault(dev_id, set()).add(src)
    return {k: sorted(v) for k, v in out.items()}


def serialize(d: Device, stale_days: int, extra: dict | None = None) -> dict:
    return {
        "id": d.id, "uid": d.uid, "name": d.display_name, "hostname": d.hostname, "serial_number": d.serial_number,
        "manufacturer": d.manufacturer, "model": d.model, "os_name": d.os_name, "os_version": d.os_version,
        "device_type_id": d.device_type_id, "device_type": d.device_type.name if d.device_type else None,
        "status": d.status, "freshness": freshness(d, stale_days),
        "department_id": d.department_id, "department": d.department.name if d.department else None,
        "primary_user_id": d.primary_user_id,
        "primary_user": (d.primary_user.display_name or d.primary_user.upn) if d.primary_user else None,
        "primary_user_upn": d.primary_user.upn if d.primary_user else None,
        "location": d.location, "compliance_state": d.compliance_state, "encrypted": d.encrypted,
        "ram_bytes": d.ram_bytes, "storage_total_bytes": d.storage_total_bytes,
        "last_seen_at": d.last_seen_at, "last_seen_source": d.last_seen_source,
        "source_last_sync_at": d.source_last_sync_at, **(extra or {}),
    }


def _filtered(q: str | None, status: str | None, department_id: int | None, device_type_id: int | None,
              freshness_f: str | None, unassigned: bool | None, stale_days: int):
    query = select(Device)
    if q:
        like = f"%{q.strip()}%"
        query = query.outerjoin(User, User.id == Device.primary_user_id).where(or_(
            Device.hostname.ilike(like), Device.serial_number.ilike(like), Device.model.ilike(like),
            Device.manufacturer.ilike(like), User.upn.ilike(like), User.display_name.ilike(like),
            Device.location.ilike(like), Device.uid == q.strip(),
        ))
    if status:
        query = query.where(Device.status.in_(status.split(",")))
    elif freshness_f != "retired":
        query = query.where(Device.status != "retired")
    if department_id:
        query = query.where(Device.department_id == department_id)
    if unassigned:
        query = query.where(Device.department_id.is_(None))
    if device_type_id:
        query = query.where(Device.device_type_id == device_type_id)
    limit = utcnow() - timedelta(days=stale_days)
    if freshness_f == "stale":
        query = query.where(Device.last_seen_at < limit, Device.status != "retired")
    elif freshness_f == "never_synced":
        query = query.where(Device.last_seen_at.is_(None))
    elif freshness_f == "current":
        query = query.where(Device.last_seen_at >= limit)
    elif freshness_f == "retired":
        query = query.where(Device.status == "retired")
    return query


SORTABLE = {"name": Device.hostname, "serial_number": Device.serial_number, "model": Device.model,
            "os_version": Device.os_version, "last_seen_at": Device.last_seen_at, "status": Device.status,
            "department": Device.department_id}


@router.get("")
def list_devices(page: Page = Depends(), q: str | None = None, status: str | None = None,
                 department_id: int | None = None, device_type_id: int | None = None,
                 freshness: str | None = Query(None, pattern="^(current|stale|never_synced|retired)$"),
                 unassigned: bool | None = None, db: Session = Depends(get_db), _: CurrentUser = Reader):
    stale_days = get_settings().stale_device_days
    query = _filtered(q, status, department_id, device_type_id, freshness, unassigned, stale_days)
    rows, total = paginate(db, query, page, SORTABLE, Device.hostname.asc())
    devices = [r[0] for r in rows]
    ids = [d.id for d in devices]
    counts = dict(db.execute(select(SoftwareInstallation.device_id, func.count(func.distinct(SoftwareInstallation.product_id)))
                             .where(SoftwareInstallation.device_id.in_(ids), SoftwareInstallation.present.is_(True))
                             .group_by(SoftwareInstallation.device_id)).all()) if ids else {}
    sources = _sources(db, ids) if ids else {}
    return {"total": total, "items": [serialize(d, stale_days, {"software_count": counts.get(d.id, 0),
                                                                "sources": sources.get(d.id, [])}) for d in devices]}


@router.get("/export")
def export_devices(format: str = Query("xlsx", pattern="^(csv|xlsx)$"), q: str | None = None,
                   status: str | None = None, department_id: int | None = None, device_type_id: int | None = None,
                   freshness: str | None = None, db: Session = Depends(get_db), user: CurrentUser = Reader):
    stale_days = get_settings().stale_device_days
    query = _filtered(q, status, department_id, device_type_id, freshness, None, stale_days).order_by(Device.hostname)
    rows = [serialize(d, stale_days) for d in db.execute(query).scalars()]
    for r in rows:
        r["ram_gb"] = round(r["ram_bytes"] / 1024**3, 1) if r["ram_bytes"] else None
        r["storage_gb"] = round(r["storage_total_bytes"] / 1000**3) if r["storage_total_bytes"] else None
    audit.record(db, user.upn, "export.devices", "device", None, f"Exportación de {len(rows)} dispositivos ({format})")
    db.commit()
    cols = [("name", "Equipo"), ("serial_number", "Nº serie"), ("device_type", "Tipo"), ("manufacturer", "Fabricante"),
            ("model", "Modelo"), ("os_name", "SO"), ("os_version", "Versión SO"), ("department", "Departamento"),
            ("primary_user", "Usuario"), ("primary_user_upn", "UPN"), ("status", "Estado"),
            ("freshness", "Actualidad"), ("compliance_state", "Cumplimiento"), ("encrypted", "Cifrado"),
            ("ram_gb", "RAM (GB)"), ("storage_gb", "Disco (GB)"), ("location", "Ubicación"),
            ("last_seen_at", "Última observación"), ("last_seen_source", "Fuente")]
    return export_response(rows, cols, f"dispositivos_{utcnow():%Y%m%d}", format)


class DeviceIn(BaseModel):
    hostname: str | None = Field(None, max_length=150)
    serial_number: str | None = Field(None, max_length=120)
    manufacturer: str | None = Field(None, max_length=120)
    model: str | None = Field(None, max_length=160)
    os_name: str | None = Field(None, max_length=80)
    os_version: str | None = Field(None, max_length=80)
    device_type_id: int | None = None
    status: str | None = Field(None, pattern="^(active|in_stock|repair|lost)$")
    location: str | None = Field(None, max_length=150)
    notes: str | None = Field(None, max_length=5000)
    processor: str | None = Field(None, max_length=200)
    ram_bytes: int | None = Field(None, ge=0)
    storage_total_bytes: int | None = Field(None, ge=0)
    purchase_date: datetime | None = None
    cost: str | None = Field(None, max_length=30)
    department_id: int | None = None
    primary_user_upn: str | None = Field(None, max_length=255)


def _check_refs(db: Session, data: dict) -> None:
    if data.get("device_type_id") and not db.get(DeviceType, data["device_type_id"]):
        raise HTTPException(422, "Tipo de dispositivo no válido")
    if data.get("department_id"):
        dept = db.get(Department, data["department_id"])
        if not dept or not dept.active:
            raise HTTPException(422, "Departamento no válido o inactivo")


@router.post("", status_code=201)
def create_device(body: DeviceIn, db: Session = Depends(get_db), user: CurrentUser = Technician):
    data = body.model_dump(exclude_unset=True)
    if not (data.get("hostname") or data.get("serial_number")):
        raise HTTPException(422, "Indique al menos el nombre o el número de serie")
    _check_refs(db, data)
    dept_id = data.pop("department_id", None)
    upn = data.pop("primary_user_upn", None)
    now = utcnow()
    data["status"] = data.get("status") or "active"
    device = Device(**data, first_seen_at=now,
                    field_sources={k: {"source": "manual", "at": now.isoformat(timespec="seconds")} for k in data})
    device.hostname_key = hostname_key(device.hostname)
    db.add(device)
    db.flush()
    owner = upsert_user(db, upn, None, "manual") if upn else None
    reassign(db, device, department_id=dept_id, user_id=owner.id if owner else None, reason="Alta manual",
             actor=user.upn)
    db.add(InventoryChange(change_type="device_added", device_id=device.id, new_value=device.display_name,
                           source="manual", detected_at=now))
    audit.record(db, user.upn, "device.create", "device", device.id, f"Alta manual de {device.display_name}",
                 after=audit.snapshot(device, AUDIT_FIELDS))
    db.commit()
    return get_device(device.id, db, user)


@router.get("/{device_id}")
def get_device(device_id: int, db: Session = Depends(get_db), _: CurrentUser = Reader):
    d = db.get(Device, device_id)
    if d is None:
        raise not_found("Dispositivo")
    stale_days = get_settings().stale_device_days
    data = serialize(d, stale_days)
    data.update({
        "notes": d.notes, "processor": d.processor, "storage_free_bytes": d.storage_free_bytes,
        "mac_wifi": d.mac_wifi, "mac_ethernet": d.mac_ethernet, "management_state": d.management_state,
        "ownership": d.ownership, "enrolled_at": d.enrolled_at, "first_seen_at": d.first_seen_at,
        "retired_at": d.retired_at, "purchase_date": d.purchase_date, "cost": d.cost,
        "created_at": d.created_at, "updated_at": d.updated_at, "field_sources": d.field_sources or {},
        "external_ids": [{"source": e.source, "type": e.id_type, "value": e.value, "first_seen_at": e.first_seen_at,
                          "last_seen_at": e.last_seen_at} for e in d.external_ids],
        "legacy_equipo_id": d.legacy_equipo_id,
    })
    return data


@router.patch("/{device_id}")
def update_device(device_id: int, body: DeviceIn, db: Session = Depends(get_db), user: CurrentUser = Technician):
    d = db.get(Device, device_id)
    if d is None:
        raise not_found("Dispositivo")
    if d.status == "retired":
        raise HTTPException(409, "El dispositivo está dado de baja; reactívelo para editarlo")
    data = body.model_dump(exclude_unset=True)
    _check_refs(db, data)
    before = audit.snapshot(d, AUDIT_FIELDS)
    dept = data.pop("department_id", d.department_id)
    upn = data.pop("primary_user_upn", None)
    now = utcnow()
    sources = dict(d.field_sources or {})
    for key, value in data.items():
        if getattr(d, key) != value:
            if key in ("hostname", "serial_number", "model", "os_version", "ram_bytes", "status"):
                db.add(InventoryChange(change_type="device_updated", device_id=d.id, field=key,
                                       old_value=None if getattr(d, key) is None else str(getattr(d, key)),
                                       new_value=None if value is None else str(value), source="manual",
                                       detected_at=now))
            setattr(d, key, value)
            # Un dato corregido a mano prevalece sobre las fuentes automáticas.
            sources[key] = {"source": "manual", "at": now.isoformat(timespec="seconds"), "by": user.upn}
    d.hostname_key = hostname_key(d.hostname)
    user_id = d.primary_user_id
    if "primary_user_upn" in body.model_fields_set:
        owner = upsert_user(db, upn, None, "manual") if upn else None
        user_id = owner.id if owner else None
        sources["primary_user_id"] = {"source": "manual", "at": now.isoformat(timespec="seconds"), "by": user.upn}
    d.field_sources = sources
    reassign(db, d, department_id=dept, user_id=user_id, reason="Edición manual", actor=user.upn)
    audit.record(db, user.upn, "device.update", "device", d.id, f"Edición de {d.display_name}", before=before,
                 after=audit.snapshot(d, AUDIT_FIELDS))
    db.commit()
    return get_device(d.id, db, user)


class ReasonIn(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


@router.post("/{device_id}/retire")
def retire_device(device_id: int, body: ReasonIn, db: Session = Depends(get_db), user: CurrentUser = Technician):
    d = db.get(Device, device_id)
    if d is None:
        raise not_found("Dispositivo")
    if d.status == "retired":
        raise HTTPException(409, "Ya está dado de baja")
    before = audit.snapshot(d, AUDIT_FIELDS)
    now = utcnow()
    db.add(InventoryChange(change_type="device_retired", device_id=d.id, field="status", old_value=d.status,
                           new_value="retired", source="manual", detected_at=now))
    d.status, d.retired_at = "retired", now
    audit.record(db, user.upn, "device.retire", "device", d.id, f"Baja de {d.display_name}: {body.reason}",
                 before=before, after=audit.snapshot(d, AUDIT_FIELDS))
    db.commit()
    return get_device(d.id, db, user)


@router.post("/{device_id}/reactivate")
def reactivate_device(device_id: int, body: ReasonIn, db: Session = Depends(get_db), user: CurrentUser = Technician):
    d = db.get(Device, device_id)
    if d is None:
        raise not_found("Dispositivo")
    if d.status != "retired":
        raise HTTPException(409, "El dispositivo no está dado de baja")
    db.add(InventoryChange(change_type="device_reactivated", device_id=d.id, field="status", old_value="retired",
                           new_value="active", source="manual", detected_at=utcnow()))
    d.status, d.retired_at = "active", None
    audit.record(db, user.upn, "device.reactivate", "device", d.id, f"Reactivación: {body.reason}")
    db.commit()
    return get_device(d.id, db, user)


class BulkAssignIn(BaseModel):
    device_ids: list[int] = Field(..., min_length=1, max_length=1000)
    department_id: int | None
    reason: str = Field(..., min_length=3, max_length=500)


@router.post("/bulk-assign")
def bulk_assign(body: BulkAssignIn, db: Session = Depends(get_db), user: CurrentUser = Technician):
    _check_refs(db, {"department_id": body.department_id})
    devices = db.execute(select(Device).where(Device.id.in_(body.device_ids))).scalars().all()
    if len(devices) != len(set(body.device_ids)):
        raise HTTPException(404, "Algún dispositivo no existe")
    moved = 0
    for d in devices:
        if d.department_id != body.department_id:
            before = d.department_id
            reassign(db, d, department_id=body.department_id, reason=body.reason, actor=user.upn)
            audit.record(db, user.upn, "device.move", "device", d.id, f"{d.display_name}: departamento",
                         before={"department_id": before}, after={"department_id": body.department_id})
            moved += 1
    db.commit()
    return {"moved": moved, "unchanged": len(devices) - moved}


@router.get("/{device_id}/software")
def device_software(device_id: int, include_removed: bool = False, db: Session = Depends(get_db),
                    _: CurrentUser = Reader):
    d = db.get(Device, device_id)
    if d is None:
        raise not_found("Dispositivo")
    query = (select(SoftwareInstallation, SoftwareProduct, SoftwareVersion)
             .join(SoftwareProduct, SoftwareProduct.id == SoftwareInstallation.product_id)
             .join(SoftwareVersion, SoftwareVersion.id == SoftwareInstallation.version_id)
             .where(SoftwareInstallation.device_id == device_id))
    if not include_removed:
        query = query.where(SoftwareInstallation.present.is_(True))
    evaluator = PolicyEvaluator(db)
    items = []
    for inst, prod, ver in db.execute(query.order_by(SoftwareProduct.name)).all():
        status, origin = evaluator.evaluate(prod, d)
        items.append({
            "installation_id": inst.id, "product_id": prod.id, "name": prod.name, "publisher": prod.publisher,
            "category": prod.category, "is_relevant": prod.is_relevant, "version": ver.version or None,
            "source": inst.source, "present": inst.present, "first_seen_at": inst.first_seen_at,
            "last_seen_at": inst.last_seen_at, "removed_at": inst.removed_at, "install_date": inst.install_date,
            "authorization_status": status, "authorization_origin": origin,
        })
    return {"total": len(items), "items": items}


@router.get("/{device_id}/assignments")
def device_assignments(device_id: int, db: Session = Depends(get_db), _: CurrentUser = Reader):
    rows = db.execute(select(DeviceAssignment).where(DeviceAssignment.device_id == device_id)
                      .order_by(DeviceAssignment.started_at.desc(), DeviceAssignment.id.desc())).scalars().all()
    return [{"id": a.id, "department_id": a.department_id, "department": a.department.name if a.department else None,
             "user": (a.user.display_name or a.user.upn) if a.user else None, "user_upn": a.user.upn if a.user else None,
             "started_at": a.started_at, "ended_at": a.ended_at, "reason": a.reason, "actor": a.actor,
             "source": a.source} for a in rows]


@router.get("/{device_id}/history")
def device_history(device_id: int, limit: int = Query(200, le=1000), db: Session = Depends(get_db),
                   _: CurrentUser = Reader):
    changes = db.execute(select(InventoryChange).where(InventoryChange.device_id == device_id)
                         .order_by(InventoryChange.detected_at.desc(), InventoryChange.id.desc()).limit(limit)).scalars()
    events = db.execute(select(AuditEvent).where(and_(AuditEvent.entity_type == "device",
                                                      AuditEvent.entity_id == str(device_id)))
                        .order_by(AuditEvent.id.desc()).limit(limit)).scalars()
    return {
        "changes": [{"id": c.id, "type": c.change_type, "field": c.field, "old": c.old_value, "new": c.new_value,
                     "product_id": c.product_id, "product": c.product.name if c.product else None,
                     "source": c.source, "at": c.detected_at, "run_id": c.run_id} for c in changes],
        "audit": [{"id": e.id, "action": e.action, "actor": e.actor, "summary": e.summary, "at": e.occurred_at,
                   "before": e.before, "after": e.after} for e in events],
    }


@router.get("/{device_id}/observations")
def device_observations(device_id: int, db: Session = Depends(get_db), _: CurrentUser = Admin):
    """Último dato original recibido de cada fuente (diagnóstico)."""
    keys = db.execute(select(DeviceExternalId.value).where(DeviceExternalId.device_id == device_id,
                                                           DeviceExternalId.id_type == "intune_device_id")).scalars().all()
    obs = []
    for key in keys:
        row = db.execute(select(InventoryObservation, InventoryRun.trigger)
                         .join(InventoryRun, InventoryRun.id == InventoryObservation.run_id)
                         .where(InventoryObservation.entity == "device", InventoryObservation.external_key == key)
                         .order_by(InventoryObservation.id.desc()).limit(1)).first()
        if row:
            obs.append({"run_id": row[0].run_id, "observed_at": row[0].observed_at, "payload": row[0].payload})
    return obs


@router.get("/meta/types")
def device_types(db: Session = Depends(get_db), _: CurrentUser = Reader):
    return [{"id": t.id, "code": t.code, "name": t.name} for t in db.execute(select(DeviceType).order_by(DeviceType.id)).scalars()]


@router.get("/meta/statuses")
def device_statuses(_: CurrentUser = Reader):
    return list(DEVICE_STATUSES)
