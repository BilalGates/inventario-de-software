"""Conectores basados en ficheros: Panda (exportación de software por equipo) y CSV de Intune.

Son el mecanismo de compatibilidad y contingencia mientras no haya API disponible.
"""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from app.connectors.base import ConnectorError, DeviceRecord, ExtractResult, InstallRecord
from app.legacy import parse_panda_text


def decode(content: bytes) -> str:
    for enc in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            text = content.decode(enc)
            if enc == "utf-16" and "\x00" in text:
                continue
            return text
        except UnicodeDecodeError:
            continue
    raise ConnectorError("No se pudo decodificar el fichero (UTF-8/UTF-16/CP1252).", kind="data")


# --------------------------------------------------------------------------- Panda
_PANDA_NAME = re.compile(r"^(?P<host>[A-Za-z0-9][A-Za-z0-9._-]{0,62}?)(__.*)?$")


def hostname_from_filename(filename: str) -> str | None:
    """`PC-001.txt` o `PC-001__2026-10.txt` -> `PC-001`."""
    match = _PANDA_NAME.match(Path(filename).stem)
    return match.group("host") if match else None


class PandaFileConnector:
    """Una exportación de Panda contiene el software de UN equipo.

    params: content (str), filename, device_id (opcional, elegido en la UI) o hostname.
    """

    source_code = "panda"

    def extract(self, params: dict[str, Any], log) -> ExtractResult:
        parsed = parse_panda_text(params.get("content", ""))
        result = ExtractResult()
        if not parsed.rows:
            raise ConnectorError(
                "El fichero de Panda no contiene programas reconocibles: "
                + "; ".join(e.message for e in parsed.errors[:3]),
                kind="data",
            )
        hostname = params.get("hostname") or hostname_from_filename(params.get("filename", ""))
        device_key = f"device:{params['device_id']}" if params.get("device_id") else f"host:{(hostname or '').upper()}"
        if device_key == "host:":
            raise ConnectorError("No se puede identificar el equipo: indica el dispositivo o nombra el fichero "
                                 "como <HOSTNAME>.txt", kind="data")
        result.devices.append(DeviceRecord(
            key=device_key,
            ids={"hostname": hostname.upper()} if hostname else {},
            hostname=hostname,
            raw={"filename": params.get("filename"), "hostname": hostname},
        ))
        for row in parsed.rows:
            install_date = row.get("fecha_instalacion")
            result.installs.append(InstallRecord(
                device_key=device_key,
                name=row["nombre"],
                publisher=row.get("fabricante"),
                version=row.get("version"),
                platform="Windows",
                install_date=datetime.combine(install_date, datetime.min.time()) if install_date else None,
                raw={"line": row.get("raw_line"), "size": row.get("tamano")},
            ))
        # Panda no es la fuente de existencia de dispositivos: devices_complete se refiere
        # solo a este equipo. Los errores de líneas sueltas impiden inferir desinstalaciones.
        result.devices_complete = True
        if parsed.errors:
            result.warnings.extend(f"Línea {e.line_number}: {e.message}" for e in parsed.errors[:50])
            log(f"Panda: {len(parsed.errors)} líneas no reconocidas; no se inferirán desinstalaciones.")
        else:
            result.software_complete_for = {device_key}
        result.stats.update(programs=len(parsed.rows), parse_errors=len(parsed.errors), parse_mode=parsed.mode,
                            raw_hash=parsed.raw_hash)
        return result


