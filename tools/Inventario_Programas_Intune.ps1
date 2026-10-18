#requires -Version 5.1
<#
.SYNOPSIS
    Genera un inventario CSV del software detectado por Microsoft Intune.

.DESCRIPTION
    Consulta Microsoft Graph para obtener todas las aplicaciones detectadas por Intune
    y los dispositivos administrados en los que aparecen instaladas.

    Cada ejecucion crea un CSV nuevo con fecha y hora, por lo que no sobrescribe
    inventarios anteriores. Inventario Asserta importa automaticamente los CSV que
    aparecen en Escritorio\Inventario_Intune.

    IMPORTANTE:
    - El inventario refleja el ultimo estado conocido por Intune; no es una consulta
      en tiempo real contra cada ordenador.
    - Requiere una cuenta con permisos para leer dispositivos administrados en Intune.
    - En el primer uso, Microsoft Graph puede solicitar consentimiento para:
      DeviceManagementManagedDevices.Read.All

.OUTPUTS
    Escritorio\Inventario_Intune\Inventario_Programas_Intune_AAAA-MM-DD_HH-mm-ss.csv
#>

param(
    # Inicio de sesion con codigo (https://microsoft.com/devicelogin) en lugar de ventana.
    [switch]$DeviceCode
)

$ErrorActionPreference = "Stop"

# ============================================================
# CONFIGURACION
# ============================================================

$OutputFolder = Join-Path ([Environment]::GetFolderPath("Desktop")) "Inventario_Intune"
$Fecha = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$OutputFile = Join-Path $OutputFolder "Inventario_Programas_Intune_$Fecha.csv"

# ============================================================
# FUNCIONES
# ============================================================

function Invoke-GraphGetWithRetry {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Uri,

        [int]$MaxRetries = 6
    )

    $Attempt = 0

    while ($true) {
        try {
            return Invoke-MgGraphRequest -Method GET -Uri $Uri -OutputType PSObject
        }
        catch {
            $Attempt++

            if ($Attempt -ge $MaxRetries) {
                throw
            }

            $WaitSeconds = [Math]::Min([Math]::Pow(2, $Attempt), 30)

            Write-Warning "Error temporal consultando Microsoft Graph. Reintento $Attempt/$MaxRetries en $WaitSeconds segundos..."
            Start-Sleep -Seconds $WaitSeconds
        }
    }
}

function Get-GraphPagedData {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Uri
    )

    $Results = [System.Collections.Generic.List[object]]::new()

    do {
        $Response = Invoke-GraphGetWithRetry -Uri $Uri

        if ($null -ne $Response.value) {
            foreach ($Item in $Response.value) {
                $Results.Add($Item)
            }
        }

        $Uri = $Response.'@odata.nextLink'
    }
    while ($Uri)

    return $Results
}

# ============================================================
# PREPARACION
# ============================================================

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host " INVENTARIO DE SOFTWARE - MICROSOFT INTUNE" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $OutputFolder)) {
    New-Item -ItemType Directory -Path $OutputFolder -Force | Out-Null
}

