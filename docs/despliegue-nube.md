# Despliegue en la nube: Vercel + Supabase + GitHub Actions

Guía para poner Asserta Inventario en la nube y retirar la instalación del PC con Windows.
Está pensada para quien administra Microsoft 365 y GitHub en Asserta; cada paso indica dónde
se hace y qué valor sale de él.

## Arquitectura

| Pieza | Dónde | Qué hace |
|---|---|---|
| Interfaz web (React) | Vercel, estáticos | `frontend/dist`, servida desde el CDN de Vercel |
| API (FastAPI) | Vercel, función Python `api/index.py` | Todas las rutas `/api/*`. Sin estado |
| Base de datos | Supabase (PostgreSQL 16, UE) | Todo el inventario, la cola de ejecuciones y la auditoría |
| Worker | GitHub Actions, `.github/workflows/worker.yml` | Sincroniza Intune, procesa ficheros subidos, cierre mensual, alertas |
| Disparador horario | Supabase `pg_cron` | Lanza el worker cada hora (el cron de GitHub queda de respaldo) |
| Inicio de sesión | Microsoft Entra ID | Cuentas de Asserta con roles Admin, Técnico y Auditor |
| Intune | Microsoft Graph, registro de aplicación | Lectura de equipos y aplicaciones detectadas |

Cuando alguien pulsa **Sincronizar ahora**, sube un fichero o reintenta, la API encola la ejecución y
lanza el workflow del worker en ese momento. El resultado aparece en 1–2 minutos (lo que tarda
GitHub en arrancar el trabajo).

### Qué cambia respecto a la instalación de Windows

- **Inicio de sesión obligatorio** con Microsoft. Ya no existe el modo local sin login.
- **Intune solo con registro de aplicación.** La «sesión de Microsoft desde la web» guardaba el token
  cifrado con Windows (DPAPI) y no está disponible en la nube.
- **Sin carpetas supervisadas.** Las exportaciones de Panda y los CSV del script de Intune se suben
  desde *Sincronización › Importar fichero*.
- **Ficheros de hasta 4 MB** (límite de Vercel). Las exportaciones de Panda ocupan unos pocos KB.

### Planes y costes

- **Vercel**: el plan Hobby es solo para uso no comercial; para Asserta corresponde **Pro**.
- **Supabase**: el plan Free pausa los proyectos tras una semana sin actividad y no incluye copias
  diarias restaurables; para producción se recomienda **Pro**.
- **GitHub Actions**: el worker horario consume unos 1 000–1 500 minutos al mes. Un repositorio
  privado en el plan Free tiene 2 000 minutos incluidos.

Compruebe los precios vigentes antes de contratar: este documento no los fija.

---

## 1. Supabase

1. Cree un proyecto en <https://supabase.com/dashboard> con **región UE (Frankfurt)**. Guarde la
   contraseña de la base de datos en el gestor de contraseñas de IT.
2. En **Connect** (o *Project Settings › Database › Connection string*), copie dos cadenas:
   - **Transaction pooler**, puerto **6543**: la usará Vercel → `INV_DATABASE_URL`.
   - **Session pooler**, puerto **5432**: la usarán GitHub Actions y la migración → `INV_DATABASE_URL_SESSION`.

   Sustituya `[YOUR-PASSWORD]` por la contraseña. Formato:
   `postgresql://postgres.<ref>:<contraseña>@aws-0-eu-central-1.pooler.supabase.com:6543/postgres`

No hace falta crear tablas a mano: las crea el paso 4.

## 2. Microsoft Entra ID: inicio de sesión

Se crean **dos** registros de aplicación en <https://entra.microsoft.com> › *Aplicaciones › Registros
de aplicaciones*. Necesitará el **ID de inquilino (tenant)**, que aparece en *Información general*.

### 2.1 Registro de la API: «Asserta Inventario API»

1. *Nuevo registro* → nombre `Asserta Inventario API`, cuentas «solo de este directorio», sin URI de
   redirección. Anote el **ID de aplicación (cliente)** → `INV_ENTRA_API_CLIENT_ID`.
2. *Manifiesto*: ponga `"requestedAccessTokenVersion": 2` (en el manifiesto nuevo está en
   `api › requestedAccessTokenVersion`) y guarde. **Sin esto los tokens son v1 y la API rechaza
   todos los inicios de sesión.**
