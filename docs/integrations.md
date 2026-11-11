# Integraciones

## Microsoft Intune (Microsoft Graph)

Dos formas de autenticarse; si hay credenciales de aplicación, tienen prioridad.

### Opción A: sesión de usuario desde la web (sin registro de aplicación)

*Sincronización › Microsoft Intune › Conectar con Microsoft* (rol administrador) muestra un código
de dispositivo; se introduce en https://microsoft.com/devicelogin con una cuenta con acceso a
Intune. Usa el cliente público "Microsoft Graph Command Line Tools" (el mismo que el script
PowerShell) con los permisos delegados `DeviceManagementManagedDevices.Read.All` (inventario),
`DeviceManagementConfiguration.Read.All` (motivo de la no conformidad) y
`DeviceManagementManagedDevices.PrivilegedOperations.All` (acciones remotas: sincronizar, Defender).
Los dos últimos pueden requerir consentimiento de un administrador del tenant.

- La renovación pide siempre esos permisos explícitos, **nunca `.default`**: con este cliente
  compartido, `.default` devolvería todo lo que se haya concedido alguna vez a Graph PowerShell en
  el tenant (p. ej. permisos de escritura de directorio).
- Una sesión iniciada antes de ampliar los permisos, sin consentimiento de los nuevos (AADSTS65001),
  sigue sincronizando en **solo lectura**; Sincronización lo indica y ofrece reconectar. Hasta
  entonces, el motivo de la no conformidad y las acciones remotas responden «vuelva a conectar».

- El refresh token se guarda en la base de datos cifrado con AES-GCM y `INV_TOKEN_ENCRYPTION_KEY`,
  clave que solo conocen Vercel y GitHub Actions.
- Se renueva solo en cada sincronización (Entra rota el refresh token y se guarda el nuevo).
- Si caduca por inactividad o por políticas de acceso condicional, la ejecución falla con
  "La sesión de Microsoft ha caducado" y hay que volver a conectar.
- *Desconectar* borra el token; los datos importados se conservan. Ambos pasos quedan en auditoría.

### Opción B: registro de aplicación (credenciales de aplicación) — recomendada en producción

Por qué es preferible a la opción A:
- **Permisos propios**: el cliente "Graph Command Line Tools" es compartido; sus consentimientos se
  mezclan con los que usan los administradores en PowerShell. Un registro propio tiene solo lo que
  necesita esta aplicación.
- **Acceso condicional y revocación** por aplicación, sin afectar a Graph PowerShell.
- **Trazabilidad**: en los registros de inicio de sesión de Entra aparece con su propio nombre, no
  con el genérico de Microsoft.
- **Sin dependencia de una persona**: no caduca porque una cuenta deje de usarse o cambie su contraseña.

1. Registro de aplicación en Entra ID (p. ej. "Inventario Asserta – Graph").
2. Permiso de **aplicación** `DeviceManagementManagedDevices.Read.All` con consentimiento de
   administrador (inventario, solo lectura). Opcionales: `DeviceManagementConfiguration.Read.All`
   (motivo de la no conformidad) y `DeviceManagementManagedDevices.PrivilegedOperations.All`
   (acciones remotas desde la ficha del equipo).
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
  - `per_device` (por defecto): `beta/…/managedDevices/{id}?$expand=detectedApps`, una llamada
    por equipo. Validado en el tenant el 2026-10-19: 29 equipos en ~11 s, sin limitaciones.
    En v1.0 la ruta `…/managedDevices/{id}/detectedApps` responde 400. Un equipo que devuelve la
    lista vacía no se marca completo (no se infieren bajas en él).
  - `per_app`: lista apps (descarta `deviceCount = 0`) y, por cada una,
    `…/detectedApps/{id}/managedDevices`. Técnica del script PowerShell; con ~1100 apps tarda
    ~24 min por las limitaciones (429) de Intune. `$batch` no ayuda: Intune limita cada
    sub-petición (probado: 4075 limitaciones y extracción parcial).
  - Si `per_device` falla en **todos** los equipos (p. ej. Microsoft retira la ruta beta), la misma
    ejecución repite la lectura con `per_app` (v1.0), deja un aviso y abre la alerta
    `strategy_fallback:intune`. Un fallo en algunos equipos no activa el respaldo.
  - El progreso de la extracción se publica en el registro de la ejecución mientras corre.
- Tipo de equipo: móvil/servidor por el SO; portátil/sobremesa por la familia del modelo
  (Latitude, XPS, Inspiron, Dell Pro 14/16, LG gram… / OptiPlex, Precision Tower…). Solo se rellena
  si el equipo no tiene tipo; lo desconocido queda «Sin clasificar».

### Conformidad: motivo y acciones remotas

- Motivo: `GET /v1.0/deviceManagement/managedDevices/{id}/deviceCompliancePolicyStates`; se
  guardan solo las directivas en `nonCompliant`/`error`/`conflict` y sus `settingStates` en fallo.
  Si v1.0 no detalla los ajustes, se repite en `beta`. Se pide durante la sincronización **solo para
  los equipos no conformes** (no esencial: sin permiso se avisa y se sigue) y bajo demanda desde la
  ficha (*Consultar ahora*). Al pasar a conforme, el motivo se limpia.
- Los ajustes conocidos (BitLocker, Secure Boot, TPM, versión mínima del SO, Defender, firmas,
  antivirus, firewall, «Is active» de la directiva por defecto…) se traducen con una pista de
  corrección (`app/connectors/intune_compliance.py`); los desconocidos se muestran tal cual.
