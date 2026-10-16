# Quita el arranque automático. No borra datos (%LOCALAPPDATA%\InventarioAsserta).
Stop-ScheduledTask -TaskName "Inventario Asserta" -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "Inventario Asserta" -Confirm:$false -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object { $_.CommandLine -match 'app\.(server|supervisor)' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Write-Host "Arranque automático eliminado. Datos conservados en $env:LOCALAPPDATA\InventarioAsserta"
