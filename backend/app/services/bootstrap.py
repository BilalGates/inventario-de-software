"""Datos de referencia mínimos (idempotente). No crea departamentos ni datos de negocio."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AppSetting, DeviceType, InventorySource

DEVICE_TYPES = [
    ("laptop", "Portátil"),
    ("desktop", "Sobremesa"),
    ("server", "Servidor"),
    ("mobile", "Dispositivo móvil"),
    ("peripheral", "Periférico / otro"),
]

SOURCES = [
    # code, name, kind, priority (menor = más fiable)
    ("intune", "Microsoft Intune", "api", 10),
    ("panda", "Panda Adaptive Defense", "file", 20),
    ("legacy", "Inventario anterior (PySide6)", "file", 50),
]

DEFAULT_SETTINGS = {
    # Programación mensual: día del mes y hora (UTC) en que el worker lanza las fuentes API
    # y, cuando terminan, genera el borrador del inventario mensual.
    "schedule.monthly": {"enabled": True, "day": 1, "hour": 6, "sources": ["intune"]},
    "alerts.stale_source_days": 3,
}


def ensure_reference_data(db: Session) -> None:
    existing_types = set(db.execute(select(DeviceType.code)).scalars())
    for code, name in DEVICE_TYPES:
        if code not in existing_types:
            db.add(DeviceType(code=code, name=name))
    existing_sources = set(db.execute(select(InventorySource.code)).scalars())
    for code, name, kind, priority in SOURCES:
        if code not in existing_sources:
            db.add(InventorySource(code=code, name=name, kind=kind, priority=priority, enabled=code != "legacy",
                                   config={"software_strategy": "per_app", "api_version": "v1.0"}
                                   if code == "intune" else {}))
    for key, value in DEFAULT_SETTINGS.items():
        if db.get(AppSetting, key) is None:
            db.add(AppSetting(key=key, value=value, updated_by="bootstrap"))
    db.flush()


def get_setting(db: Session, key: str):
    row = db.get(AppSetting, key)
    return row.value if row else DEFAULT_SETTINGS.get(key)
