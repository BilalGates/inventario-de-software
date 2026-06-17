$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Desktop = [Environment]::GetFolderPath("Desktop")

$LocalExePath = Join-Path $ProjectRoot "dist_fixed\Inventario Software Asserta\Inventario Software Asserta.exe"
$MainPyPath = Join-Path $ProjectRoot "main.py"
$PythonwPath = Join-Path $ProjectRoot ".venv\Scripts\pythonw.exe"
$PythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

function New-InventarioShortcut {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [string]$TargetPath,

        [string]$Arguments = "",

        [Parameter(Mandatory = $true)]
        [string]$WorkingDirectory,

        [Parameter(Mandatory = $true)]
        [string]$Description,

        [string]$IconLocation = ""
    )

    $ShortcutPath = Join-Path $Desktop "$Name.lnk"
    $Shell = New-Object -ComObject WScript.Shell
    $Shortcut = $Shell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $TargetPath
    $Shortcut.Arguments = $Arguments
    $Shortcut.WorkingDirectory = $WorkingDirectory
    $Shortcut.Description = $Description

    if ($IconLocation -and (Test-Path $IconLocation)) {
        $Shortcut.IconLocation = "$IconLocation,0"
    }

    $Shortcut.Save()
    Write-Host "Acceso directo creado: $ShortcutPath"
}

if (-not (Test-Path $LocalExePath)) {
    throw "No se encontro el ejecutable local: $LocalExePath"
}

if (-not (Test-Path $MainPyPath)) {
    throw "No se encontro el punto de entrada de desarrollo: $MainPyPath"
}

$DevPythonPath = $null
if (Test-Path $PythonwPath) {
    $DevPythonPath = $PythonwPath
} elseif (Test-Path $PythonPath) {
    $DevPythonPath = $PythonPath
} else {
    throw "No se encontro Python en el entorno virtual: $PythonwPath ni $PythonPath"
}

New-InventarioShortcut `
    -Name "Inventario Software Asserta Local" `
    -TargetPath $LocalExePath `
    -WorkingDirectory $ProjectRoot `
    -Description "Abrir Inventario Software Asserta como aplicacion local" `
    -IconLocation $LocalExePath

New-InventarioShortcut `
    -Name "Inventario Software Asserta Dev" `
    -TargetPath $DevPythonPath `
    -Arguments "`"$MainPyPath`"" `
    -WorkingDirectory $ProjectRoot `
    -Description "Abrir Inventario Software Asserta desde el codigo fuente" `
    -IconLocation $LocalExePath

Write-Host ""
Write-Host "Listo. Para anclar: clic derecho en el acceso directo o en la app abierta y elige 'Anclar a la barra de tareas'."