3. *Exponer una API* → *URI del identificador de aplicación* → acepte `api://<id de la API>`.
   *Agregar un ámbito*: nombre `access_as_user`, consentimiento de administradores y usuarios,
   estado habilitado.
4. *Roles de aplicación* → cree tres roles (tipo de miembro: Usuarios/Grupos):

   | Nombre para mostrar | Valor |
   |---|---|
   | Administrador de Inventario | `Inventario.Admin` |
   | Técnico de Inventario | `Inventario.Tecnico` |
   | Auditor de Inventario | `Inventario.Auditor` |

5. *Aplicaciones empresariales* › `Asserta Inventario API` › *Propiedades* → **¿Se requiere
   asignación? = Sí**. Después, *Usuarios y grupos* → asigne a cada persona o grupo su rol.
   Quien no tenga rol no puede entrar.

### 2.2 Registro de la web: «Asserta Inventario Web»

1. *Nuevo registro* → nombre `Asserta Inventario Web`, solo este directorio. Plataforma
   **Aplicación de página única (SPA)** con el URI de redirección del dominio de Vercel, p. ej.
   `https://inventario-asserta.vercel.app` (añada luego el dominio propio si lo hay, y
   `http://localhost:5173` para desarrollo). Anote el **ID de aplicación** → `INV_ENTRA_SPA_CLIENT_ID`.
2. *Permisos de API* → *Agregar* → *Mis API* → `Asserta Inventario API` → permiso delegado
   `access_as_user`. Pulse **Conceder consentimiento de administrador**.

## 3. Microsoft Graph: lectura de Intune

1. *Nuevo registro* → `Asserta Inventario Intune`, solo este directorio, sin redirección. Anote el
   **ID de aplicación** → `INV_GRAPH_CLIENT_ID`. El tenant es el mismo → `INV_GRAPH_TENANT_ID`.
2. *Permisos de API* → *Microsoft Graph* → **Permisos de aplicación** →
   `DeviceManagementManagedDevices.Read.All` (solo lectura; es el único necesario). Pulse
   **Conceder consentimiento de administrador**.
3. *Certificados y secretos* → *Nuevo secreto de cliente* (caducidad 12 o 24 meses). Copie el
   **valor** (solo se muestra una vez) → `INV_GRAPH_CLIENT_SECRET`. Apunte en el calendario de IT
   la fecha de caducidad: al caducar, la sincronización falla con una alerta crítica.

## 4. GitHub: secretos, migraciones y worker

### 4.1 Token para lanzar el worker

En GitHub › *Settings › Developer settings › Personal access tokens › Fine-grained tokens* cree un
token con acceso **solo al repositorio `inventario-de-software`** y el permiso
**Actions: Read and write**. Es `INV_WORKER_DISPATCH_TOKEN`. Anote su caducidad.

### 4.2 Secretos y variables del repositorio

*Settings › Secrets and variables › Actions*:

| Tipo | Nombre | Valor |
|---|---|---|
| Secret | `INV_DATABASE_URL_SESSION` | Cadena del *session pooler* (puerto 5432) |
| Secret | `INV_GRAPH_CLIENT_SECRET` | Secreto del paso 3 |
| Secret | `INV_WORKER_DISPATCH_TOKEN` | Token del paso 4.1 |
| Variable | `INV_ENTRA_TENANT_ID` | ID de inquilino |
| Variable | `INV_ENTRA_API_CLIENT_ID` | ID de la API (paso 2.1) |
| Variable | `INV_GRAPH_TENANT_ID` | ID de inquilino |
| Variable | `INV_GRAPH_CLIENT_ID` | ID del registro de Intune (paso 3) |

### 4.3 Crear las tablas

*Actions › Migraciones de base de datos › Run workflow*. Debe terminar en verde y mostrar la
revisión actual. A partir de aquí se ejecuta solo en cada cambio de esquema que llegue a `main`.

## 5. Copiar los datos del PC a Supabase

Se copian todas las tablas tal cual (ids, historial, clasificaciones, auditoría). Antes de copiar,
**detenga la instalación local** para que no cambie nada durante la copia:

