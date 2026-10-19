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

# Sin el modulo Microsoft.Graph: en Windows PowerShell 5.1 su Connect-MgGraph falla con
# "Error al escribir en un agente de escucha" (EventSourceException). Se usa la API REST.
$script:ClientId = "14d82eec-204b-4c2f-b7e8-296a70dab67e"   # Microsoft Graph Command Line Tools (app publica de Microsoft)
$script:Scope    = "https://graph.microsoft.com/DeviceManagementManagedDevices.Read.All offline_access openid profile"
$script:Token    = $null

function Connect-GraphDeviceCode {
    $dc = Invoke-RestMethod -Method POST -Uri "https://login.microsoftonline.com/organizations/oauth2/v2.0/devicecode" `
        -Body @{ client_id = $script:ClientId; scope = $script:Scope }
    Write-Host ""
    Write-Host "Para iniciar sesion abre $($dc.verification_uri) y escribe el codigo:" -ForegroundColor Yellow
    Write-Host "    $($dc.user_code)" -ForegroundColor Yellow
    Write-Host ""
    $deadline = (Get-Date).AddSeconds([int]$dc.expires_in)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds ([int]$dc.interval)
        try {
            $script:Token = Invoke-RestMethod -Method POST -Uri "https://login.microsoftonline.com/organizations/oauth2/v2.0/token" `
                -Body @{ grant_type = "urn:ietf:params:oauth:grant-type:device_code"; client_id = $script:ClientId; device_code = $dc.device_code }
            $script:Token | Add-Member -NotePropertyName ExpiresAt -NotePropertyValue (Get-Date).AddSeconds([int]$script:Token.expires_in - 120)
            return
        }
        catch {
            $err = $null
            try { $err = ($_.ErrorDetails.Message | ConvertFrom-Json).error } catch {}
            if ($err -eq "authorization_pending" -or $err -eq "slow_down") { continue }
            throw "Inicio de sesion rechazado: $err"
        }
    }
    throw "El codigo de inicio de sesion ha caducado."
}

function Update-GraphToken {
    if ($script:Token -and (Get-Date) -ge $script:Token.ExpiresAt -and $script:Token.refresh_token) {
        $t = Invoke-RestMethod -Method POST -Uri "https://login.microsoftonline.com/organizations/oauth2/v2.0/token" `
            -Body @{ grant_type = "refresh_token"; client_id = $script:ClientId; refresh_token = $script:Token.refresh_token; scope = $script:Scope }
        $t | Add-Member -NotePropertyName ExpiresAt -NotePropertyValue (Get-Date).AddSeconds([int]$t.expires_in - 120)
        $script:Token = $t
    }
}

function Invoke-GraphGetWithRetry {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Uri,

        [int]$MaxRetries = 6
    )

    $Attempt = 0

    while ($true) {
        try {
            Update-GraphToken
            return Invoke-RestMethod -Method GET -Uri $Uri -Headers @{ Authorization = "Bearer $($script:Token.access_token)" }
        }
        catch {
            $Status = $null
            try { $Status = [int]$_.Exception.Response.StatusCode } catch {}
            if ($Status -eq 401 -or $Status -eq 403) { throw }   # permisos: no tiene sentido reintentar

            $Attempt++

            if ($Attempt -ge $MaxRetries) {
                throw
            }

            $WaitSeconds = [Math]::Min([Math]::Pow(2, $Attempt), 30)
            try {
                $RetryAfter = $_.Exception.Response.Headers["Retry-After"]
                if ($RetryAfter) { $WaitSeconds = [Math]::Min([int]$RetryAfter, 300) }
            } catch {}

            Write-Warning "Error temporal consultando Microsoft Graph ($Status). Reintento $Attempt/$MaxRetries en $WaitSeconds segundos..."
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

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# ============================================================
# LOGIN
# ============================================================

Write-Host "Iniciando sesion en Microsoft Graph..." -ForegroundColor Cyan
Write-Host "Usa una cuenta con acceso a Microsoft Intune." -ForegroundColor DarkGray
Write-Host ""

Connect-GraphDeviceCode
Write-Host "Sesion iniciada correctamente." -ForegroundColor Green

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
    $script:Token = $null
}
