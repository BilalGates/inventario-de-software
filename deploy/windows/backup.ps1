#Requires -RunAsAdministrator
# Copia de seguridad consistente de la base de datos SQLite del servicio (puede ejecutarse en caliente).
param([string]$Destino = "$env:ProgramData\InventarioAsserta\backups")
$Py = Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..\..\backend")) ".venv\Scripts\python.exe"
New-Item -ItemType Directory -Force $Destino | Out-Null
$src = "$env:ProgramData\InventarioAsserta\inventario.db"
$dst = Join-Path $Destino ("inventario_{0:yyyyMMdd_HHmmss}.db" -f (Get-Date))
& $Py -c "import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.close(); s.close()" $src $dst
Write-Host "Copia creada: $dst"
