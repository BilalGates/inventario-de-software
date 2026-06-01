$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "Inventario Software Asserta Local.lnk"
$TargetPath = Join-Path $ProjectRoot "dist_fixed\Inventario Software Asserta\Inventario Software Asserta.exe"
$WorkingDirectory = Split-Path -Parent $TargetPath

if (-not (Test-Path $TargetPath)) {
    throw "No se encontro el ejecutable: $TargetPath"
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($ShortcutPath)
$shortcut.TargetPath = $TargetPath
$shortcut.WorkingDirectory = $WorkingDirectory
$shortcut.Description = "Abrir Inventario Software Asserta como aplicacion local"
$shortcut.Save()

Write-Host "Acceso directo creado en: $ShortcutPath"
