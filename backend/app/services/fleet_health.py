"""Estado de salud de cada equipo: la misma leyenda en el Panel, Dispositivos y Departamentos.

- infra: servidores, red y periféricos (inventario manual, no cuentan como puestos de trabajo).
- ok: sin incidencias.
- alert: tiene software no autorizado (alerta abierta).
- nc: no conforme en Intune.
- alertnc: ambas cosas.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Alert, Device

INFRA_TYPES = {"server", "peripheral"}
# Igual que `isFailing` del frontend: estados de Intune que explican un «No conforme».
FAILING = {"noncompliant", "error", "conflict", "ingraceperiod"}


def unauthorized_devices(db: Session) -> set[int]:
    """Equipos con alguna alerta abierta de software no autorizado."""
    return {d for d in db.execute(select(Alert.device_id).where(
        Alert.alert_type == "unauthorized_software", Alert.status != "resolved",
        Alert.device_id.is_not(None)).distinct()).scalars()}


def type_code(device: Device) -> str | None:
    return device.device_type.code if device.device_type else None


def state(device: Device, unauthorized: set[int]) -> str:
    if type_code(device) in INFRA_TYPES:
        return "infra"
    nc = (device.compliance_state or "").lower() in FAILING
    bad = device.id in unauthorized
    return "alertnc" if bad and nc else "alert" if bad else "nc" if nc else "ok"


def summarize(states: list[str]) -> dict:
    """Recuento para la cifra principal del Panel: solo puestos de trabajo (sin infraestructura)."""
    work = [s for s in states if s != "infra"]
    return {"workstations": len(work), "clean": work.count("ok"),
            "unauthorized": sum(s in ("alert", "alertnc") for s in work),
            "noncompliant": sum(s in ("nc", "alertnc") for s in work),
            "both": work.count("alertnc"), "infra": len(states) - len(work)}
