# Modelo de datos

Fuente de verdad: `backend/app/models/` y las migraciones de `backend/alembic/versions/`.
Compatible con SQLite (servicio local) y MySQL 8 (`utf8mb4`). Las tablas de la versión de
escritorio (`equipos`, `software`, `software_instalado`, …) no se tocan; ver [migration.md](migration.md).

## Entidades

| Tabla | Propósito | Claves e integridad |
|---|---|---|
| `departments` | Departamentos editables (nombre, responsable, centro de coste, atributos JSON, activo) | `code` y `name` únicos; `legacy_id` |
| `users` | Personas (UPN). Con `role` pueden entrar en la app | `upn`, `entra_object_id` únicos |
| `device_types` | Portátil, sobremesa, servidor, móvil, periférico | `code` único |
| `devices` | Activo con identidad persistente `uid` (no depende del hostname); datos técnicos, estado, departamento/usuario vigentes, `field_sources` (procedencia por atributo), `first/last_seen_at` | `uid` único; índices por estado/departamento, serie, hostname |
| `device_external_ids` | Identificadores oficiales por fuente (`intune_device_id`, `entra_device_id`) | único (`source`,`id_type`,`value`) |
| `device_assignments` | Historial de departamento/usuario; la vigente tiene `ended_at` NULL | índice (`device_id`,`ended_at`) |
| `software_products` | Catálogo global (un producto aunque esté en N equipos), categoría, relevancia, autorización global, clasificación ENS, `merged_into_id` | único (`name_key`,`publisher_key`) |
| `software_aliases` | Nombre/editor de origen → producto (`auto` o `manual`) | único (`raw_name_key`,`raw_publisher_key`) |
| `software_versions` | Versiones como **texto** | único (`product_id`,`version`) |
| `software_installations` | Producto+versión presente en un equipo según una fuente; baja lógica (`present`, `removed_at`) | único (`device_id`,`product_id`,`version_id`,`source`) |
| `software_policies` | Autorización por ámbito global/departamento/dispositivo; excepciones con justificación, aprobador y vigencia; revocación sin borrado | índice (`product_id`,`scope`,`active`) |
| `inventory_sources` | Fuentes, prioridad (menor = más fiable), configuración no secreta | `code` único |
| `inventory_runs` | Ejecuciones y cola del worker: estado, completitud, intento, log, estadísticas | índices por estado y lote |
| `inventory_observations` | Datos originales de cada ejecución | único (`run_id`,`entity`,`external_key`) |
| `inventory_changes` | Cambios detectados (altas, bajas, versiones, asignaciones, autorizaciones…) | índices por fecha, equipo, producto |
| `inventory_snapshots` / `_items` | Inventario mensual (borrador → aprobado/rechazado; `legacy` para histórico importado) y sus filas | único (`period`,`version`) |
| `alerts` | Incidencias con `dedup_key` (no se duplican en reejecuciones) | índice por estado/severidad |
| `review_cases` | Conciliaciones ambiguas que decide IT | |
| `audit_events` | Auditoría encadenada por hash (solo inserción) | `hash` único |
| `app_settings` | Programación mensual, umbrales, latido del worker | |

## Estados que distingue el sistema

- **Vigente** (`status` ≠ `retired`, observado en los últimos `INV_STALE_DEVICE_DAYS`).
- **Retirado** (`status = retired`; solo por decisión manual, nunca automática).
- **No observado recientemente** (`last_seen_at` antiguo) — calculado, no destructivo.
- **Sincronización incompleta** (`inventory_runs.is_complete = false` / estado `partial`).
- **Dato desconocido**: `NULL` (p. ej. `encrypted`, RAM o serie no informados); nunca se inventa.

## Reglas

1. Versiones siempre texto; no se ordenan numéricamente.
2. Sin borrados físicos de datos de negocio (bajas lógicas, políticas revocadas, productos fusionados).
3. Precedencia de autorización: dispositivo › departamento › global › estado del producto.
4. Prioridad de atributos: manual (0) › Intune (10) › Panda (20) › sistema anterior (50).
