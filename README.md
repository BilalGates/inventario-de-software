# Asserta Inventario 2.0

Plataforma interna de IT para el inventario de dispositivos, software, departamentos,
autorizaciones e inventarios mensuales de Asserta Global Healthcare Solutions.

Es una **aplicación web** que recoge datos de Microsoft Intune (Microsoft Graph) y de Panda
Adaptive Defense (exportaciones), los normaliza, detecta cambios y genera evidencias de auditoría.

## Despliegue en la nube (Vercel + Supabase)

La interfaz y la API se publican en **Vercel**, los datos viven en **Supabase** (PostgreSQL, UE) y el
worker de sincronización corre en **GitHub Actions**, lanzado cada hora por `pg_cron` y al momento
desde la web. Inicio de sesión con Microsoft Entra ID y roles. Guía paso a paso, incluida la copia
de los datos de la instalación de Windows: [docs/despliegue-nube.md](docs/despliegue-nube.md).

## Instalación local en Windows (histórico, ya no se mantiene)

Arranca sola en segundo plano y se usa en **http://127.0.0.1:8180**.
Requisitos: Windows 10/11, Python 3.11+ y Node.js 20+ (solo para compilar la interfaz).
No necesita permisos de administrador.

```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\install-autostart.ps1
```

Arranca al iniciar sesión, sin ventana, y se reinicia sola si cae. Datos y configuración en
`%LOCALAPPDATA%\InventarioAsserta`. Detalles: [docs/deployment.md](docs/deployment.md).

## Desarrollo

```powershell
cd backend; python -m venv .venv; .venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\python -m app.demo_data          # datos SINTÉTICOS de demostración (opcional)
.venv\Scripts\uvicorn app.main:app --reload    # API en :8000
.venv\Scripts\python -m app.worker             # worker (otra consola)
cd ..\frontend; npm install; npm run dev       # interfaz en http://localhost:5173
```

Pruebas: `backend> .venv\Scripts\pytest` · `frontend> npm test` · `frontend> npm run build; npm run test:e2e`.

## Estructura

| Carpeta | Contenido |
|---|---|
| `backend/` | API FastAPI, modelo SQLAlchemy, migraciones Alembic, conectores, motor de sincronización, worker y servicio de Windows |
| `frontend/` | Interfaz web (React + TypeScript + Tailwind) |
| `deploy/windows/` | Instalación, desinstalación y copias de seguridad del servicio |
| `docs/` | Documentación (abajo) |

## Documentación

| Tema | Documento |
|---|---|
| Arquitectura | [docs/architecture.md](docs/architecture.md) |
| Modelo de datos | [docs/data-model.md](docs/data-model.md) |
| Integraciones (Intune, Panda) | [docs/integrations.md](docs/integrations.md) |
| Instalación y operación | [docs/deployment.md](docs/deployment.md) |
| Seguridad | [docs/security.md](docs/security.md) |
| Migración desde la versión de escritorio | [docs/migration.md](docs/migration.md) |
| Decisiones de arquitectura | [docs/decisions.md](docs/decisions.md) |
| Estado del trabajo | [docs/progress.md](docs/progress.md) |
| Documentación de la versión de escritorio | [docs/legacy/](docs/legacy/) |

## Datos y seguridad

No suba datos reales ni credenciales al repositorio (es público). La configuración y la base
de datos del servicio viven en `C:\ProgramData\InventarioAsserta`, fuera del repositorio.
Ver [docs/security.md](docs/security.md), que incluye una exposición histórica pendiente de remediar.