# Instalar Microsoft Graph Authentication si no existe.
if (-not (Get-Module -ListAvailable -Name Microsoft.Graph.Authentication)) {
    Write-Host "Microsoft Graph no esta instalado." -ForegroundColor Yellow
    Write-Host "Instalando Microsoft.Graph.Authentication para el usuario actual..." -ForegroundColor Yellow

    try {
        Install-Module Microsoft.Graph.Authentication `
            -Scope CurrentUser `
            -Force `
            -AllowClobber
    }
    catch {
        Write-Host ""
        Write-Host "No se pudo instalar Microsoft.Graph.Authentication." -ForegroundColor Red
        Write-Host "Prueba a abrir PowerShell como administrador y ejecutar:" -ForegroundColor Yellow
        Write-Host "Install-Module Microsoft.Graph.Authentication -Scope CurrentUser -Force -AllowClobber"
        throw
    }
}

Import-Module Microsoft.Graph.Authentication

# ============================================================
# LOGIN
# ============================================================

Write-Host "Iniciando sesion en Microsoft Graph..." -ForegroundColor Cyan
Write-Host "Usa una cuenta con acceso a Microsoft Intune." -ForegroundColor DarkGray
Write-Host ""

# El inicio de sesion integrado de Windows (WAM) falla sin una ventana propietaria
# ("A window handle must be configured"): se usa el navegador y, si no, codigo de dispositivo.
try { Set-MgGraphOption -EnableLoginByWAM $false } catch {}

function Connect-Inventario([switch]$Code) {
    try {
        if ($Code) { Connect-MgGraph -Scopes "DeviceManagementManagedDevices.Read.All" -NoWelcome -UseDeviceCode }
        else { Connect-MgGraph -Scopes "DeviceManagementManagedDevices.Read.All" -NoWelcome }
    }
    catch {
        # El SDK a veces lanza "Error al escribir en un agente de escucha" (EventSourceException)
        # DESPUES de autenticar correctamente: si hay sesion, se continua.
        if (Get-MgContext) { Write-Warning "Aviso interno de Microsoft Graph ignorado: sesion iniciada correctamente." }
        else { throw }
    }
}

if ($DeviceCode) {
    Connect-Inventario -Code
}
else {
    try { Connect-Inventario }
    catch {
        Write-Warning "No se pudo abrir el inicio de sesion en el navegador; se usara un codigo de dispositivo."
        Connect-Inventario -Code
    }
}
Write-Host "Sesion iniciada como: $((Get-MgContext).Account)" -ForegroundColor Green

try {
    # ========================================================
    # APLICACIONES DETECTADAS
    # ========================================================

    Write-Host ""
    Write-Host "Consultando aplicaciones detectadas por Intune..." -ForegroundColor Cyan

    $AppsUri = "https://graph.microsoft.com/v1.0/deviceManagement/detectedApps?`$select=id,displayName,version,publisher,platform,deviceCount"
    $Apps = Get-GraphPagedData -Uri $AppsUri

    $Apps = @($Apps | Where-Object {
        $_.deviceCount -gt 0 -and
        -not [string]::IsNullOrWhiteSpace($_.displayName)
    })

    Write-Host "Aplicaciones con dispositivos asociados: $($Apps.Count)" -ForegroundColor Green

    if ($Apps.Count -eq 0) {
        Write-Warning "Intune no ha devuelto aplicaciones detectadas con dispositivos asociados."
        Write-Warning "Revisa que haya inventario de aplicaciones disponible y que la cuenta tenga permisos."
        return
    }

    # ========================================================
    # RELACIONAR APP -> DISPOSITIVOS
    # ========================================================

    $Inventario = [System.Collections.Generic.List[object]]::new()
    $Errores = [System.Collections.Generic.List[object]]::new()

    for ($i = 0; $i -lt $Apps.Count; $i++) {
        $App = $Apps[$i]

        $Percent = [Math]::Round((($i + 1) / $Apps.Count) * 100, 0)

        Write-Progress `
            -Activity "Generando inventario de software" `
            -Status "$($i + 1) de $($Apps.Count): $($App.displayName)" `
            -PercentComplete $Percent

        try {
            $EncodedId = [System.Uri]::EscapeDataString([string]$App.id)

            $DevicesUri = "https://graph.microsoft.com/v1.0/deviceManagement/detectedApps/$EncodedId/managedDevices?`$select=id,deviceName,userPrincipalName,operatingSystem,osVersion,lastSyncDateTime,azureADDeviceId"
            $Devices = Get-GraphPagedData -Uri $DevicesUri

            foreach ($Device in $Devices) {
                $Inventario.Add(
                    [PSCustomObject]@{
                        Equipo              = $Device.deviceName
                        Usuario             = $Device.userPrincipalName
                        Programa            = $App.displayName
                        Version             = $App.version
                        Editor              = $App.publisher
                        PlataformaApp       = $App.platform
                        SistemaOperativo    = $Device.operatingSystem
                        VersionSO           = $Device.osVersion
                        UltimaSincronizacion = $Device.lastSyncDateTime
                        AzureADDeviceId      = $Device.azureADDeviceId
                        IntuneDeviceId       = $Device.id
                    }
                )
            }
        }
        catch {
            $Errores.Add(
                [PSCustomObject]@{
                    Programa = $App.displayName
                    Version  = $App.version
                    Error    = $_.Exception.Message
                }
            )

            Write-Warning "No se pudo consultar '$($App.displayName)'. Se continuara con el resto."
        }
    }

    Write-Progress -Activity "Generando inventario de software" -Completed

    # ========================================================
    # EXPORTACION
    # ========================================================

    $InventarioOrdenado = @(
        $Inventario |
        Sort-Object Equipo, Programa, Version
    )

    if ($InventarioOrdenado.Count -eq 0) {
        Write-Warning "No se han recuperado asociaciones entre aplicaciones y dispositivos."
        return
    }

    # Errores primero: Inventario Asserta solo considera completo el CSV si no existe el fichero
    # de errores con la misma fecha cuando detecta el inventario.
    if ($Errores.Count -gt 0) {
        $ErrorFile = Join-Path $OutputFolder "Errores_Inventario_Intune_$Fecha.csv"

        $Errores |
            Export-Csv `
                -Path $ErrorFile `
                -Delimiter ";" `
                -NoTypeInformation `
                -Encoding UTF8
    }

    # Se escribe con otro nombre y se renombra al final, para que la importacion automatica
    # nunca lea un fichero a medio escribir.
    $TempFile = "$OutputFile.tmp"
    $InventarioOrdenado |
        Export-Csv `
            -Path $TempFile `
            -Delimiter ";" `
            -NoTypeInformation `
            -Encoding UTF8
    Move-Item -Path $TempFile -Destination $OutputFile -Force

    # ========================================================
    # RESUMEN
    # ========================================================

    $NumeroEquipos = @(
        $InventarioOrdenado |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_.Equipo) } |
        Select-Object -ExpandProperty Equipo -Unique
    ).Count

    $NumeroProgramas = @(
        $InventarioOrdenado |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_.Programa) } |
        Select-Object -ExpandProperty Programa -Unique
    ).Count

    Write-Host ""
    Write-Host "==============================================" -ForegroundColor Green
    Write-Host " INVENTARIO COMPLETADO" -ForegroundColor Green
    Write-Host "==============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Equipos encontrados     : $NumeroEquipos"
    Write-Host "Programas distintos     : $NumeroProgramas"
    Write-Host "Instalaciones registradas: $($InventarioOrdenado.Count)"
    Write-Host "Errores                  : $($Errores.Count)"
    Write-Host ""
    Write-Host "CSV generado:" -ForegroundColor Cyan
    Write-Host $OutputFile
    Write-Host ""
    Write-Host "Inventario Asserta lo importara automaticamente: http://127.0.0.1:8180/sincronizacion" -ForegroundColor Cyan

    if ($Errores.Count -gt 0) {
        Write-Host "Se ha generado tambien un CSV con las consultas que fallaron:" -ForegroundColor Yellow
        Write-Host $ErrorFile
        Write-Host ""
    }

    Write-Host "Nota: los datos corresponden al ultimo inventario conocido por Intune;" -ForegroundColor DarkGray
    Write-Host "no a una consulta en tiempo real de cada ordenador." -ForegroundColor DarkGray
}
finally {
    Disconnect-MgGraph | Out-Null
}
