$ErrorActionPreference = "Stop"
Add-Type -AssemblyName PresentationFramework

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$LogDir = Join-Path $ProjectRoot "logs"
$StdoutLog = Join-Path $LogDir "streamlit_stdout.log"
$StderrLog = Join-Path $LogDir "streamlit_stderr.log"

if (-not (Test-Path $PythonExe)) {
    [System.Windows.MessageBox]::Show("No se encontro el entorno virtual .venv. Ejecuta primero la instalacion del proyecto.", "Inventario Software")
    exit 1
}

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

$StreamlitCheck = & $PythonExe -m streamlit --version 2>$null
if ($LASTEXITCODE -ne 0) {
    [System.Windows.MessageBox]::Show("Streamlit no esta instalado en .venv. Ejecuta: .\.venv\Scripts\python.exe -m pip install -r requirements.txt", "Inventario Software")
    exit 1
}

$existing = Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue
if (-not $existing) {
    Start-Process -FilePath $PythonExe `
        -ArgumentList "-m streamlit run app.py --server.port 8501 --server.headless true" `
        -WorkingDirectory $ProjectRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $StdoutLog `
        -RedirectStandardError $StderrLog

    Start-Sleep -Seconds 3
}

Start-Process "http://localhost:8501"
