"""Conector Microsoft Intune vía Microsoft Graph.

Dispositivos: GET /deviceManagement/managedDevices  (DeviceManagementManagedDevices.Read.All)
Software:     "Discovered apps" = /deviceManagement/detectedApps (mismo permiso).

Estrategias de software (parámetro `software_strategy`):
- "per_app": lista detectedApps y, por cada app, sus managedDevices. Es la
  técnica habitual de los scripts PowerShell de inventario. Solo hay completitud si TODAS
  las apps se leen sin error.
- "per_device" (por defecto en el servicio): beta managedDevices/{id}?$expand=detectedApps. Una
  llamada por equipo (segundos en lugar de ~24 min) y completitud por equipo. En v1.0 la
  relación managedDevices/{id}/detectedApps responde 400 (verificado en el tenant).

Graph no ofrece consulta delta para managedDevices/detectedApps: cada ejecución es una
extracción completa (volumen bajo: decenas de equipos). La idempotencia la garantiza el
motor de sincronización, no la API.

"App inventory" (catálogo de propiedades / inventario de dispositivos de Intune) no se usa:
no se ha verificado un endpoint estable en Graph v1.0 para él. Ver docs/integrations.md.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.connectors.base import ConnectorError, DeviceRecord, ExtractResult, InstallRecord
from app.connectors.graph import GraphClient
from app.connectors.intune_compliance import DEVICE_FAILING, fetch_compliance

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


def _key(name: Any) -> str:
    return str(name or "").strip().lower()


# Portátil/sobremesa por familia de modelo (Intune no lo informa en v1.0). Lo que no encaja queda
# sin clasificar: nunca se inventa, y una clasificación manual no se pisa (ver apply_record).
_LAPTOP = re.compile(r"latitude|xps|inspiron|2n1|2-in-1|dell pro (14|16)|dell (14|16) |\bgram\b|\d{2}z9\dq|"
                     r"thinkpad|elitebook|probook|zbook|surface (laptop|pro|book)|macbook")
_DESKTOP = re.compile(r"optiplex|precision (tower|t\d)|precision \d{4} tower|elitedesk|prodesk|thinkcentre|"
                      r"vostro \d+ (tower|small)|imac|mac mini|dell pro (slim|tower|micro)")


def _device_type(os_name: str | None, model: str | None = None) -> str | None:
    os_l = (os_name or "").lower()
    if os_l in {"ios", "ipados", "android"}:
        return "mobile"
    if "server" in os_l:
        return "server"
    model_l = (model or "").lower()
    if _DESKTOP.search(model_l):
        return "desktop"
    if _LAPTOP.search(model_l):
        return "laptop"
    return None


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
        device_type=_device_type(d.get("operatingSystem"), d.get("model")),
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
        if params.get("fetch_compliance_details", True):
            self._compliance_details(result, log)

        # 2. Software.
        device_keys = {d.key for d in result.devices}
        if strategy == "per_device":
            errors_before = len(result.errors)
            self._software_per_device(result, device_keys, log)
            if device_keys and len(result.errors) - errors_before == len(device_keys):
                # La ruta beta falla en todos los equipos (p. ej. Microsoft la retira): se repite con
                # la estrategia v1.0 en esta misma ejecución en lugar de quedarse sin software.
                del result.errors[errors_before:]
                result.warnings.append("La lectura de software por equipo (beta) falló en todos los equipos; "
                                       "se ha usado la estrategia por aplicación (v1.0), más lenta.")
                log(result.warnings[-1])
                result.stats["software_strategy_fallback"] = True
                strategy = "per_app"
                self._software_per_app(result, device_keys, log)
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

    def _compliance_details(self, result: ExtractResult, log) -> None:
        """Motivo de la no conformidad, solo en los equipos que fallan (pocas llamadas). No es esencial:
        sin permiso o sin sesión válida se avisa y se sigue con el software."""
        failing = [d for d in result.devices if (d.compliance_state or "").lower() in DEVICE_FAILING]
        for dev in result.devices:
            if (dev.compliance_state or "").lower() not in DEVICE_FAILING:
                dev.compliance_details = {"policies": []}  # ya no falla: se limpia el motivo anterior
        failures = 0
        for dev in failing:
            try:
                dev.compliance_details = fetch_compliance(self.client, dev.key, self.api.strip("/"))
                dev.compliance_checked = True
            except ConnectorError as exc:
                if exc.kind in ("permission", "auth"):
                    result.warnings.append("No se pudo leer el detalle de conformidad (falta el permiso "
                                           "DeviceManagementConfiguration.Read.All o la sesión no es válida); "
                                           "vuelva a conectar Intune.")
                    log(result.warnings[-1])
                    return
                failures += 1
        if failing:
            log(f"Intune: detalle de conformidad de {len(failing) - failures}/{len(failing)} equipos no conformes.")
        if failures:
            result.warnings.append(f"No se pudo leer el detalle de conformidad de {failures} dispositivos.")

    def _software_per_app(self, result: ExtractResult, device_keys: set[str], log) -> None:
        apps = list(self.client.paginate(f"{self.api}/deviceManagement/detectedApps", {"$top": "500"}))
        # Las apps sin dispositivos no aportan instalaciones: no se consultan (ahorra cientos de llamadas).
        apps = [a for a in apps if a.get("deviceCount") != 0]
        log(f"Intune: {len(apps)} aplicaciones detectadas con dispositivos (nombre+versión).")
        # Una petición por app y en serie: con $batch Intune limita cada sub-petición y es peor
        # (probado el 2026-10-19: 4075 limitaciones y extracción parcial).
        failed = 0
        for n, app in enumerate(apps, 1):
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
            if n % 100 == 0 or n == len(apps):
                log(f"Intune: aplicaciones {n}/{len(apps)}.")
        if not failed:
            result.software_complete_for = set(device_keys)
        else:
            log(f"Intune: {failed} aplicaciones no se pudieron leer; no se inferirán desinstalaciones.")

    def _software_per_device(self, result: ExtractResult, device_keys: set[str], log) -> None:
        # v1.0 rechaza managedDevices/{id}/detectedApps (400); en beta funciona como $expand.
        # Verificado en el tenant el 2026-10-19: 29 equipos en ~11 s sin limitaciones (per_app: ~24 min).
        # El $expand de beta no trae el editor (verificado: 0 de 136), usa otros ids para la mayoría
        # de apps e incluye paquetes del sistema que no están en el catálogo de Intune. El catálogo
        # v1.0 (pocas páginas) aporta el editor y delimita lo que se inventaría, como per_app.
        # Verificado el 2026-10-20 sobre 3609 entradas: 1106 por id, 2439 por nombre+versión y el
        # resto por nombre (versión más nueva que el catálogo) o paquetes del sistema.
        catalog = list(self.client.paginate(f"{self.api}/deviceManagement/detectedApps", {"$top": "500"}))
        by_id = {a["id"]: a for a in catalog}
        by_name_version = {(_key(a.get("displayName")), a.get("version") or ""): a for a in catalog}
        by_name = {_key(a.get("displayName")): a for a in catalog}
        log(f"Intune: catálogo de {len(catalog)} aplicaciones detectadas.")

        def resolve(entry: dict) -> dict | None:
            if entry.get("id") in by_id:
                return by_id[entry["id"]]
            name = _key(entry.get("displayName"))
            match = by_name_version.get((name, entry.get("version") or "")) or by_name.get(name)
            if match is None:
                return None
            return {**entry, "publisher": match.get("publisher"), "platform": entry.get("platform") or match.get("platform")}

        empty = skipped = 0
        for n, key in enumerate(sorted(device_keys), 1):
            try:
                body = self.client.get(f"/beta/deviceManagement/managedDevices/{key}",
                                       {"$expand": "detectedApps", "$select": "id"})
            except ConnectorError as exc:
                if exc.kind in ("auth", "permission"):
                    raise
                result.errors.append(f"managedDevices/{key}?$expand=detectedApps: {exc}")
                continue
            listed = body.get("detectedApps") or []
            apps = [app for app in map(resolve, listed) if app is not None]
            skipped += len(listed) - len(apps)
            result.installs.extend(self._install(app, key) for app in apps)
            if apps:
                result.software_complete_for.add(key)
            else:
                empty += 1  # lista vacía: puede ser falta de inventario; no se infieren bajas en ese equipo
            if n % 10 == 0 or n == len(device_keys):
                log(f"Intune: software de {n}/{len(device_keys)} equipos.")
        if empty:
            log(f"Intune: {empty} equipos sin aplicaciones detectadas; no se inferirán bajas en ellos.")
        if skipped:
            log(f"Intune: {skipped} entradas fuera del catálogo de Intune (paquetes del sistema) descartadas.")

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
