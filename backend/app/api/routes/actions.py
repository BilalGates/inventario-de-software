"""Acciones sobre el software no autorizado: avisar al usuario por correo y desinstalar con Intune.

Siempre manuales: las lanza un técnico y quedan en auditoría y en «Acciones remotas».
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.common import Page, not_found, paginate
from app.api.routes.devices import _graph_http_error
from app.connectors.base import ConnectorError
from app.core.security import Admin, CurrentUser, Reader, Technician
from app.db import get_db
from app.models import AppSetting, RemoteAction, SoftwareProduct
from app.services import audit, graph_session, notify
from app.services import remote_actions as remote
from app.services import uninstall_script as scripts
from app.services.bootstrap import get_setting

router = APIRouter(prefix="/api", tags=["Acciones"])

MAIL_PERMISSION = "Mail.Send.Shared («Activar avisos por correo» en Sincronización)"
UNINSTALL_PERMISSION = ("DeviceManagementConfiguration.ReadWrite.All y "
                        "DeviceManagementManagedDevices.PrivilegedOperations.All")


def _client():
    if not graph_session.configured():
        raise HTTPException(409, "No hay conexión con Microsoft. Conéctese desde Sincronización.")
    return graph_session.make_client()


class Scope(BaseModel):
    alert_ids: list[int] | None = Field(None, max_length=1000)
    product_id: int | None = None
    device_ids: list[int] | None = Field(None, max_length=1000)

    @model_validator(mode="after")
    def _some(self):
        if not (self.alert_ids or self.product_id or self.device_ids):
            raise ValueError("Indique alertas, una aplicación o equipos")
        return self

    def as_kwargs(self) -> dict:
        return {"alert_ids": self.alert_ids, "product_id": self.product_id, "device_ids": self.device_ids}


class NotifyIn(Scope):
    subject: str | None = Field(None, max_length=300)
    body: str | None = Field(None, max_length=10000)


# --------------------------------------------------------------------------- avisos por correo
@router.post("/notifications/preview")
def notification_preview(body: Scope, db: Session = Depends(get_db), _: CurrentUser = Technician):
    return notify.preview(db, **body.as_kwargs())


@router.post("/notifications/send")
def notification_send(body: NotifyIn, db: Session = Depends(get_db), user: CurrentUser = Technician):
    client = _client()
    try:
        result = notify.send(db, client, user.upn, body.subject, body.body, **body.as_kwargs())
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ConnectorError as exc:
        db.rollback()
        raise _graph_http_error(exc, MAIL_PERMISSION) from exc
    db.commit()
    return result


@router.post("/notifications/test")
def notification_test(db: Session = Depends(get_db), user: CurrentUser = Technician):
    client = _client()
    try:
        notify.send_test(db, client, user.upn, user.upn)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ConnectorError as exc:
        raise _graph_http_error(exc, MAIL_PERMISSION) from exc
    db.commit()
    return {"sent_to": user.upn}


class NotifySettings(BaseModel):
    sender: str = Field("", max_length=255, pattern=r"^$|^[^\s@]+@[^\s@]+\.[^\s@]+$")
    cc: str = Field("", max_length=500)
    subject: str = Field(..., min_length=3, max_length=300)
    body: str = Field(..., min_length=10, max_length=10000)


@router.put("/settings/notify")
def set_notify_settings(body: NotifySettings, db: Session = Depends(get_db), user: CurrentUser = Admin):
    values = {"notify.sender": body.sender.strip().lower(), "notify.cc": body.cc.strip(),
              "notify.template": {"subject": body.subject, "body": body.body}}
    for key, value in values.items():
        row = db.get(AppSetting, key) or AppSetting(key=key)
        before = row.value
        row.value, row.updated_by = value, user.upn
        db.add(row)
        audit.record(db, user.upn, "settings.notify", "app_setting", key, "Avisos por correo",
                     before={"value": before}, after={"value": value})
    db.commit()
    return {"sender": values["notify.sender"], "cc": values["notify.cc"], "template": values["notify.template"]}


# --------------------------------------------------------------------------- desinstalaciones
class UninstallScope(BaseModel):
    product_id: int
    device_ids: list[int] | None = Field(None, max_length=1000)


class UninstallIn(UninstallScope):
    device_ids: list[int] = Field(..., min_length=1, max_length=1000)
    reason: str = Field(..., min_length=3, max_length=1000)
    notify_first: bool = True


def _product(db: Session, product_id: int) -> SoftwareProduct:
    p = db.get(SoftwareProduct, product_id)
    if p is None or p.merged_into_id:
        raise not_found("Producto")
    return p


@router.post("/uninstalls/preview")
def uninstall_preview(body: UninstallScope, db: Session = Depends(get_db), _: CurrentUser = Technician):
    """Simulación: qué equipos admiten la desinstalación, con qué método y el script. No cambia nada."""
    p = _product(db, body.product_id)
    try:
        built = scripts.build(p, remote.raw_names(db, p))
    except scripts.NotUninstallable as exc:
        return {"product": {"id": p.id, "name": p.name}, "blocked": str(exc), "devices": [], "skipped": []}
    ok, skipped = remote.candidates(db, p, body.device_ids)
    recipients, no_user = notify.collect(db, product_id=p.id, device_ids=[d.id for d in ok] or [0])
    return {
        "product": {"id": p.id, "name": p.name}, "blocked": None, "method": built["method"], "names": built["names"],
        "devices": [{"id": d.id, "name": d.display_name,
                     "user": d.primary_user.upn if d.primary_user else None} for d in ok],
        "skipped": skipped, "recipients": len(recipients), "no_user": no_user,
        "detection": built["detection"], "remediation": built["remediation"],
        "connected": graph_session.configured(),
    }


@router.post("/uninstalls")
def uninstall(body: UninstallIn, db: Session = Depends(get_db), user: CurrentUser = Technician):
    p = _product(db, body.product_id)
    try:
        scripts.check(p)
    except scripts.NotUninstallable as exc:
        raise HTTPException(422, str(exc)) from exc
    devices, _ = remote.candidates(db, p, body.device_ids)
    if not devices:
        raise HTTPException(422, "Ninguno de los equipos indicados admite la desinstalación remota.")
    client = _client()
    notified = None
    if body.notify_first:
        try:
            notified = notify.send(db, client, user.upn, product_id=p.id, device_ids=[d.id for d in devices])
        except ValueError as exc:
            raise HTTPException(409, f"{exc} (o desmarque «Avisar antes al usuario»).") from exc
        except ConnectorError as exc:
            db.rollback()
            raise _graph_http_error(exc, MAIL_PERMISSION) from exc
    try:
        actions = remote.launch(db, client, p, devices, user.upn, body.reason)
    except ConnectorError as exc:
        db.rollback()
        raise _graph_http_error(exc, UNINSTALL_PERMISSION) from exc
    db.commit()
    return {"launched": sum(a.status == "sent" for a in actions), "failed": sum(a.status == "failed" for a in actions),
            "notified": notified}


# --------------------------------------------------------------------------- seguimiento
def serialize(a: RemoteAction) -> dict:
    return {"id": a.id, "kind": a.kind, "status": a.status, "device_id": a.device_id,
            "device": a.device.display_name if a.device else None, "product_id": a.product_id,
            "product": a.product.name if a.product else None, "alert_id": a.alert_id, "recipient": a.recipient,
            "requested_by": a.requested_by, "requested_at": a.requested_at, "finished_at": a.finished_at,
            "reason": a.reason, "detail": a.detail or {}}


@router.get("/remote-actions")
def list_remote_actions(page: Page = Depends(), kind: str | None = None, status: str | None = None,
                        product_id: int | None = None, device_id: int | None = None,
                        db: Session = Depends(get_db), _: CurrentUser = Reader):
    query = select(RemoteAction)
    if kind:
        query = query.where(RemoteAction.kind.in_(kind.split(",")))
    if status:
        query = query.where(RemoteAction.status.in_(status.split(",")))
    if product_id:
        query = query.where(RemoteAction.product_id == product_id)
    if device_id:
        query = query.where(RemoteAction.device_id == device_id)
    rows, total = paginate(db, query, page, {"requested_at": RemoteAction.requested_at}, RemoteAction.id.desc())
    return {"total": total, "items": [serialize(r[0]) for r in rows]}


@router.post("/remote-actions/{action_id}/retry")
def retry_remote_action(action_id: int, db: Session = Depends(get_db), user: CurrentUser = Technician):
    a = db.get(RemoteAction, action_id)
    if a is None:
        raise not_found("Acción")
    if a.kind != "uninstall" or a.status not in ("failed", "expired", "manual_required"):
        raise HTTPException(409, "Solo se reintentan desinstalaciones fallidas o caducadas.")
    client = _client()
    try:
        new = remote.retry(db, client, a, user.upn)
    except scripts.NotUninstallable as exc:
        raise HTTPException(422, str(exc)) from exc
    except ConnectorError as exc:
        db.rollback()
        raise _graph_http_error(exc, UNINSTALL_PERMISSION) from exc
    db.commit()
    return serialize(new)


@router.get("/settings/notify")
def get_notify_settings(db: Session = Depends(get_db), _: CurrentUser = Reader):
    return {"sender": get_setting(db, "notify.sender") or "", "cc": get_setting(db, "notify.cc") or "",
            "template": notify.template(db)}