```powershell
# En el PC donde corre hoy (PowerShell)
Stop-ScheduledTask -TaskName "Inventario Asserta"        # o detenga el servicio de Windows
cd C:\repositorios\inventario-de-software\backend
.venv\Scripts\pip install -r requirements.txt            # instala el controlador de PostgreSQL
$env:PGSSLMODE = "require"
$origen  = "sqlite:///C:/Users/<usuario>/AppData/Local/InventarioAsserta/inventario.db"
$destino = "<cadena del session pooler, puerto 5432>"
.venv\Scripts\python -m app.copy_database --source $origen --target $destino --check
.venv\Scripts\python -m app.copy_database --source $origen --target $destino
```

`--check` no escribe nada: comprueba que el esquema del destino está al día, que está vacío y que
ningún texto supera la longitud de su columna (PostgreSQL lo exige; SQLite no). La copia termina
verificando los recuentos de cada tabla y la **cadena de auditoría**; si algo no cuadra, lo dice y
termina con error.

La ruta de la base local está en `%LOCALAPPDATA%\InventarioAsserta\inventario.env`
(`INV_DATABASE_URL`).

## 6. Vercel

1. *Add New › Project* → importe el repositorio `inventario-de-software`. **Root Directory**: la raíz
   del repositorio. *Framework Preset*: Other (la configuración está en `vercel.json`).
2. *Environment Variables* (entorno Production):

   | Nombre | Valor |
   |---|---|
   | `INV_ENVIRONMENT` | `production` |
   | `INV_AUTH_MODE` | `entra` |
   | `INV_DATABASE_URL` | Cadena del *transaction pooler* (puerto 6543) |
   | `PGSSLMODE` | `require` |
   | `INV_ENTRA_TENANT_ID` | ID de inquilino |
   | `INV_ENTRA_API_CLIENT_ID` | ID de la API |
   | `INV_ENTRA_SPA_CLIENT_ID` | ID de la web |
   | `INV_GRAPH_TENANT_ID` | ID de inquilino |
   | `INV_GRAPH_CLIENT_ID` | ID del registro de Intune |
   | `INV_GRAPH_CLIENT_SECRET` | Secreto de Intune |
   | `INV_WORKER_INTERVAL_MINUTES` | `60` |
   | `INV_WORKER_DISPATCH_TOKEN` | Token del paso 4.1 |
   | `INV_WORKER_DISPATCH_REPO` | `BilalGates/inventario-de-software` |

3. *Deploy*. Si el dominio final no es el que puso en el paso 2.2, añádalo allí como URI de
   redirección.

La región de la función es Frankfurt (`fra1` en `vercel.json`), la misma zona que Supabase.

## 7. Poner en marcha el worker

1. *Actions › Worker › Run workflow*. Debe terminar en verde.
2. *Actions › Disparador del worker › Run workflow*. Instala en Supabase el trabajo `pg_cron` que lo
   lanza cada hora (minuto 5) y guarda el token en Supabase Vault.
3. En la web, *Configuración › Programación mensual*: revise día y hora del cierre (en UTC).

## 8. Comprobaciones

- [ ] Entrar con una cuenta con rol: se ve el Panel con los datos migrados.
- [ ] Entrar con una cuenta sin rol: «Su cuenta no tiene un rol asignado».
- [ ] *Auditoría › Registro de auditoría › Verificar integridad*: «Cadena íntegra».
- [ ] *Sincronización › Microsoft Intune › Sincronizar ahora*: en 1–2 minutos pasa a *Completada*.
- [ ] Subir una exportación de Panda: se procesa y aparece en la ficha del equipo.
- [ ] El Panel no muestra el aviso «El proceso de sincronización no está activo».

## 9. Retirar la instalación de Windows

Cuando todo lo anterior esté comprobado:

```powershell
.\deploy\windows\uninstall-autostart.ps1     # o desinstale el servicio de Windows
```

Conserve la base SQLite (`inventario.db`) un tiempo como copia. La instalación de Windows
(`deploy/windows`, `app/winservice.py`, `app/supervisor.py`) queda en el repositorio como histórico,
pero ya no se mantiene.

## Mantenimiento

| Qué caduca | Dónde se renueva | Qué pasa si caduca |
|---|---|---|
| Secreto de Intune | Entra › registro de Intune › Certificados y secretos | Alerta crítica, no sincroniza |
| Token del worker | GitHub › Fine-grained tokens; actualice el secreto y Vercel y vuelva a lanzar *Disparador del worker* | La sincronización espera al cron de respaldo de GitHub |
| Contraseña de la base | Supabase › Database › Reset password; actualice Vercel y GitHub | La web y el worker dejan de conectar |
