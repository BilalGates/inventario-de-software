"""Conector Microsoft Intune vía Microsoft Graph.

Dispositivos: GET /deviceManagement/managedDevices  (DeviceManagementManagedDevices.Read.All)
Software:     "Discovered apps" = /deviceManagement/detectedApps (mismo permiso).

Estrategias de software (parámetro `software_strategy`):
- "per_app" (por defecto): lista detectedApps y, por cada app, sus managedDevices. Es la
  técnica habitual de los scripts PowerShell de inventario. Solo hay completitud si TODAS
  las apps se leen sin error.
- "per_device": /managedDevices/{id}/detectedApps. Menos llamadas y completitud por equipo,
  pero debe validarse en el tenant (la relación puede venir vacía según versión de API).

Graph no ofrece consulta delta para managedDevices/detectedApps: cada ejecución es una
extracción completa (volumen bajo: decenas de equipos). La idempotencia la garantiza el
motor de sincronización, no la API.

"App inventory" (catálogo de propiedades / inventario de dispositivos de Intune) no se usa:
no se ha verificado un endpoint estable en Graph v1.0 para él. Ver docs/integrations.md.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.connectors.base import ConnectorError, DeviceRecord, ExtractResult, InstallRecord
from app.connectors.graph import GraphClient

DEVICE_FIELDS = [
    "id", "deviceName", "azureADDeviceId", "serialNumber", "manufacturer", "model", "operatingSystem",
    "osVersion", "userPrincipalName", "userDisplayName", "emailAddress", "enrolledDateTime",
    "lastSyncDateTime", "complianceState", "managementState", "isEncrypted", "totalStorageSpaceInBytes",
    "freeStorageSpaceInBytes", "physicalMemoryInBytes", "wiFiMacAddress", "ethernetMacAddress",
    "managedDeviceOwnerType", "managementAgent", "deviceEnrollmentType",
]


def _dt(value: Any) -> datetime | None:
    if not value or str(value).startswith("0001-01-01"):
        return None  # Graph usa 0001-01-01 como "sin dato"
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _positive(value: Any) -> int | None:
    try:
        num = int(value)
    except (TypeError, ValueError):
        return None
    return num if num > 0 else None  # Graph devuelve 0 cuando no informa el dato


def _text(value: Any) -> str | None:
    val = str(value).strip() if value is not None else ""
    return val if val and val.lower() not in {"unknown", "none", "null"} else None


def _device_type(os_name: str | None) -> str | None:
    os_l = (os_name or "").lower()
    if os_l in {"ios", "ipados", "android"}:
        return "mobile"
    if "server" in os_l:
        return "server"
    return None  # portátil/sobremesa no se deduce del SO: se clasifica manualmente


def map_device(d: dict) -> DeviceRecord:
    ids = {"intune_device_id": d["id"]}
    entra = _text(d.get("azureADDeviceId"))
    if entra and entra != "00000000-0000-0000-0000-000000000000":
        ids["entra_device_id"] = entra.lower()
    upn = _text(d.get("userPrincipalName"))
    return DeviceRecord(
        key=d["id"],
        ids=ids,
        hostname=_text(d.get("deviceName")),
        serial_number=_text(d.get("serialNumber")),
        manufacturer=_text(d.get("manufacturer")),
        model=_text(d.get("model")),
        os_name=_text(d.get("operatingSystem")),
        os_version=_text(d.get("osVersion")),
        device_type=_device_type(d.get("operatingSystem")),
        user_upn=upn.lower() if upn else None,
        user_display_name=_text(d.get("userDisplayName")),
        ram_bytes=_positive(d.get("physicalMemoryInBytes")),
        storage_total_bytes=_positive(d.get("totalStorageSpaceInBytes")),
        storage_free_bytes=_positive(d.get("freeStorageSpaceInBytes")),
        mac_wifi=_text(d.get("wiFiMacAddress")),
        mac_ethernet=_text(d.get("ethernetMacAddress")),
        encrypted=d.get("isEncrypted") if isinstance(d.get("isEncrypted"), bool) else None,
        compliance_state=_text(d.get("complianceState")),
        management_state=_text(d.get("managementState")),
        ownership=_text(d.get("managedDeviceOwnerType")),
        enrolled_at=_dt(d.get("enrolledDateTime")),
        source_last_sync_at=_dt(d.get("lastSyncDateTime")),
        raw={k: d.get(k) for k in DEVICE_FIELDS},
    )


class IntuneConnector:
    source_code = "intune"

    def __init__(self, client: GraphClient, api_version: str = "v1.0"):
        self.client = client
        self.api = f"/{api_version}"

    def extract(self, params: dict[str, Any], log) -> ExtractResult:
        result = ExtractResult()
        strategy = params.get("software_strategy", "per_app")

        # 1. Dispositivos (esencial: si falla, la ejecución falla).
        raw_devices = list(self.client.paginate(
            f"{self.api}/deviceManagement/managedDevices", {"$select": ",".join(DEVICE_FIELDS), "$top": "100"}
        ))
        result.devices = [map_device(d) for d in raw_devices]
        result.devices_complete = True
        log(f"Intune: {len(result.devices)} dispositivos administrados.")

        if params.get("fetch_hardware_details", True):
            self._hardware_details(result, log)

        # 2. Software.
        device_keys = {d.key for d in result.devices}
        if strategy == "per_device":
            self._software_per_device(result, device_keys, log)
        else:
            self._software_per_app(result, device_keys, log)

        result.stats.update(
            devices=len(result.devices),
            installs=len(result.installs),
            graph_requests=self.client.request_count,
            graph_throttled=self.client.throttled_count,
            software_strategy=strategy,
        )
        return result

    def _hardware_details(self, result: ExtractResult, log) -> None:
        """La lista no informa la RAM (devuelve 0); se pide por dispositivo. No es esencial."""
        missing = [d for d in result.devices if d.ram_bytes is None]
        failures = 0
        for dev in missing:
            try:
                body = self.client.get(
                    f"{self.api}/deviceManagement/managedDevices/{dev.key}", {"$select": "id,physicalMemoryInBytes"}
                )
                dev.ram_bytes = _positive(body.get("physicalMemoryInBytes"))
            except ConnectorError as exc:
                if exc.kind in ("auth", "permission"):
                    raise
                failures += 1
        if failures:
            result.warnings.append(f"No se pudo leer la RAM de {failures} dispositivos.")
            log(result.warnings[-1])

    def _software_per_app(self, result: ExtractResult, device_keys: set[str], log) -> None:
        apps = list(self.client.paginate(f"{self.api}/deviceManagement/detectedApps", {"$top": "500"}))
        log(f"Intune: {len(apps)} aplicaciones detectadas (nombre+versión).")
        failed = 0
        for app in apps:
            try:
                devices = list(self.client.paginate(
                    f"{self.api}/deviceManagement/detectedApps/{app['id']}/managedDevices",
                    {"$select": "id,deviceName"},
                ))
            except ConnectorError as exc:
                if exc.kind in ("auth", "permission"):
                    raise
                failed += 1
                result.errors.append(f"detectedApps/{app.get('id')}: {exc}")
                continue
            for dev in devices:
                result.installs.append(self._install(app, dev["id"]))
        if not failed:
            result.software_complete_for = set(device_keys)
        else:
            log(f"Intune: {failed} aplicaciones no se pudieron leer; no se inferirán desinstalaciones.")

    def _software_per_device(self, result: ExtractResult, device_keys: set[str], log) -> None:
        for key in sorted(device_keys):
            try:
                apps = list(self.client.paginate(f"{self.api}/deviceManagement/managedDevices/{key}/detectedApps"))
            except ConnectorError as exc:
                if exc.kind in ("auth", "permission"):
                    raise
                result.errors.append(f"managedDevices/{key}/detectedApps: {exc}")
                continue
            result.installs.extend(self._install(app, key) for app in apps)
            result.software_complete_for.add(key)

    @staticmethod
    def _install(app: dict, device_key: str) -> InstallRecord:
        return InstallRecord(
            device_key=device_key,
            name=str(app.get("displayName") or "").strip(),
            publisher=_text(app.get("publisher")),
            version=_text(app.get("version")),
            platform=_text(app.get("platform")),
            source_app_id=app.get("id"),
            raw={k: app.get(k) for k in ("id", "displayName", "version", "publisher", "platform", "sizeInByte")},
        )
