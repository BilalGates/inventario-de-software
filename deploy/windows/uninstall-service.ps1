#Requires -RunAsAdministrator
# Elimina el servicio. NO borra datos: la base de datos y la configuración siguen en
# C:\ProgramData\InventarioAsserta (bórrela a mano solo si está seguro).
$ErrorActionPreference = "Stop"
$Backend = Resolve-Path (Join-Path $PSScriptRoot "..\..\backend")
$Py = Join-Path $Backend ".venv\Scripts\python.exe"
Stop-Service InventarioAsserta -Force -ErrorAction SilentlyContinue
Push-Location $Backend; & $Py -m app.winservice remove; Pop-Location
Write-Host "Servicio eliminado. Datos conservados en $env:ProgramData\InventarioAsserta"
