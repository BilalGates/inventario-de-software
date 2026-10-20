"""Departamentos y usuarios."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.common import export_response, not_found
from app.core.security import Admin, CurrentUser, Reader, Technician
from app.db import get_db, utcnow
from app.models import (
    AuditEvent,
    Department,
    Device,
    DeviceAssignment,
    SoftwareInstallation,
    SoftwareProduct,
    User,
)
from app.services import audit

router = APIRouter(prefix="/api", tags=["Organización"])

DEPT_FIELDS = ["code", "name", "description", "manager_id", "cost_center", "attributes", "active"]


def _slug(name: str) -> str:
    import unicodedata

    val = unicodedata.normalize("NFKD", name)
    val = "".join(c for c in val if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "_", val).strip("_")[:50] or "dept"


def _dept(d: Department, stats: dict | None = None) -> dict:
    return {"id": d.id, "code": d.code, "name": d.name, "description": d.description, "manager_id": d.manager_id,
            "manager": (d.manager.display_name or d.manager.upn) if d.manager else None,
            "cost_center": d.cost_center, "attributes": d.attributes or {}, "active": d.active,
            "created_at": d.created_at, "updated_at": d.updated_at, **(stats or {})}


@router.get("/departments")
def list_departments(include_inactive: bool = True, db: Session = Depends(get_db), _: CurrentUser = Reader):
    query = select(Department).order_by(Department.name)
    if not include_inactive:
        query = query.where(Department.active.is_(True))
    depts = db.execute(query).scalars().all()
    dev_counts = dict(db.execute(select(Device.department_id, func.count()).where(Device.status != "retired")
                                 .group_by(Device.department_id)).all())
    user_counts = dict(db.execute(select(User.department_id, func.count()).where(User.active.is_(True))
                                  .group_by(User.department_id)).all())
    sw_counts = dict(db.execute(
        select(Device.department_id, func.count(func.distinct(SoftwareInstallation.product_id)))
        .join(Device, Device.id == SoftwareInstallation.device_id)
        .where(SoftwareInstallation.present.is_(True), Device.status != "retired").group_by(Device.department_id)
    ).all())
    items = [_dept(d, {"devices": dev_counts.get(d.id, 0), "users": user_counts.get(d.id, 0),
                       "software": sw_counts.get(d.id, 0)}) for d in depts]
    return {"items": items, "unassigned_devices": dev_counts.get(None, 0)}


class DepartmentIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    code: str | None = Field(None, max_length=50, pattern=r"^[a-z0-9_]+$")
    description: str | None = Field(None, max_length=2000)
    manager_upn: str | None = Field(None, max_length=255)
    cost_center: str | None = Field(None, max_length=50)
    attributes: dict[str, str] | None = None


class DepartmentPatch(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=120)
    description: str | None = Field(None, max_length=2000)
    manager_upn: str | None = Field(None, max_length=255)
    cost_center: str | None = Field(None, max_length=50)
    attributes: dict[str, str] | None = None
    active: bool | None = None


def _manager_id(db: Session, upn: str | None) -> int | None:
    if not upn:
        return None
    user = db.execute(select(User).where(User.upn == upn.lower())).scalar_one_or_none()
    if user is None:
        user = User(upn=upn.lower(), source="manual")
        db.add(user)
        db.flush()
    return user.id


@router.post("/departments", status_code=201)
def create_department(body: DepartmentIn, db: Session = Depends(get_db), user: CurrentUser = Technician):
    if db.execute(select(Department).where(func.lower(Department.name) == body.name.strip().lower())).first():
        raise HTTPException(409, "Ya existe un departamento con ese nombre")
    code = body.code or _slug(body.name)
    if db.execute(select(Department).where(Department.code == code)).first():
        raise HTTPException(409, f"El código '{code}' ya existe")
    dept = Department(code=code, name=body.name.strip(), description=body.description,
                      manager_id=_manager_id(db, body.manager_upn), cost_center=body.cost_center,
                      attributes=body.attributes, active=True)
    db.add(dept)
    db.flush()
    audit.record(db, user.upn, "department.create", "department", dept.id, f"Alta de {dept.name}",
                 after=audit.snapshot(dept, DEPT_FIELDS))
    db.commit()
    return _dept(dept)


@router.patch("/departments/{dept_id}")
def update_department(dept_id: int, body: DepartmentPatch, db: Session = Depends(get_db),
                      user: CurrentUser = Technician):
    dept = db.get(Department, dept_id)
    if dept is None:
        raise not_found("Departamento")
    before = audit.snapshot(dept, DEPT_FIELDS)
    data = body.model_dump(exclude_unset=True)
    if "name" in data and data["name"].strip().lower() != dept.name.lower():
        if db.execute(select(Department).where(func.lower(Department.name) == data["name"].strip().lower())).first():
            raise HTTPException(409, "Ya existe un departamento con ese nombre")
    if data.get("active") is False:
        in_use = db.execute(select(func.count()).select_from(Device).where(
            Device.department_id == dept.id, Device.status != "retired")).scalar()
        if in_use:
            raise HTTPException(409, f"No se puede desactivar: tiene {in_use} dispositivos asignados. Muévalos antes.")
    if "manager_upn" in data:
        dept.manager_id = _manager_id(db, data.pop("manager_upn"))
    for key, value in data.items():
        setattr(dept, key, value.strip() if isinstance(value, str) else value)
    audit.record(db, user.upn, "department.update", "department", dept.id, f"Edición de {dept.name}",
                 before=before, after=audit.snapshot(dept, DEPT_FIELDS))
    db.commit()
    return _dept(dept)


@router.get("/departments/{dept_id}")
def department_detail(dept_id: int, db: Session = Depends(get_db), _: CurrentUser = Reader):
    dept = db.get(Department, dept_id)
    if dept is None:
        raise not_found("Departamento")
    users = db.execute(select(User).where(User.department_id == dept_id).order_by(User.display_name)).scalars().all()
    top = db.execute(
        select(SoftwareProduct.id, SoftwareProduct.name, SoftwareProduct.authorization_status,
               func.count(func.distinct(SoftwareInstallation.device_id)).label("n"))
        .join(SoftwareInstallation, SoftwareInstallation.product_id == SoftwareProduct.id)
        .join(Device, Device.id == SoftwareInstallation.device_id)
        .where(Device.department_id == dept_id, Device.status != "retired", SoftwareInstallation.present.is_(True),
               SoftwareProduct.is_relevant.is_(True))
        .group_by(SoftwareProduct.id, SoftwareProduct.name, SoftwareProduct.authorization_status)
        .order_by(func.count(func.distinct(SoftwareInstallation.device_id)).desc()).limit(200)
    ).all()
    moves = db.execute(select(DeviceAssignment, Device).join(Device, Device.id == DeviceAssignment.device_id)
                       .where(DeviceAssignment.department_id == dept_id)
                       .order_by(DeviceAssignment.started_at.desc()).limit(50)).all()
    history = db.execute(select(AuditEvent).where(AuditEvent.entity_type == "department",
                                                  AuditEvent.entity_id == str(dept_id))
                         .order_by(AuditEvent.id.desc()).limit(50)).scalars().all()
    return {
        **_dept(dept),
        "users": [{"id": u.id, "upn": u.upn, "display_name": u.display_name} for u in users],
        "software": [{"product_id": r.id, "name": r.name, "authorization_status": r.authorization_status,
                      "devices": r.n} for r in top],
        "movements": [{"device_id": m.device_id, "device": dev.display_name, "started_at": m.started_at,
                       "ended_at": m.ended_at, "reason": m.reason, "actor": m.actor} for m, dev in moves],
        "history": [{"action": e.action, "actor": e.actor, "summary": e.summary, "at": e.occurred_at,
                     "before": e.before, "after": e.after} for e in history],
    }


# ------------------------------------------------------------------------- usuarios
@router.get("/users")
def list_users(q: str | None = None, app_only: bool = False, db: Session = Depends(get_db), _: CurrentUser = Reader):
    query = select(User).order_by(User.display_name, User.upn)
    if q:
        like = f"%{q}%"
        query = query.where((User.upn.ilike(like)) | (User.display_name.ilike(like)))
    if app_only:
        query = query.where(User.role.is_not(None))
    counts = dict(db.execute(select(Device.primary_user_id, func.count()).where(Device.status != "retired")
                             .group_by(Device.primary_user_id)).all())
    return [{"id": u.id, "upn": u.upn, "display_name": u.display_name, "department_id": u.department_id,
             "department": u.department.name if u.department else None, "role": u.role, "active": u.active,
             "source": u.source, "last_login_at": u.last_login_at, "devices": counts.get(u.id, 0)}
            for u in db.execute(query.limit(1000)).scalars()]


@router.get("/users/export")
def export_users(format: str = Query("xlsx", pattern="^(csv|xlsx)$"), db: Session = Depends(get_db),
                 user: CurrentUser = Reader):
    """Usuarios con sus equipos asignados (usuario principal), uno por fila de usuario."""
    devices: dict[int, list[Device]] = {}
    for d in db.execute(select(Device).where(Device.status != "retired", Device.primary_user_id.is_not(None))
                        .order_by(Device.hostname)).scalars():
        devices.setdefault(d.primary_user_id, []).append(d)
    rows = []
    for u in db.execute(select(User).order_by(User.display_name, User.upn)).scalars():
        own = devices.get(u.id, [])
        rows.append({
            # Sin departamento propio se usa el de sus equipos (es lo habitual con datos de Intune).
            "display_name": u.display_name, "upn": u.upn,
            "department": u.department.name if u.department else
            ", ".join(sorted({d.department.name for d in own if d.department})) or None,
            "active": u.active, "source": u.source, "devices": len(own),
            "device_names": ", ".join(d.display_name or "" for d in own),
            "models": ", ".join(sorted({f"{d.manufacturer or ''} {d.model or ''}".strip() for d in own} - {""})),
            "serials": ", ".join(d.serial_number for d in own if d.serial_number),
            "last_seen_at": max((d.last_seen_at for d in own if d.last_seen_at), default=None),
        })
    audit.record(db, user.upn, "export.users", "user", None, f"Exportación de {len(rows)} usuarios ({format})")
    db.commit()
    cols = [("display_name", "Usuario"), ("upn", "UPN"), ("department", "Departamento"), ("active", "Activo"),
            ("devices", "Nº equipos"), ("device_names", "Equipos"), ("models", "Modelos"), ("serials", "Nº serie"),
            ("last_seen_at", "Última observación de sus equipos"), ("source", "Origen")]
    return export_response(rows, cols, f"usuarios_{utcnow():%Y%m%d}", format)


class UserPatch(BaseModel):
    department_id: int | None = None
    display_name: str | None = Field(None, max_length=200)
    active: bool | None = None


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: UserPatch, db: Session = Depends(get_db), actor: CurrentUser = Technician):
    u = db.get(User, user_id)
    if u is None:
        raise not_found("Usuario")
    before = audit.snapshot(u, ["department_id", "display_name", "active"])
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(u, key, value)
    audit.record(db, actor.upn, "user.update", "user", u.id, f"Edición de {u.upn}", before=before,
                 after=audit.snapshot(u, ["department_id", "display_name", "active"]))
    db.commit()
    return {"ok": True}


@router.get("/me")
def me(user: CurrentUser = Reader):
    return {"upn": user.upn, "name": user.name, "role": user.role,
            "permissions": {"read": True, "write": user.can("technician"), "admin": user.can("admin")}}


@router.get("/admin/roles")
def roles_info(_: CurrentUser = Admin):
    """Los roles se asignan en Entra ID (app roles), no en esta aplicación."""
    from app.core.config import get_settings

    s = get_settings()
    return {"mode": s.auth_mode, "mapping": {"admin": s.entra_role_admin, "technician": s.entra_role_technician,
                                             "auditor": s.entra_role_auditor}}