# --------------------------------------------------------------------------- CSV Intune
# Alias de cabeceras: exportación del portal de Intune, exportación Jira/Intune y la salida
# de scripts PowerShell sobre Graph (nombres de propiedades de Graph).
DEVICE_COLUMNS = {
    "intune_id": ["Device ID", "DeviceId", "ManagedDeviceId", "id", "Intune Device ID"],
    "entra_id": ["AzureADDeviceId", "Azure AD Device ID", "Entra Device ID", "azureADDeviceId"],
    "hostname": ["Hostname", "Device name", "DeviceName", "deviceName", "Name"],
    "serial": ["Serial number", "SerialNumber", "serialNumber"],
    "manufacturer": ["IntuneManufacturer", "Manufacturer", "manufacturer"],
    "model": ["IntuneModel", "Model", "model"],
    "os_name": ["IntuneOperatingSystem", "Operating system", "OS", "operatingSystem"],
    "os_version": ["OS version", "OSVersion", "osVersion"],
    "upn": ["UserPrincipalName", "Primary user UPN", "userPrincipalName"],
    "user_name": ["UserDisplayName", "Primary user display name", "userDisplayName"],
    "ram": ["PhysicalMemoryInBytes", "physicalMemoryInBytes"],
    "storage_total": ["TotalStorageSpaceInBytes", "totalStorageSpaceInBytes"],
    "storage_free": ["FreeStorageSpaceInBytes", "freeStorageSpaceInBytes"],
    "mac_wifi": ["WiFiMacAddress", "Wi-Fi MAC", "wiFiMacAddress"],
    "mac_ethernet": ["EthernetMacAddress", "Ethernet MAC", "ethernetMacAddress"],
    "encrypted": ["IsEncrypted", "Encrypted", "isEncrypted"],
    "compliance": ["ComplianceState", "Compliance", "complianceState"],
    "ownership": ["ManagedDeviceOwnerType", "Ownership", "managedDeviceOwnerType"],
    "enrolled": ["EnrolledDateTime", "Enrollment date", "enrolledDateTime"],
    "last_sync": ["Last check-in", "LastSyncDateTime", "Last inventory date", "lastSyncDateTime"],
}
APP_COLUMNS = {
    "device_id": ["IntuneDeviceId", "DeviceId", "Device ID", "ManagedDeviceId"],
    "hostname": ["DeviceName", "Device name", "Device", "Equipo", "ComputerName", "Hostname"],
    "name": ["AppName", "Application", "DisplayName", "Application name", "App", "Programa", "Name"],
    "publisher": ["Publisher", "Editor", "Fabricante"],
    "version": ["Version", "AppVersion", "Versión", "Application version"],
    "platform": ["Platform", "Plataforma", "PlataformaApp"],
    # Columnas de dispositivo que añade Inventario_Programas_Intune.ps1
    "entra_id": ["AzureADDeviceId", "azureADDeviceId"],
    "upn": ["Usuario", "UserPrincipalName", "userPrincipalName"],
    "os_name": ["SistemaOperativo", "OperatingSystem", "operatingSystem"],
    "os_version": ["VersionSO", "OSVersion", "osVersion"],
    "last_sync": ["UltimaSincronizacion", "LastSyncDateTime", "lastSyncDateTime"],
}


def _sniff_reader(text: str) -> csv.DictReader:
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    return csv.DictReader(io.StringIO(text), dialect=dialect)


def _resolve(headers: list[str], aliases: dict[str, list[str]]) -> dict[str, str]:
    lower = {h.strip().lower(): h for h in headers if h}
    found = {}
    for field, names in aliases.items():
        for name in names:
            if name.lower() in lower:
                found[field] = lower[name.lower()]
                break
    return found


def _cell(row: dict, cols: dict[str, str], field: str) -> str | None:
    col = cols.get(field)
    val = (row.get(col) or "").strip() if col else ""
    return val if val and val.lower() not in {"unknown", "n/a", "-", "none", "null"} else None


def _int(value: str | None) -> int | None:
    try:
        num = int(float(value)) if value else None
    except ValueError:
        return None
    return num if num and num > 0 else None


def _bool(value: str | None) -> bool | None:
    if value is None:
        return None
    val = value.strip().lower()
    if val in {"true", "yes", "sí", "si", "1", "encrypted"}:
        return True
    if val in {"false", "no", "0", "not encrypted"}:
        return False
    return None


