"""Contrato común de los conectores de inventario."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


@dataclass
class DeviceRecord:
    """Dispositivo tal como lo ve una fuente. None = la fuente no aporta el dato."""

    key: str  # clave estable dentro de la fuente (p.ej. id de Intune)
    ids: dict[str, str] = field(default_factory=dict)  # id_type -> valor
    hostname: str | None = None
    serial_number: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    os_name: str | None = None
    os_version: str | None = None
    device_type: str | None = None
    user_upn: str | None = None
    user_display_name: str | None = None
    ram_bytes: int | None = None
    storage_total_bytes: int | None = None
    storage_free_bytes: int | None = None
    mac_wifi: str | None = None
    mac_ethernet: str | None = None
    encrypted: bool | None = None
    compliance_state: str | None = None
    management_state: str | None = None
    ownership: str | None = None
    enrolled_at: datetime | None = None
    source_last_sync_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class InstallRecord:
    device_key: str
    name: str
    publisher: str | None = None
    version: str | None = None
    platform: str | None = None
    install_date: datetime | None = None
    source_app_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractResult:
    devices: list[DeviceRecord] = field(default_factory=list)
    installs: list[InstallRecord] = field(default_factory=list)
    # True solo si TODAS las consultas esenciales terminaron sin error.
    devices_complete: bool = False
    # Dispositivos (claves) cuyo software se ha leído íntegro: solo en ellos se infieren bajas.
    software_complete_for: set[str] = field(default_factory=set)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    @property
    def complete(self) -> bool:
        return self.devices_complete and not self.errors


class ConnectorError(Exception):
    """Error que impide continuar la extracción (credenciales, permisos, red...)."""

    def __init__(self, message: str, kind: str = "error"):
        super().__init__(message)
        self.kind = kind  # auth | permission | throttled | network | data | config


class Connector(Protocol):
    source_code: str

    def extract(self, params: dict[str, Any], log) -> ExtractResult: ...
