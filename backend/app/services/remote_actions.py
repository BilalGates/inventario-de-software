"""Desinstalaciones con Intune Remediations y seguimiento de su resultado.

1. Un script por producto (deviceHealthScripts, beta), creado la primera vez y reutilizado; si el script
   generado cambia, se actualiza. Su id se guarda en AppSetting["intune.remediation_scripts"].
2. Se lanza bajo demanda en cada equipo (initiateOnDemandProactiveRemediation).
3. El worker lee deviceRunStates y cierra cada acción; si fue bien, pide a Intune que sincronice el equipo:
   la siguiente sincronización del inventario marca la instalación como retirada y cierra la alerta.
"""
from __future__ import annotations

import base64
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.base import ConnectorError
from app.db import utcnow
from app.models import AppSetting, Device, RemoteAction, SoftwareAlias, SoftwareInstallation, SoftwareProduct
from app.services import audit
from app.services import uninstall_script as scripts

log = logging.getLogger(__name__)
BETA = "/beta/deviceManagement"
SCRIPTS_KEY = "intune.remediation_scripts"
EXPIRE_AFTER = timedelta(hours=24)


def intune_id(device: Device) -> str | None:
    return next((e.value for e in device.external_ids if e.source == "intune" and e.id_type == "intune_device_id"), None)


def raw_names(db: Session, product: SoftwareProduct) -> list[str]:
    return list(db.execute(select(SoftwareAlias.raw_name).where(SoftwareAlias.product_id == product.id)).scalars())


def candidates(db: Session, product: SoftwareProduct, device_ids: list[int] | None = None) -> tuple[list[Device], list[dict]]:
    """Equipos donde el producto está instalado: los que admiten desinstalación remota y los que no (y por qué)."""
    query = (select(Device).join(SoftwareInstallation, SoftwareInstallation.device_id == Device.id)
             .where(SoftwareInstallation.product_id == product.id, SoftwareInstallation.present.is_(True))
             .distinct().order_by(Device.hostname))
    if device_ids:
        query = query.where(Device.id.in_(device_ids))
    ok, skipped = [], []
    for d in db.execute(query).scalars():
        if d.status == "retired":
            skipped.append({"id": d.id, "name": d.display_name, "reason": "Dado de baja"})
        elif not intune_id(d):
            skipped.append({"id": d.id, "name": d.display_name, "reason": "No está gestionado por Intune"})
        else:
            ok.append(d)
    return ok, skipped


def _b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def ensure_script(db: Session, client, product: SoftwareProduct, built: dict) -> str:
    """Id del script de Intune para el producto (lo crea o lo actualiza si el contenido cambió)."""
    row = db.get(AppSetting, SCRIPTS_KEY) or AppSetting(key=SCRIPTS_KEY, value={})
    known = dict(row.value or {})
    entry = known.get(str(product.id))
    body = {
        "displayName": f"Asserta Inventario · Desinstalar {product.name}"[:200],
        "description": "Generado por Asserta Inventario para desinstalar software no autorizado bajo demanda.",
        "publisher": "Asserta Inventario",
        "runAsAccount": "system", "runAs32Bit": False, "enforceSignatureCheck": False,
        "detectionScriptContent": _b64(built["detection"]), "remediationScriptContent": _b64(built["remediation"]),
        "roleScopeTagIds": ["0"],
    }
    if entry and entry.get("hash") == built["hash"]:
        return entry["id"]
    if entry:
        try:
            client.patch(f"{BETA}/deviceHealthScripts/{entry['id']}", json=body)
            script_id = entry["id"]
        except ConnectorError as exc:
            if exc.kind != "error":  # permisos, sesión…: se propaga
                raise
            script_id = client.post(f"{BETA}/deviceHealthScripts", json=body)["id"]  # borrado en Intune: se recrea
    else:
        script_id = client.post(f"{BETA}/deviceHealthScripts", json=body)["id"]
    known[str(product.id)] = {"id": script_id, "hash": built["hash"]}
    row.value, row.updated_by = known, "system:uninstall"
    db.add(row)
    return script_id