def _date(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S",
                "%d/%m/%Y %H:%M", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %I:%M:%S %p", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            value_clean = value.strip().split(".")[0].replace("Z", "") + ("Z" if fmt.endswith("Z") else "")
            dt = datetime.strptime(value_clean, fmt)
            return None if dt.year < 1990 else dt
        except ValueError:
            continue
    return None


class IntuneCsvConnector:
    """CSV de dispositivos y/o de aplicaciones exportados de Intune (portal o script PowerShell).

    params: content, filename, kind ("devices" | "apps" | auto), declared_complete (bool).
    Solo si el usuario declara que la exportación es completa se infieren desinstalaciones,
    y únicamente en los equipos presentes en el fichero.
    """

    source_code = "intune"

    def extract(self, params: dict[str, Any], log) -> ExtractResult:
        reader = _sniff_reader(params.get("content", ""))
        headers = reader.fieldnames or []
        app_cols = _resolve(headers, APP_COLUMNS)
        dev_cols = _resolve(headers, DEVICE_COLUMNS)
        kind = params.get("kind") or ("apps" if "name" in app_cols and "version" in app_cols else "devices")
        rows = list(reader)
        result = ExtractResult()
        if kind == "apps":
            self._apps(rows, app_cols, result, bool(params.get("declared_complete")))
        else:
            self._devices(rows, dev_cols, result)
        result.stats.update(kind=kind, rows=len(rows), columns=sorted(set(app_cols if kind == "apps" else dev_cols)))
        log(f"CSV Intune ({kind}): {len(rows)} filas, {len(result.devices)} dispositivos, "
            f"{len(result.installs)} instalaciones.")
        return result

    def _devices(self, rows: list[dict], cols: dict[str, str], result: ExtractResult) -> None:
        if "hostname" not in cols and "serial" not in cols:
            raise ConnectorError("El CSV no tiene columnas de nombre de equipo ni número de serie.", kind="data")
        for i, row in enumerate(rows, start=2):
            ids = {}
            if v := _cell(row, cols, "intune_id"):
                ids["intune_device_id"] = v
            if (v := _cell(row, cols, "entra_id")) and v != "00000000-0000-0000-0000-000000000000":
                ids["entra_device_id"] = v.lower()
            hostname = _cell(row, cols, "hostname")
            serial = _cell(row, cols, "serial")
            if not (ids or hostname or serial):
                result.warnings.append(f"Fila {i}: sin identificadores; ignorada.")
                continue
            upn = _cell(row, cols, "upn")
            result.devices.append(DeviceRecord(
                key=ids.get("intune_device_id") or ids.get("entra_device_id") or f"row:{serial or hostname}",
                ids=ids,
                hostname=hostname,
                serial_number=serial,
                manufacturer=_cell(row, cols, "manufacturer"),
                model=_cell(row, cols, "model"),
                os_name=_cell(row, cols, "os_name"),
                os_version=_cell(row, cols, "os_version"),
                user_upn=upn.lower() if upn else None,
                user_display_name=_cell(row, cols, "user_name"),
                ram_bytes=_int(_cell(row, cols, "ram")),
                storage_total_bytes=_int(_cell(row, cols, "storage_total")),
                storage_free_bytes=_int(_cell(row, cols, "storage_free")),
                mac_wifi=_cell(row, cols, "mac_wifi"),
                mac_ethernet=_cell(row, cols, "mac_ethernet"),
                encrypted=_bool(_cell(row, cols, "encrypted")),
                compliance_state=_cell(row, cols, "compliance"),
                ownership=_cell(row, cols, "ownership"),
                enrolled_at=_date(_cell(row, cols, "enrolled")),
                source_last_sync_at=_date(_cell(row, cols, "last_sync")),
                raw={k: row.get(v) for k, v in cols.items()},
            ))
        # Un CSV no garantiza contener todo el parque: no se infiere ausencia de dispositivos.
        result.devices_complete = False

    def _apps(self, rows: list[dict], cols: dict[str, str], result: ExtractResult, declared_complete: bool) -> None:
        if "name" not in cols or not ({"hostname", "device_id"} & set(cols)):
            raise ConnectorError("El CSV de aplicaciones necesita columnas de aplicación y de equipo.", kind="data")
        devices: dict[str, DeviceRecord] = {}
        for i, row in enumerate(rows, start=2):
            name = _cell(row, cols, "name")
            device_id = _cell(row, cols, "device_id")
            hostname = _cell(row, cols, "hostname")
            if not name or not (device_id or hostname):
                result.warnings.append(f"Fila {i}: falta aplicación o equipo; ignorada.")
                continue
            key = device_id or f"host:{hostname.upper()}"
            if key not in devices:
                ids = {"intune_device_id": device_id} if device_id else {"hostname": hostname.upper()}
                entra = _cell(row, cols, "entra_id")
                if entra and entra != "00000000-0000-0000-0000-000000000000":
                    ids["entra_device_id"] = entra.lower()
                upn = _cell(row, cols, "upn")
                devices[key] = DeviceRecord(
                    key=key, ids=ids, hostname=hostname, user_upn=upn.lower() if upn and "@" in upn else None,
                    os_name=_cell(row, cols, "os_name"), os_version=_cell(row, cols, "os_version"),
                    source_last_sync_at=_date(_cell(row, cols, "last_sync")),
                )
            result.installs.append(InstallRecord(
                device_key=key,
                name=name,
                publisher=_cell(row, cols, "publisher"),
                version=_cell(row, cols, "version"),
                platform=_cell(row, cols, "platform"),
                raw={k: row.get(v) for k, v in cols.items()},
            ))
        result.devices = list(devices.values())
        result.devices_complete = False
        if declared_complete:
            result.software_complete_for = set(devices)
