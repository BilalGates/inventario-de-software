<#
.SYNOPSIS
    Crea un acceso directo a Inventario Asserta en el Escritorio.

.DESCRIPTION
    El acceso directo arranca la app con pythonw.exe del entorno virtual,
    de modo que NO se abre ninguna ventana de terminal. Usa el icono
    resources/icons/app.ico (se genera solo si falta).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\crear_acceso_directo.ps1

.PARAMETER Nombre
    Nombre del acceso directo. Por defecto "Inventario Asserta".
#>
[CmdletBinding()]
param(
    [string]$Nombre = "Inventario Asserta"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$pythonw = Join-Path $root ".venv\Scripts\pythonw.exe"
$mainPy = Join-Path $root "main.py"
$icono = Join-Path $root "resources\icons\app.ico"

# --- Comprobaciones -------------------------------------------------------
if (-not (Test-Path $mainPy)) {
    throw "No se encuentra main.py en $root"
}

if (-not (Test-Path $pythonw)) {
    # Sin venv, recurrimos al pythonw del PATH.
    $cmd = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    if (-not $cmd) {
        throw "No se encuentra pythonw.exe. Crea el entorno virtual (.venv) o instala Python."
    }
    $pythonw = $cmd.Source
    Write-Warning "No hay .venv; se usara $pythonw"
}

# El icono se genera bajo demanda si aun no existe.
if (-not (Test-Path $icono)) {
    Write-Host "Generando el icono de la aplicacion..."
    $py = Join-Path $root ".venv\Scripts\python.exe"
    if (-not (Test-Path $py)) { $py = "python" }
    & $py (Join-Path $root "scripts\generar_icono.py")
}

# --- Crear el acceso directo ----------------------------------------------
$escritorio = [Environment]::GetFolderPath("Desktop")
$destino = Join-Path $escritorio "$Nombre.lnk"

$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($destino)
$lnk.TargetPath = $pythonw
$lnk.Arguments = '"{0}"' -f $mainPy
$lnk.WorkingDirectory = $root
$lnk.Description = "Inventario de software y hardware de Asserta"
if (Test-Path $icono) {
    $lnk.IconLocation = $icono
}
$lnk.Save()

Write-Host ""
Write-Host "Acceso directo creado:" -ForegroundColor Green
Write-Host "  $destino"
Write-Host "  -> $pythonw `"$mainPy`""
Write-Host ""
Write-Host "Ya puedes arrancar la app desde el Escritorio, sin terminal."
