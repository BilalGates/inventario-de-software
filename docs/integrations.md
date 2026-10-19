# Integraciones

## Microsoft Intune (Microsoft Graph)

**Estado: implementado y probado con respuestas simuladas. Bloqueado para validación real**
hasta disponer de un registro de aplicación en Entra ID con permisos concedidos.

### Qué falta para activarlo

1. Registro de aplicación en Entra ID (p. ej. "Inventario Asserta – Graph").
2. Permiso de **aplicación** `DeviceManagementManagedDevices.Read.All` con consentimiento de
   administrador. Es el único necesario (solo lectura).
3. Credencial: **certificado** (recomendado) o secreto. En `inventario.env`:
   ```
   INV_GRAPH_TENANT_ID=<tenant>
   INV_GRAPH_CLIENT_ID=<app id>
   INV_GRAPH_CERTIFICATE_PATH=C:/ProgramData/InventarioAsserta/graph.pem   # clave privada PEM
   INV_GRAPH_CERTIFICATE_THUMBPRINT=<huella SHA-1 en hex>
   # o bien INV_GRAPH_CLIENT_SECRET=<secreto>
   ```
4. Reiniciar el servicio y pulsar *Sincronización › Microsoft Intune › Sincronizar ahora*.

### Datos que se leen

- `GET /v1.0/deviceManagement/managedDevices` (`$select` explícito): id de Intune, id de Entra,
  nombre, serie, fabricante, modelo, SO y versión, UPN y nombre del usuario principal,
  inscripción, último check-in, cumplimiento, estado de gestión, cifrado, almacenamiento total y
  libre, MAC Wi-Fi/Ethernet, propiedad.
- RAM: la lista devuelve 0, así que se pide por dispositivo (`$select=physicalMemoryInBytes`). Si
  falla no es esencial (aviso).
- Software — **Discovered apps** (`/deviceManagement/detectedApps`), dos estrategias:
  - `per_app` (por defecto): lista apps y, por cada una, `…/detectedApps/{id}/managedDevices`.
    Es la técnica habitual de los scripts PowerShell de inventario.
  - `per_device`: `…/managedDevices/{id}/detectedApps`. Menos llamadas y completitud por equipo;
    **pendiente de validar** que el tenant la rellena.

### Discovered Apps vs. App Inventory

*Discovered apps* (detectedApps) lo recoge la Intune Management Extension y está en Graph v1.0;
es lo que usa el conector. *App inventory* (inventario de dispositivos / catálogo de
propiedades de Intune) se ve en el portal, pero **no se ha verificado** un endpoint estable de
Graph v1.0 que lo exponga, por lo que no se usa. No se asume que ambos devuelvan lo mismo.

### Comportamiento ante errores

| Situación | Tratamiento |
|---|---|
| Paginación | `@odata.nextLink` hasta el final |
| 429 / 500 / 502 / 503 / 504, error de red | Reintento con backoff exponencial; se respeta `Retry-After` (máx. 300 s) |
| 401 | Renueva el token una vez |
| 403 | Error de permisos inmediato (alerta crítica), sin reintentos |
| Fallo leyendo una app | La ejecución queda **parcial**: se aplican altas, no se infieren bajas |
| Caída > 25 % de dispositivos o > 40 % de instalaciones frente a la última ejecución completa | Se degrada a parcial y alerta crítica |
| Valores vacíos, `0001-01-01`, ids de Entra a ceros, `0` bytes | Se tratan como desconocidos (`NULL`) |

Los errores registran solo el código de Graph, nunca el cuerpo ni tokens.

**Incrementalidad**: Graph no ofrece *delta* para managedDevices/detectedApps. Cada ejecución es
completa (volumen bajo); la idempotencia la garantiza el motor.

### Script `Inventario_Programas_Intune.ps1` (analizado 2026-10-15)

Usa la misma técnica que la estrategia `per_app` del conector: `detectedApps` (descarta las que
tienen `deviceCount = 0`) y, por cada app, `detectedApps/{id}/managedDevices`, con paginación y
reintentos con backoff. Diferencias con el conector:

| Aspecto | Script | Conector 2.0 |
|---|---|---|
| Autenticación | Delegada e interactiva (`Connect-MgGraph`, usuario con acceso a Intune) | De aplicación, sin intervención (certificado/secreto) |
| `Retry-After` / 403 | No los distingue: reintenta cualquier error | Respeta `Retry-After`; 403 falla al instante |
| Fallos parciales | Los guarda en `Errores_Inventario_Intune_<fecha>.csv` y sigue | Ejecución parcial: sin inferir bajas |
| Hardware del equipo | No lo extrae | `managedDevices` completo (serie, modelo, RAM, disco, cifrado, cumplimiento…) |

**Integración ya operativa (sin credenciales de aplicación):** el servicio vigila
`INV_INTUNE_DROP_DIR` (por defecto `Escritorio\Inventario_Intune`, donde el script guarda sus CSV).
Cada `Inventario_Programas_Intune_<fecha>.csv` se importa solo (separador `;`, columnas
`Equipo, Usuario, Programa, Version, Editor, PlataformaApp, SistemaOperativo, VersionSO,
UltimaSincronizacion, AzureADDeviceId, IntuneDeviceId`): crea o concilia los equipos por id de
Intune/Entra, asigna el usuario y carga el software. Se considera completa (y por tanto registra
desinstalaciones) **solo si no existe** el `Errores_Inventario_Intune_<fecha>.csv` correspondiente.
Al ser un CSV, nunca cuenta como extracción completa del parque para el inventario mensual;
para eso sigue haciendo falta el conector API.

Las cifras de referencia (28 equipos, 3.340 instalaciones, 562 programas) se comprobarán con la
primera ejecución real: aparecen en *Sincronización › ejecución*.

## Panda Adaptive Defense

**API de WatchGuard Aether: no implementada.** No se ha confirmado que la licencia incluya
acceso API ni hay credenciales; no se ha programado contra endpoints no verificados. Para
implementarla se necesita: confirmación de licencia, *API key* y credenciales de acceso de
WatchGuard Cloud, y la documentación del endpoint de inventario de software de la cuenta.

**Ingesta por ficheros (operativa):**

- Subida desde la ficha del dispositivo o desde *Sincronización* (reutiliza el parser estable
  `backend/app/parsers/panda.py`: tabulado, vertical o pegado sin tabuladores).
- **Carpeta supervisada**: dejar `<HOSTNAME>.txt` en `INV_PANDA_DROP_DIR`
  (por defecto `C:\ProgramData\InventarioAsserta\panda`). El worker los importa y los mueve a
  `processed/` o `failed/`.
- Panda complementa los dispositivos de Intune por hostname (único y no retirado). Si hay
  ambigüedad, se abre un caso de revisión.
- Si el fichero tiene líneas no reconocidas o el número de programas cae bruscamente, no se
  registran desinstalaciones.

## CSV de Intune (contingencia)

Subida de CSV de dispositivos o de aplicaciones (portal o script). Un CSV no se considera
extracción completa del parque; las desinstalaciones solo se registran si se marca
"exportación completa" y solo en los equipos incluidos.
