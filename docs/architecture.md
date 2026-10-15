# Arquitectura

```
Navegador (http://127.0.0.1:8080)
        │  HTTPS/HTTP local
┌───────▼─────────────────────────────── Servicio de Windows "InventarioAsserta" ─┐
│  app.server (un proceso)                                                         │
│   ├─ Uvicorn + FastAPI ── /api/*  (REST, RBAC)                                   │
│   │                    └─ /*      (interfaz React compilada: frontend/dist)      │
│   └─ Hilo worker ──────── cola inventory_runs · programación mensual ·           │
│                           carpeta supervisada Panda · alertas de fuentes         │
└──────────────┬───────────────────────────────────────────────┬──────────────────┘
               │ SQLAlchemy                                    │ HTTPS (Graph)
        SQLite (ProgramData)  o  MySQL 8                 Microsoft Graph / Intune
```

## Componentes (backend/app)

| Módulo | Responsabilidad |
|---|---|
| `core/config.py` | Configuración por variables de entorno / `inventario.env`; validaciones de seguridad |
| `core/security.py` | Autenticación (`local`, `entra`, `dev`) y autorización por rol en el backend |
| `models/` | Modelo de datos (ver [data-model.md](data-model.md)) |
| `connectors/` | `graph.py` (cliente Graph con reintentos), `intune.py`, `files.py` (Panda, CSV Intune) |
| `services/sync.py` | Motor común de sincronización (pipeline, idempotencia, salvaguardas) |
| `services/devices.py` | Identidad y conciliación de dispositivos, asignaciones con historial |
| `services/software.py` | Catálogo, alias, versiones, autorización efectiva |
| `services/normalization.py` | Normalización conservadora de nombres, editores, series, hostnames |
| `services/snapshots.py` | Inventarios mensuales: generación, cobertura, revisión, comparación |
| `services/alerts.py`, `audit.py` | Alertas idempotentes; auditoría encadenada por hash |
| `api/routes/` | API REST (documentación OpenAPI en `/api/docs` fuera de producción) |
| `worker.py` | Pasada del worker (también ejecutable de forma independiente) |
| `server.py`, `winservice.py` | Proceso único y su envoltorio como servicio de Windows |
| `legacy_import.py` | Migración desde las tablas de la versión de escritorio |

## Pipeline de sincronización

1. **Extracción** por conector (`Connector.extract` → `ExtractResult`).
2. **Validación** (claves duplicadas, software huérfano).
3. **Observaciones originales** (`inventory_observations`, payload tal cual).
4. **Normalización** de nombres/editores/versiones.
5. **Conciliación** de dispositivos (ids oficiales → serie → hostname; casos de revisión si hay ambigüedad).
6. **Actualización operativa** con prioridad de fuentes; un valor vacío nunca borra uno conocido.
7. **Comparación**: altas, desinstalaciones (solo con lectura íntegra del equipo), cambios de versión.
8. **Alertas**: no autorizado, fallo/parcial de sincronización, caídas anómalas, equipos no observados, software nuevo.
9. **Registro**: estadísticas y log en `inventory_runs`, evento de auditoría.

La cola es la propia tabla `inventory_runs` (estado `queued`): la web solo encola y el worker
ejecuta, de modo que todo funciona aunque nadie tenga la interfaz abierta.

## Interfaz

SPA en `frontend/` (Vite, React 18, TypeScript, Tailwind, TanStack Query, MSAL para Entra ID).
Sistema de diseño propio en `src/components/ui.tsx` y `DataTable.tsx` con tokens de color en
`src/index.css` (modo claro/oscuro). Los filtros de las listas viven en la URL.