def launch(db: Session, client, product: SoftwareProduct, devices: list[Device], actor: str, reason: str) -> list[RemoteAction]:
    built = scripts.build(product, raw_names(db, product))
    script_id = ensure_script(db, client, product, built)
    actions = []
    for d in devices:
        action = RemoteAction(kind="uninstall", status="sent", device_id=d.id, product_id=product.id, requested_by=actor,
                              reason=reason, graph_ref=script_id, detail={"method": built["method"]})
        try:
            client.post(f"{BETA}/managedDevices/{intune_id(d)}/initiateOnDemandProactiveRemediation",
                        json={"scriptPolicyId": script_id})
        except ConnectorError as exc:
            if exc.kind in ("permission", "auth", "config"):
                raise
            action.status, action.finished_at = "failed", utcnow()
            action.detail = {**action.detail, "error": str(exc)}
        db.add(action)
        actions.append(action)
        audit.record(db, actor, "software.uninstall", "device", d.id,
                     f"Desinstalación remota de {product.name} en {d.display_name}: {reason}"
                     + ("" if action.status == "sent" else " (no se pudo lanzar)"))
    db.flush()
    return actions


def _when(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def poll(db: Session, client) -> dict:
    """Actualiza las desinstalaciones en curso con el estado que informa Intune."""
    now = utcnow()
    pending = db.execute(select(RemoteAction).where(RemoteAction.kind == "uninstall",
                                                    RemoteAction.status.in_(("sent", "running")))).scalars().all()
    summary = {"checked": len(pending), "finished": 0}
    by_script: dict[str, list[RemoteAction]] = {}
    for a in pending:
        if now - a.requested_at > EXPIRE_AFTER:
            a.status, a.finished_at = "expired", now
            a.detail = {**(a.detail or {}), "error": "Intune no informó del resultado en 24 horas."}
            summary["finished"] += 1
            continue
        by_script.setdefault(a.graph_ref or "", []).append(a)
    for script_id, actions in by_script.items():
        if not script_id:
            continue
        states = client.get(f"{BETA}/deviceHealthScripts/{script_id}/deviceRunStates",
                            {"$expand": "managedDevice($select=id)"}).get("value", [])
        by_device = {(s.get("managedDevice") or {}).get("id"): s for s in states}
        for a in actions:
            iid = intune_id(a.device) if a.device else None
            state = by_device.get(iid)
            updated = _when((state or {}).get("lastStateUpdateDateTime"))
            if not state or (updated and updated < a.requested_at - timedelta(minutes=5)):
                continue  # todavía no hay resultado de esta ejecución
            detection = (state.get("detectionState") or "").lower()
            remediation = (state.get("remediationState") or "").lower()
            output = state.get("remediationScriptError") or state.get("postRemediationDetectionScriptOutput") \
                or state.get("preRemediationDetectionScriptOutput") or ""
            if remediation == "success":
                status = scripts.interpret(state.get("remediationScriptOutput") or output)
            elif remediation in ("remediationfailed", "scripterror") or detection == "scripterror":
                status = "failed"
            elif detection == "success" and remediation in ("skipped", "unknown", ""):
                status = "succeeded"  # la detección no lo encontró: ya no estaba instalado
            else:
                a.status = "running"
                continue
            a.status, a.finished_at = status, now
            a.detail = {**(a.detail or {}), "detection": detection, "remediation": remediation, "output": output[:2000]}
            summary["finished"] += 1
            if status == "succeeded" and iid:
                try:  # que Intune vuelva a inventariar el equipo: la alerta se cerrará en la próxima sincronización
                    client.post(f"/v1.0/deviceManagement/managedDevices/{iid}/syncDevice")
                except ConnectorError as exc:
                    log.warning("No se pudo pedir la sincronización de %s: %s", iid, exc)
    db.flush()
    return summary


def retry(db: Session, client, action: RemoteAction, actor: str) -> RemoteAction:
    product = db.get(SoftwareProduct, action.product_id)
    scripts.check(product)
    if not action.device or not intune_id(action.device):
        raise scripts.NotUninstallable("El equipo ya no está gestionado por Intune.")
    return launch(db, client, product, [action.device], actor, action.reason or "Reintento")[0]


def has_pending(db: Session) -> bool:
    return db.execute(select(RemoteAction.id).where(RemoteAction.kind == "uninstall",
                                                    RemoteAction.status.in_(("sent", "running"))).limit(1)).first() is not None

