$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ScriptPath = Join-Path $ProjectRoot "crear_accesos_directos.ps1"

& $ScriptPath