- Acciones (rol técnico, con auditoría `device.intune_action`):
  `POST …/managedDevices/{id}/syncDevice`, `windowsDefenderUpdateSignatures` y
  `windowsDefenderScan` (`quickScan: true`). Lista cerrada: no se exponen acciones destructivas
  (borrado, retirada, reinicio).
- La conformidad la evalúa el equipo: estas acciones fuerzan la reevaluación o resuelven causas
  concretas, pero no «aplican» la conformidad. El resultado tarda minutos.
- **Pendiente de verificar en el tenant**: que v1.0 devuelve `settingStates` rellenos y los
  nombres exactos de los ajustes (`setting`) de las directivas de Asserta.

### Software no autorizado: aviso por correo y desinstalación remota

Las dos acciones son **siempre manuales**: las lanza un técnico desde el menú de una alerta, de una
aplicación «No autorizado» o de un equipo. Quedan en auditoría y en *Auditoría › Acciones remotas*.

**Permisos (sesión de usuario, por niveles).** En *Sincronización*, la conexión con Microsoft tiene tres
niveles. Si falta el consentimiento de un nivel, la sesión baja al anterior sin desconectarse:

| Nivel | Añade | Consentimiento |
|---|---|---|
| `read` | `DeviceManagementManagedDevices.Read.All` (sincronizar el inventario) | Normalmente ya concedido |
| `mail` («Activar avisos por correo y fotos de perfil») | `Mail.Send.Shared` y `ProfilePhoto.Read.All` (solo lee la foto de perfil, que se guarda en caché a 96×96 y se revisa como mucho una vez por semana) | Suele bastar el del propio usuario, si el tenant lo permite |
| `full` («Ampliar todos los permisos») | `DeviceManagementConfiguration.Read.All` y `ReadWrite.All`, `DeviceManagementManagedDevices.PrivilegedOperations.All` | **Administrador global** (o administrador de roles con privilegios), para toda la organización |

Con credenciales de aplicación (opción B) se usan los permisos de aplicación equivalentes:
`Mail.Send` (conviene limitarlo al buzón remitente con una *Application Access Policy* de Exchange),
`DeviceManagementConfiguration.ReadWrite.All` y `DeviceManagementManagedDevices.PrivilegedOperations.All`.

**Aviso por correo.**
- **Configuración:** en *Configuración › Avisos por correo* se configuran el buzón compartido remitente, la copia
  opcional y la plantilla (campos `{nombre}`, `{equipo}`, `{programas}` y `{fecha}`).
- **Permiso en Exchange:** la cuenta conectada necesita **«Enviar como»** sobre ese buzón (Centro de administración
  de Exchange › Buzón › Delegación).
- **Contenido:** se envía un correo por persona (el usuario principal del equipo según Intune) con todos sus programas
  no autorizados. De cada programa incluye el motivo y la alternativa que dejó la política en las notas del producto.
- **Equipos sin usuario:** se listan y no se avisa a nadie.
- **Petición:** `POST /v1.0/users/{remitente}/sendMail`.

**Desinstalación (Intune Remediations; requiere licencia Windows Enterprise E3/E5 o Microsoft 365 E3/E5).**
- **Script:** se crea un *deviceHealthScript* por producto (`POST /beta/deviceManagement/deviceHealthScripts`), que se
  reutiliza y se actualiza si cambia. Se ejecuta como SYSTEM en 64 bits.
  - **Detección:** busca los nombres con los que se detectó el programa en las claves `Uninstall` de HKLM (64/32 bits)
    y de cada perfil (HKU), y como paquete AppX/MSIX.
  - **Corrección:** según lo que encuentra, usa `msiexec /x {GUID} /qn`, `QuietUninstallString` o
    `Remove-AppxPackage -AllUsers`. Si el programa no tiene modo silencioso, no se toca y se informa «MANUAL».
  - Generador: `app/services/uninstall_script.py`.
- **Ejecución:** se lanza bajo demanda en cada equipo con
  `POST /beta/deviceManagement/managedDevices/{id}/initiateOnDemandProactiveRemediation`.
- **Seguimiento:** el worker lee `GET …/deviceHealthScripts/{id}/deviceRunStates` y deja cada acción en hecha,
  fallida, manual o sin respuesta (a las 24 h). Si sale bien, pide `syncDevice`; la siguiente sincronización
  marca la instalación como retirada y cierra la alerta.
- **Salvaguardas:**
  - solo productos «No autorizado»;
  - nunca componentes, drivers ni runtimes;
  - lista protegida de software base y de seguridad: Intune, Panda, FortiClient, Microsoft 365/Edge/OneDrive/Teams,
    Windows, Defender, KeePass, Wazuh…;
  - simulación previa y confirmación con motivo obligatorio.
- **Pendiente de verificar en el tenant:**
  - los nombres exactos de los campos de salida de `deviceRunStates` en beta;
  - que *Remediations* está habilitado: requisito de licencia y aceptación de los términos en Intune ›
    Dispositivos › Scripts y correcciones.

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

**Contingencia (sin sesión de Microsoft en la nube):** el CSV que genera el script
(`Escritorio\Inventario_Intune\Inventario_Programas_Intune_<fecha>.csv`) se sube desde
*Sincronización › Microsoft Intune › Importar CSV* y se importa (separador `;`, columnas
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
- Panda complementa los dispositivos de Intune por hostname (único y no retirado). Si hay
  ambigüedad, se abre un caso de revisión.
- Si el fichero tiene líneas no reconocidas o el número de programas cae bruscamente, no se
  registran desinstalaciones.

## CSV de Intune (contingencia)

Subida de CSV de dispositivos o de aplicaciones (portal o script). Un CSV no se considera
extracción completa del parque; las desinstalaciones solo se registran si se marca
"exportación completa" y solo en los equipos incluidos.
