#Requires -RunAsAdministrator
<#
.SYNOPSIS
  Instala Inventario Asserta como servicio de Windows (arranque automático).
  Después se accede desde el navegador en http://127.0.0.1:8080 (solo desde este equipo).

.NOTES
  Ejecutar en PowerShell como administrador, desde la raíz del repositorio:
    powershell -ExecutionPolicy Bypass -File deploy\windows\install-service.ps1
  Es idempotente: puede repetirse para actualizar tras un "git pull".
#>
param(
  [int]$Port = 8080
)
$ErrorActionPreference = "Stop"
$Repo     = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$Backend  = Join-Path $Repo "backend"
$Frontend = Join-Path $Repo "frontend"
$Venv     = Join-Path $Backend ".venv"
$Py       = Join-Path $Venv "Scripts\python.exe"
$DataDir  = Join-Path $env:ProgramData "InventarioAsserta"
$EnvFile  = Join-Path $DataDir "inventario.env"
$Service  = "InventarioAsserta"
# Carpeta donde Inventario_Programas_Intune.ps1 guarda sus CSV (escritorio del usuario que instala)
$IntuneDir = Join-Path ([Environment]::GetFolderPath("Desktop")) "Inventario_Intune"

Write-Host "1/6 Entorno Python" -ForegroundColor Cyan
if (-not (Test-Path $Py)) { python -m venv $Venv }
& $Py -m pip install --quiet --upgrade pip
& $Py -m pip install --quiet -r (Join-Path $Backend "requirements.txt")

Write-Host "2/6 Interfaz web" -ForegroundColor Cyan
if (-not (Test-Path (Join-Path $Frontend "dist\index.html"))) {
  if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw "Falta Node.js para compilar la interfaz (frontend\dist)." }
  Push-Location $Frontend; npm ci --no-audit --no-fund; npm run build; Pop-Location
}

Write-Host "3/6 Configuración en $DataDir" -ForegroundColor Cyan
New-Item -ItemType Directory -Force $DataDir | Out-Null
if (-not (Test-Path $EnvFile)) {
  $DataFwd   = $DataDir.Replace('\', '/')
  $IntuneFwd = $IntuneDir.Replace('\', '/')
  $db = "$DataFwd/inventario.db"
  @"
# Inventario Asserta - configuración del servicio (no subir a ningún repositorio)
INV_ENVIRONMENT=production
# local: sin login, solo accesible desde este equipo (127.0.0.1)
INV_AUTH_MODE=local
INV_BIND_HOST=127.0.0.1
INV_PORT=$Port
INV_DATABASE_URL=sqlite:///$db
# Carpeta donde dejar exportaciones de Panda (<HOSTNAME>.txt) para importarlas solas:
INV_PANDA_DROP_DIR=$DataFwd/panda
# CSV generados por Inventario_Programas_Intune.ps1 (se importan solos y pasan a processed\)
INV_INTUNE_DROP_DIR=$IntuneFwd
# Credenciales de Microsoft Graph (Intune). Ver docs/integrations.md:
# INV_GRAPH_TENANT_ID=
# INV_GRAPH_CLIENT_ID=
# INV_GRAPH_CLIENT_SECRET=
"@ | Set-Content -Encoding utf8 $EnvFile
  New-Item -ItemType Directory -Force (Join-Path $DataDir "panda") | Out-Null
  New-Item -ItemType Directory -Force $IntuneDir | Out-Null
}
# Solo administradores y SYSTEM pueden leer la configuración y la base de datos.
icacls $DataDir /inheritance:r /grant:r "*S-1-5-32-544:(OI)(CI)F" "*S-1-5-18:(OI)(CI)F" | Out-Null

Write-Host "4/6 Componentes de servicio (pywin32)" -ForegroundColor Cyan
& $Py (Join-Path $Venv "Scripts\pywin32_postinstall.py") -install -quiet | Out-Null

Write-Host "5/6 Registro del servicio" -ForegroundColor Cyan
# El servicio lo ejecuta el python.exe BASE (junto a python3xx.dll) con app\winservice.py;
# el script añade las librerías del .venv. No se usa pythonservice.exe: copiado al .venv no
# encuentra la DLL de Python y el servicio no llega a arrancar.
$SvcArgs = @("--startup", "auto")
Push-Location $Backend
if (Get-Service $Service -ErrorAction SilentlyContinue) {
  Stop-Service $Service -Force -ErrorAction SilentlyContinue
  & $Py -m app.winservice @SvcArgs update
} else {
  & $Py -m app.winservice @SvcArgs install
}
Pop-Location
$image = (Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Services\$Service").ImagePath
Write-Host "   Ejecutable del servicio: $image"
# Reinicio automático si el proceso cae.
sc.exe failure $Service reset= 86400 actions= restart/60000/restart/60000/restart/300000 | Out-Null

Write-Host "6/6 Arranque" -ForegroundColor Cyan
Start-Service $Service
$ok = $false
foreach ($i in 1..30) {
  try { $h = Invoke-RestMethod "http://127.0.0.1:$Port/api/health" -TimeoutSec 2; if ($h.database) { $ok = $true; break } } catch {}
  Start-Sleep 2
}
if ($ok) {
  Write-Host "`nInventario Asserta funcionando: http://127.0.0.1:$Port" -ForegroundColor Green
  Start-Process "http://127.0.0.1:$Port"
} else {
  Write-Warning "El servicio no responde. Revise el Visor de eventos (Aplicación, origen 'InventarioAsserta')."
}
