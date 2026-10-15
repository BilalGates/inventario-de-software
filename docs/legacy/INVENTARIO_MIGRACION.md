# Inventario de migración — PySide6 2.0

## Lógica de negocio encontrada en modules/

| Archivo | Contenido | Decisión |
|---|---|---|
| `software.py` | CRUD inventario software, métricas dashboard, queries ENS/departamentos | **Conservar** — lógica SQL madura |
| `equipos.py` | CRUD equipos, estado importaciones, exportación Excel | **Conservar** |
| `importacion.py` | Motor diff/apply de importaciones Panda, reactivaciones pendientes | **Conservar** |
| `autorizado.py` | Gestión software autorizado, promoción multidevice/antigüedad | **Conservar** |
| `exportacion.py` | Exportación Excel por departamento, completa, historial | **Conservar** |
| `departamento_page.py` | Página Streamlit — código UI acoplado a `st.*` | **Eliminar** — reemplazado por `ui/pages/` |

## Queries/modelos en database/

| Archivo | Contenido | Decisión |
|---|---|---|
| `connection.py` | SQLAlchemy engine + pool (mysql+pymysql://) | **Mantener SQLAlchemy** — todos los modules dependen de él. Cambiar a mysql-connector-python rompería todo. |
| `schema.sql` | DDL completo: departamentos, equipos, software, software_equipo, software_autorizado, importaciones | **Conservar** como referencia |
| `seed.sql` | Datos iniciales de departamentos | **Conservar** |
| `migration_20260526_redesign.sql` | Migración de redesign | Referencia histórica |
| `migration_20260528_servidores.sql` | Migración servidores | Referencia histórica |

## Utilidades en utils/

| Archivo | Contenido | Decisión |
|---|---|---|
| `normalizer.py` | `normalize_nombre()`, `normalize_equipo_nombre()`, `clean_version()` | **Conservar** |
| `parser.py` | Parser CSV/XLSX/paste para importaciones Panda y equipos | **Conservar** |
| `theme.py` | CSS Streamlit (ASSERTA_CSS) | **Eliminar** — es Streamlit |
| `ui_components.py` | Helpers Streamlit (`empty_state`, `page_header`) | **Eliminar** — es Streamlit |

## Páginas/funcionalidades en nicegui_app/ (eliminado)

- `dashboard.py` — métricas globales
- `departamento.py` — inventario por departamento
- `empresa.py` — software de toda la empresa
- `equipos.py` — gestión de equipos
- `autorizado.py` — software autorizado
- `importaciones.py` — historial de importaciones
- `calidad.py` — calidad de datos

→ Toda esta funcionalidad se reimplementa en `ui/pages/`.

## Páginas/funcionalidades en pyside_app/ (migradas a ui/)

| Página | Estado | Acción |
|---|---|---|
| `main_window.py` | QListWidget como nav, QTableWidget en páginas | Reemplazado por `ui/main_window.py` con sidebar y QTableView |
| `pages/dashboard_page.py` | MetricCard + DataTable (QTableWidget) | Adaptado a `ui/pages/dashboard.py` |
| `pages/departamento_page.py` | 5 tabs, importación completa | Adaptado a `ui/pages/departments.py` |
| `pages/estado_importaciones_page.py` | Lista de equipos con estado | Folded en dashboard y departments |
| `pages/software_empresa_page.py` | Vista empresa completa | Adaptado a `ui/pages/software_inventory.py` |
| `pages/calidad_datos_page.py` | Checks de calidad | Adaptado a `ui/pages/data_quality.py` |
| `pages/equipos_page.py` | Gestión equipos global | Adaptado a `ui/pages/hardware_inventory.py` |
| `pages/software_autorizado_page.py` | Software autorizado | Folded en `ui/pages/software_inventory.py` |
| `widgets/data_table.py` | **QTableWidget** (no permite alta performance) | **Reemplazado** por `ui/components/sortable_table.py` (QTableView + QAbstractTableModel) |
| `widgets/metric_card.py` | Tarjeta de métrica | Migrado a `ui/components/metric_card.py` |

## Migraciones SQL

| Carpeta | Contenido |
|---|---|
| `migration/` | `migrate_excel.py` (script Python de migración histórica) + log |
| `migrations/` | 5 scripts SQL numerados (001–005) |

**Decisión:** Carpetas tienen contenido diferente.
- `migration/migrate_excel.py` → movido a `scripts/migrate_excel.py`
- `migration/migrate_warnings.log` → descartado (es output temporal)
- `migrations/*.sql` → conservados, renombrado carpeta final es `migrations/`
- `migration/` → eliminada tras mover el script

## Decisiones de arquitectura

### ORM: SQLAlchemy (no reemplazado)
El prompt especifica `mysql-connector-python` pero toda la lógica de negocio en `modules/`
usa `sqlalchemy.text()` y el patrón de contexto `db.execute(text(...))`. Cambiar el driver
rompería 1500+ líneas de código funcional. Se mantiene `sqlalchemy + pymysql`.
El `scripts/init_database.py` usa `pymysql` directamente para inicializar el schema — esto se conserva.

### Versiones siempre como VARCHAR/str
Confirmado: `utils/normalizer.py::clean_version()` convierte cualquier valor numérico a str.
Todas las columnas `version_*` en schema.sql son VARCHAR(200).

### Departamentos como constantes
En `database/seed.sql` se insertan los 6 departamentos. En `config.py` se replican como
constante `DEPARTMENTS` para uso en ComboBoxes sin consultar la BD.
