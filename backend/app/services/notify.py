"""Avisos por correo al usuario de un equipo con software no autorizado.

Un correo por persona con todos sus programas no autorizados (de todos sus equipos), con el motivo y la
alternativa corporativa que dejó la política en las notas del producto. Siempre lo pide un técnico.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.base import ConnectorError
from app.connectors.mailer import send_mail
from app.db import utcnow
from app.models import Alert, Device, RemoteAction
from app.services import audit
from app.services.bootstrap import get_setting

DEFAULT_TEMPLATE = {
    "subject": "Software no autorizado en tu equipo",
    "body": ("Hola {nombre}:\n\n"
             "En el inventario de equipos de Asserta hemos detectado en {equipo} software que no está autorizado "
             "por la política de uso de software de la empresa:\n\n"
             "{programas}\n\n"
             "Por favor, desinstálalo o contacta con IT si lo necesitas para tu trabajo, para valorar una "
             "excepción. Si no se retira, IT podrá desinstalarlo de forma remota.\n\n"
             "Gracias,\nEquipo de IT"),
}
FIELDS = ("nombre", "equipo", "programas", "fecha")


def policy_note(notes: str | None, label: str) -> str | None:
    """Un campo («Motivo», «Alternativa»…) de la nota que dejó la política en el producto."""
    m = re.search(rf"{label}:\s*([^·\n]+)", notes or "")
    return m.group(1).strip() if m else None


@dataclass
class Program:
    product_id: int
    name: str
    reason: str | None
    alternative: str | None
    devices: list[str] = field(default_factory=list)


@dataclass
class Recipient:
    upn: str
    name: str
    devices: list[str] = field(default_factory=list)
    programs: dict[int, Program] = field(default_factory=dict)
    alerts: list[Alert] = field(default_factory=list)


def collect(db: Session, alert_ids: list[int] | None = None, product_id: int | None = None,
            device_ids: list[int] | None = None) -> tuple[list[Recipient], list[str]]:
    """Destinatarios (con sus programas) de las alertas abiertas de software no autorizado indicadas.

    Devuelve también los equipos sin usuario asignado, a los que no se puede avisar."""
    query = (select(Alert).join(Device, Device.id == Alert.device_id)
             .where(Alert.alert_type == "unauthorized_software", Alert.status != "resolved",
                    Alert.product_id.is_not(None), Device.status != "retired"))
    if alert_ids:
        query = query.where(Alert.id.in_(alert_ids))
    if product_id:
        query = query.where(Alert.product_id == product_id)
    if device_ids:
        query = query.where(Alert.device_id.in_(device_ids))
    recipients: dict[str, Recipient] = {}
    no_user: list[str] = []
    for a in db.execute(query.order_by(Alert.id)).scalars():
        d, p = a.device, a.product
        owner = d.primary_user
        if owner is None or not owner.upn:
            if d.display_name not in no_user:
                no_user.append(d.display_name)
            continue
        r = recipients.setdefault(owner.upn, Recipient(owner.upn, owner.display_name or owner.upn))
        if d.display_name not in r.devices:
            r.devices.append(d.display_name)
        prog = r.programs.setdefault(p.id, Program(p.id, p.name, policy_note(p.notes, "Motivo"),
                                                   policy_note(p.notes, "Alternativa")))
        if d.display_name not in prog.devices:
            prog.devices.append(d.display_name)
        r.alerts.append(a)
    return list(recipients.values()), no_user


class _Safe(dict):
    def __missing__(self, key):  # un campo desconocido en la plantilla se deja tal cual
        return "{" + key + "}"


def render(template: dict, r: Recipient) -> tuple[str, str]:
    several = len(r.devices) > 1
    lines = []
    for prog in r.programs.values():
        line = f"• {prog.name}" + (f" (en {', '.join(prog.devices)})" if several else "")
        if prog.reason:
            line += f"\n  Motivo: {prog.reason}"
        if prog.alternative:
            line += f"\n  Alternativa corporativa: {prog.alternative}"
        lines.append(line)
    values = _Safe(nombre=r.name.split(" ")[0] if " " in r.name and "@" not in r.name else r.name,
                   equipo=("tus equipos " if several else "tu equipo ") + ", ".join(r.devices),
                   programas="\n".join(lines), fecha=f"{utcnow():%d/%m/%Y}")
    subject = (template.get("subject") or DEFAULT_TEMPLATE["subject"]).format_map(values)
    body = (template.get("body") or DEFAULT_TEMPLATE["body"]).format_map(values)
    return subject, body


def template(db: Session) -> dict:
    return {**DEFAULT_TEMPLATE, **(get_setting(db, "notify.template") or {})}


def preview(db: Session, **scope) -> dict:
    recipients, no_user = collect(db, **scope)
    tpl = template(db)
    out = []
    for r in recipients:
        subject, body = render(tpl, r)
        out.append({"upn": r.upn, "name": r.name, "devices": r.devices, "programs": [p.name for p in r.programs.values()],
                    "alerts": len(r.alerts), "subject": subject, "body": body})
    return {"sender": get_setting(db, "notify.sender") or None, "cc": get_setting(db, "notify.cc") or None,
            "template": tpl, "recipients": out, "no_user": no_user}


def send(db: Session, client, actor: str, subject: str | None = None, body: str | None = None, **scope) -> dict:
    """Envía un correo por destinatario. `subject`/`body` (opcionales) son la plantilla editada por el técnico."""
    sender = get_setting(db, "notify.sender")
    if not sender:
        raise ValueError("Configure el buzón remitente de los avisos en Configuración.")
    cc = get_setting(db, "notify.cc") or None
    tpl = {**template(db), **({"subject": subject} if subject else {}), **({"body": body} if body else {})}
    recipients, no_user = collect(db, **scope)
    sent = failed = 0
    errors: list[str] = []
    for r in recipients:
        subj, text = render(tpl, r)
        status, error = "sent", None
        try:
            send_mail(client, sender, r.upn, subj, text, cc)
            sent += 1
        except ConnectorError as exc:
            if exc.kind in ("permission", "auth", "config"):
                raise  # sin permiso o sin sesión: no tiene sentido seguir con el resto
            status, error = "failed", str(exc)
            failed += 1
            errors.append(f"{r.upn}: {exc}")
        for a in r.alerts:
            db.add(RemoteAction(kind="notify", status=status, device_id=a.device_id, product_id=a.product_id,
                                alert_id=a.id, recipient=r.upn, requested_by=actor, finished_at=utcnow(),
                                detail={"subject": subj, **({"error": error} if error else {})}))
        audit.record(db, actor, "notify.unauthorized_software", "user", r.upn,
                     f"Aviso a {r.upn}: {', '.join(p.name for p in r.programs.values())}"
                     + ("" if status == "sent" else f" (FALLÓ: {error})"))
    db.flush()
    return {"sent": sent, "failed": failed, "errors": errors, "no_user": no_user}


def send_test(db: Session, client, actor: str, to: str) -> None:
    sender = get_setting(db, "notify.sender")
    if not sender:
        raise ValueError("Configure el buzón remitente de los avisos en Configuración.")
    sample = Recipient(to, to.split("@")[0], ["EQUIPO-DE-PRUEBA"],
                       {0: Program(0, "Programa de ejemplo", "Motivo indicado en la política.", "Alternativa corporativa",
                                   ["EQUIPO-DE-PRUEBA"])})
    subject, body = render(template(db), sample)
    send_mail(client, sender, to, f"[Prueba] {subject}", body, None)
    audit.record(db, actor, "notify.test", "user", to, f"Correo de prueba de avisos enviado a {to}")
