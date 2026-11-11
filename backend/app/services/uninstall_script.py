"""Scripts de PowerShell para desinstalar un producto con Intune Remediations.

Se generan a partir de los nombres con los que el producto se detectó de verdad (alias del catálogo),
para no tocar nada que no sea ese programa:

- detección: busca el programa en el registro (Uninstall de HKLM 64/32 bits y de cada perfil en HKU) y
  como paquete AppX/MSIX. Sale con 1 si está (Intune lanza entonces la corrección) o con 0 si no.
- corrección: MSI → msiexec /x {GUID} /qn; AppX → Remove-AppxPackage (y el aprovisionado); EXE con
  QuietUninstallString → esa orden; EXE sin modo silencioso → no se toca y se informa MANUAL.

Cada línea de salida empieza por OK:, FALLO: o MANUAL: para interpretar el resultado.
"""
from __future__ import annotations

import hashlib
import re

from app.models import SoftwareProduct

# Nunca se generan scripts para software base, de gestión o de seguridad (aunque se marcara por error).
# Patrones por palabra para no bloquear de más (p. ej. «WhatsApp for Windows» sí se puede desinstalar).
PROTECTED = tuple(re.compile(p, re.I) for p in (
    r"\bintune\b", r"\bpanda\b", r"\bforti(client|net)\b", r"\bmicrosoft (365|office|edge|onedrive|teams)\b",
    r"^(msteams|microsoft teams|onedrive)\b", r"^windows\b", r"\bdefender\b", r"\bvisual c\+\+", r"\.net\b",
    r"\bruntime\b", r"\bdriver\b", r"\bcontrolador", r"\bkeepass\b", r"\b(company portal|portal de empresa)\b",
    r"\bbitlocker\b", r"\bwazuh\b"))
APPX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*(\.[A-Za-z0-9-]+)+$")  # 5319275A.WhatsAppDesktop, Microsoft.BingNews…


class NotUninstallable(ValueError):
    """El producto no puede desinstalarse desde el inventario (motivo en el mensaje)."""


def check(product: SoftwareProduct) -> None:
    if product.authorization_status != "unauthorized":
        raise NotUninstallable("Solo se puede desinstalar software marcado como «No autorizado».")
    if not product.is_relevant or product.category in ("system_component", "driver", "runtime", "update"):
        raise NotUninstallable("Es un componente del sistema, controlador o runtime: no se desinstala desde aquí.")
    if any(p.search(product.name) for p in PROTECTED):
        raise NotUninstallable(f"«{product.name}» es software base, de gestión o de seguridad: no se desinstala desde aquí.")


def _ps_list(names: list[str]) -> str:
    return "@(" + ", ".join("'" + n.replace("'", "''") + "'" for n in names) + ")"


_ROOTS = r"""$roots = @('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall',
           'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall')
Get-ChildItem Registry::HKEY_USERS -ErrorAction SilentlyContinue | ForEach-Object {
  $roots += "Registry::$($_.Name)\Software\Microsoft\Windows\CurrentVersion\Uninstall" }
function Get-Entries { foreach ($r in $roots) { Get-ChildItem $r -ErrorAction SilentlyContinue | ForEach-Object {
  $p = Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue
  if ($p.DisplayName -and ($names -contains $p.DisplayName)) { $p } } } }"""


def build(product: SoftwareProduct, raw_names: list[str]) -> dict:
    """Scripts de detección y corrección, y una pista del método (para la simulación)."""
    check(product)
    names = sorted({n.strip() for n in [product.name, *raw_names] if n and n.strip()}, key=str.casefold)
    appx = [n for n in names if APPX.match(n)]
    header = f"# Asserta Inventario · Desinstalar {product.name} (producto {product.id})\n$names = {_ps_list(names)}\n"
    detection = header + _ROOTS + r"""
$found = @()
Get-Entries | ForEach-Object { $found += "REG: $($_.DisplayName) $($_.DisplayVersion)" }
foreach ($n in $names) { Get-AppxPackage -AllUsers -Name $n -ErrorAction SilentlyContinue |
  ForEach-Object { $found += "APPX: $($_.PackageFullName)" } }
if ($found.Count -gt 0) { Write-Output ("PRESENTE: " + ($found -join '; ')); exit 1 }
Write-Output "AUSENTE"; exit 0
"""
    remediation = header + _ROOTS + r"""
$out = @(); $failed = $false
foreach ($e in Get-Entries) {
  $label = "$($e.DisplayName) $($e.DisplayVersion)".Trim()
  $guid = $e.PSChildName
  if ($e.WindowsInstaller -eq 1 -and $guid -match '^\{[0-9A-Fa-f-]{36}\}$') {
    $p = Start-Process msiexec.exe -ArgumentList "/x $guid /qn /norestart" -Wait -PassThru
    if (@(0, 1605, 1614, 3010) -contains $p.ExitCode) { $out += "OK: $label (MSI)" }
    else { $out += "FALLO: $label (MSI, código $($p.ExitCode))"; $failed = $true }
  } elseif ($e.QuietUninstallString) {
    $p = Start-Process cmd.exe -ArgumentList "/c $($e.QuietUninstallString)" -Wait -PassThru -WindowStyle Hidden
    if (@(0, 3010) -contains $p.ExitCode) { $out += "OK: $label (silencioso)" }
    else { $out += "FALLO: $label (código $($p.ExitCode))"; $failed = $true }
  } else {
    $out += "MANUAL: $label no tiene desinstalación silenciosa: REQUIERE DESINSTALACIÓN MANUAL"
  }
}
foreach ($n in $names) {
  Get-AppxPackage -AllUsers -Name $n -ErrorAction SilentlyContinue | ForEach-Object {
    try { Remove-AppxPackage -Package $_.PackageFullName -AllUsers -ErrorAction Stop; $out += "OK: $($_.Name) (AppX)" }
    catch { $out += "FALLO: $($_.Name) (AppX: $($_.Exception.Message))"; $failed = $true } }
  Get-AppxProvisionedPackage -Online -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -eq $n } |
    ForEach-Object { Remove-AppxProvisionedPackage -Online -PackageName $_.PackageName -ErrorAction SilentlyContinue | Out-Null }
}
if ($out.Count -eq 0) { $out += "OK: no quedaba nada que desinstalar" }
Write-Output ($out -join ' | ')
if ($failed) { exit 1 } else { exit 0 }
"""
    method = "AppX/MSIX" if appx and len(appx) == len(names) else "AppX + registro" if appx else "Registro (MSI o EXE)"
    digest = hashlib.sha256((detection + remediation).encode()).hexdigest()[:16]
    return {"names": names, "method": method, "detection": detection, "remediation": remediation, "hash": digest}


def interpret(output: str | None) -> str:
    """Estado final según la salida del script de corrección."""
    text = output or ""
    if "FALLO:" in text:
        return "failed"
    if "MANUAL:" in text:
        return "manual_required"
    return "succeeded"
