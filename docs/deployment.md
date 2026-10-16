# Instalación y operación

## Método recomendado: arranque automático al iniciar sesión (sin administrador)

```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\install-autostart.ps1
```

Registra la tarea programada **"Inventario Asserta"** de su usuario, que al iniciar sesión lanza
en segundo plano (sin ventana) `app.supervisor`, el cual mantiene viva la aplicación y la
reinicia si cae. Acceso: **http://127.0.0.1:8180**. Datos y configuración en
`%LOCALAPPDATA%\InventarioAsserta` (`inventario.env`, `inventario.db`, `logs\`).

| Tarea | Cómo |
|---|---|
| Estado | `http://127.0.0.1:8180/api/health` · `Get-ScheduledTask "Inventario Asserta"` |
| Parar / arrancar | `Stop-ScheduledTask` / `Start-ScheduledTask "Inventario Asserta"` |
| Registros | `%LOCALAPPDATA%\InventarioAsserta\logs\` (`app.log`, `app-output.log`, `supervisor.log`) |
| Actualizar | `git pull`, borrar `frontend\dist` si cambió la interfaz, y volver a ejecutar el instalador |
| Desinstalar | `deploy\windows\uninstall-autostart.ps1` (no borra datos) |

Verificado el 2026-10-16 en el equipo de IT: arranque, interfaz, API y reinicio automático
tras matar el proceso (relanzado en 10 s). El puerto 8080 lo ocupa un servicio de Windows
(`svchost`) en ese equipo; por eso se usa 8180.

## Alternativa: servicio de Windows (`install-service.ps1`) — NO operativa

Con Python 3.12.0 el alojamiento de servicios de pywin32 provoca una violación de acceso en
`python312.dll` al arrancar (evento 1000, `0xc0000005`), antes de ejecutar código de la
aplicación. Se deja el script por si se actualiza Python/pywin32, pero no se recomienda.
Si se instaló, elimínelo como administrador con `deploy\windows\uninstall-service.ps1`.

### Detalle del servicio (referencia)


```powershell
# PowerShell como ADMINISTRADOR, en la raíz del repositorio
powershell -ExecutionPolicy Bypass -File deploy\windows\install-service.ps1   # -Port 8180 por defecto
```

Pasos que realiza (idempotente; repetirlo tras `git pull` actualiza):

1. Crea `backend\.venv` e instala `backend\requirements.txt`.
2. Compila la interfaz (`frontend\dist`) si no existe (necesita Node.js).
3. Crea `C:\ProgramData\InventarioAsserta\inventario.env` si no existe y restringe la carpeta a
   Administradores y SYSTEM.
4. Registra los componentes de pywin32.
5. Instala (o actualiza) el servicio **InventarioAsserta** con inicio automático y reinicio ante fallos.
6. Lo arranca, comprueba `/api/health` y abre http://127.0.0.1:8180.

Tras actualizar el código del frontend, borre `frontend\dist` o ejecute `npm run build` antes
de reinstalar. Las migraciones de base de datos se aplican solas al arrancar el servicio.

## Configuración (`C:\ProgramData\InventarioAsserta\inventario.env`)

| Variable | Valor por defecto | Notas |
|---|---|---|
| `INV_ENVIRONMENT` | `production` | Oculta `/api/docs` |
| `INV_AUTH_MODE` | `local` | Sin login; **solo** acepta `127.0.0.1`. Para acceso en red: `entra` |
| `INV_BIND_HOST` / `INV_PORT` | `127.0.0.1` / `8180` | En modo local no se permite otra IP |
| `INV_DATABASE_URL` | SQLite en ProgramData | MySQL: `mysql+pymysql://usuario:clave@host:3306/inventario_asserta?charset=utf8mb4` |
| `INV_PANDA_DROP_DIR` | `…\InventarioAsserta\panda` | Carpeta supervisada |
| `INV_GRAPH_*` | — | Ver [integrations.md](integrations.md) |
| `INV_STALE_DEVICE_DAYS` | `30` | Días para "no observado recientemente" |
| `INV_WORKER_POLL_SECONDS` | `15` | Frecuencia del worker |

Tras cambiarlo: `Restart-Service InventarioAsserta`.

## Operación diaria

| Tarea | Cómo |
|---|---|
| Estado | `Get-Service InventarioAsserta` · panel de la app · `http://127.0.0.1:8180/api/health` |
| Parar / arrancar | `Stop-Service` / `Start-Service InventarioAsserta` |
| Registros | Visor de eventos › Aplicación (origen `InventarioAsserta`) para arranque/parada; el detalle de cada sincronización está en *Sincronización › ejecución* |
| Copia de seguridad | `deploy\windows\backup.ps1` (copia consistente en caliente a `…\InventarioAsserta\backups`). Programe una tarea diaria y copie la carpeta a un almacenamiento seguro |
| Restaurar | Parar el servicio, sustituir `inventario.db` por la copia, arrancar |
| Desinstalar | `deploy\windows\uninstall-service.ps1` (no borra datos) |

## Programación mensual

Configuración › *Inventario mensual automático* (día 1–28, hora UTC, fuentes). El worker lanza
las fuentes API, y cuando terminan genera el **borrador** del inventario del mes, que IT revisa
y aprueba en Auditoría. Si el equipo está apagado en la fecha, se lanza en cuanto arranque.

## Acceso para más personas (futuro)

El modo `local` está pensado para un único usuario en su equipo. Para que otros accedan:
`INV_AUTH_MODE=entra` (con registro de aplicación de la API y de la SPA y *app roles*
`Inventario.Admin`, `Inventario.Tecnico`, `Inventario.Auditor`), MySQL como base de datos,
`INV_BIND_HOST` en la IP del servidor y **HTTPS** delante (IIS/ARR o un proxy inverso con
certificado corporativo). El backend rechaza `local` fuera de 127.0.0.1.
