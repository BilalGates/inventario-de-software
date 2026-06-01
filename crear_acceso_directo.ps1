$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "Inventario Software Asserta.lnk"
$TargetPath = Join-Path $ProjectRoot "Inventario_Software.vbs"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($ShortcutPath)
$shortcut.TargetPath = $TargetPath
$shortcut.WorkingDirectory = $ProjectRoot
$shortcut.Description = "Abrir Inventario Software Asserta"
$shortcut.Save()

Write-Host "Acceso directo creado en: $ShortcutPath"
