<#
.SYNOPSIS
  Arranque automático de Inventario Asserta al iniciar sesión, sin permisos de administrador.
  Tarea programada en segundo plano (sin ventana) que se relanza si la aplicación cae.
  Acceso: http://127.0.0.1:8180 (solo desde este equipo).

  powershell -ExecutionPolicy Bypass -File deploy\windows\install-autostart.ps1
  Idempotente: repetir tras un "git pull" para actualizar.
#>
param([int]$Port = 8180)
$ErrorActionPreference = "Stop"
$Repo     = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$Backend  = Join-Path $Repo "backend"
$Frontend = Join-Path $Repo "frontend"
$Venv     = Join-Path $Backend ".venv"
$Py       = Join-Path $Venv "Scripts\python.exe"
$Pyw      = Join-Path $Venv "Scripts\pythonw.exe"
$DataDir  = Join-Path $env:LOCALAPPDATA "InventarioAsserta"
$EnvFile  = Join-Path $DataDir "inventario.env"
$Task     = "Inventario Asserta"

Write-Host "1/5 Entorno Python" -ForegroundColor Cyan
if (-not (Test-Path $Py)) { python -m venv $Venv }
& $Py -m pip install --quiet --upgrade pip
& $Py -m pip install --quiet -r (Join-Path $Backend "requirements.txt")

Write-Host "2/5 Interfaz web" -ForegroundColor Cyan
if (-not (Test-Path (Join-Path $Frontend "dist\index.html"))) {
  Push-Location $Frontend; npm ci --no-audit --no-fund; npm run build; Pop-Location
}

Write-Host "3/5 Configuración en $DataDir" -ForegroundColor Cyan
New-Item -ItemType Directory -Force $DataDir, (Join-Path $DataDir "panda"), (Join-Path $DataDir "logs") | Out-Null
$IntuneDir = Join-Path ([Environment]::GetFolderPath("Desktop")) "Inventario_Intune"
New-Item -ItemType Directory -Force $IntuneDir | Out-Null
if (-not (Test-Path $EnvFile)) {
  $d = $DataDir.Replace('\', '/')
  @"
# Inventario Asserta - configuración (no subir a ningún repositorio)
INV_ENVIRONMENT=production
# local: sin login, solo accesible desde este equipo (127.0.0.1)
INV_AUTH_MODE=local
INV_BIND_HOST=127.0.0.1
INV_PORT=$Port
INV_DATABASE_URL=sqlite:///$d/inventario.db
INV_PANDA_DROP_DIR=$d/panda
# CSV de Inventario_Programas_Intune.ps1 (se importan solos)
INV_INTUNE_DROP_DIR=$($IntuneDir.Replace('\', '/'))
INV_LOG_FILE=$d/logs/app.log
# Credenciales de Microsoft Graph (Intune): ver docs/integrations.md
"@ | Set-Content -Encoding utf8 $EnvFile
}

Write-Host "4/5 Tarea de arranque" -ForegroundColor Cyan
$action   = New-ScheduledTaskAction -Execute $Pyw -Argument "-m app.supervisor" -WorkingDirectory $Backend
$trigger  = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
  -MultipleInstances IgnoreNew -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
Stop-ScheduledTask -TaskName $Task -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $Task -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
  -Description "Inventario Asserta: web en http://127.0.0.1:$Port y sincronizaciones programadas" -Force | Out-Null

Write-Host "5/5 Arranque" -ForegroundColor Cyan
Start-ScheduledTask -TaskName $Task
$ok = $false
foreach ($i in 1..30) {
  try { if ((Invoke-RestMethod "http://127.0.0.1:$Port/api/health" -TimeoutSec 2).database) { $ok = $true; break } } catch {}
  Start-Sleep 2
}
if ($ok) { Write-Host "Inventario Asserta funcionando: http://127.0.0.1:$Port" -ForegroundColor Green }
else { Write-Warning "No responde. Revise $DataDir\logs\app.log" }
