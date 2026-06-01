$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$SpecPath = Join-Path $ProjectRoot "build\inventario.spec"
$InstallerScript = Join-Path $ProjectRoot "installer\inventario_software.iss"

if (-not (Test-Path $PythonExe)) {
    throw "No se encontro .venv\Scripts\python.exe. Crea el entorno virtual antes de compilar."
}

& $PythonExe -m pip install -r (Join-Path $ProjectRoot "requirements.txt")
& $PythonExe -m pip install -r (Join-Path $ProjectRoot "requirements-build.txt")
& $PythonExe -m PyInstaller --clean --noconfirm $SpecPath

$isccCommand = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
$isccPath = if ($isccCommand) { $isccCommand.Source } else { $null }
if (-not $isccPath) {
    $defaultIscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
    if (Test-Path $defaultIscc) {
        $isccPath = $defaultIscc
    }
}

if (-not $isccPath) {
    Write-Warning "PyInstaller genero el ejecutable, pero no se encontro Inno Setup (ISCC.exe)."
    Write-Warning "Instala Inno Setup 6 y vuelve a ejecutar este script para generar el instalador."
    exit 0
}

& $isccPath $InstallerScript
