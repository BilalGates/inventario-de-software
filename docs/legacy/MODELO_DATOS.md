# Modelo de datos — Inventario Asserta

Base de datos **MySQL 8.0** (`utf8mb4` / `utf8mb4_unicode_ci`). La fuente de
verdad del schema es [`database/schema.sql`](../database/schema.sql); los cambios
incrementales viven en [`migrations/`](../migrations/).

---

## Tablas

### `departamentos`
Lista fija (6 departamentos), poblada por `seed.sql`. No se edita desde la UI.

| Campo | Tipo | Notas |
|---|---|---|
| `id` | INT PK | |
| `codigo` | VARCHAR(30) UNIQUE | `gerencia`, `it`, `silicon`, `data_science`, `administracion`, `servidores` |
| `nombre` | VARCHAR(100) | nombre visible |
| `prefijo_id` | VARCHAR(5) | prefijo de código de software (`GER`, `IT`, ...) |

### `equipos`
Ordenadores / dispositivos (incluye campos de hardware añadidos por migraciones).

- FK `departamento_id → departamentos(id)`.
- UNIQUE `(departamento_id, nombre_norm)`.
- `nombre` (original) + `nombre_norm` (`UPPER(TRIM(...))`) para matching.
- **Soft-delete**: baja = `activo = FALSE` + `fecha_baja` (no se borra la fila).
- `es_servidor` BOOLEAN.

### `software`
Catálogo de software por departamento.

- FK `departamento_id → departamentos(id)`.
- UNIQUE `(departamento_id, nombre_norm)`.
- `codigo` autogenerado (`GER-001`, `IT-042`...).
- **`version_referencia` VARCHAR(200)** — siempre texto (ver reglas).
- `clasificacion_informacion`, `en_guia_105`, observaciones ENS.
- **Soft-delete**: `activo = FALSE`.

### `software_equipo` (tabla puente)
Qué software está instalado en qué equipo.

- FK `software_id → software(id)`, `equipo_id → equipos(id)`.
- UNIQUE `(software_id, equipo_id)`.
- `version_detectada` VARCHAR(200) — versión en ESE equipo (texto).
- **`presente` BOOLEAN** — `FALSE` = desinstalado en la última revisión
  (**no se borra**: se preserva el histórico).

### `software_autorizado`
Software autorizado de forma específica (1–2 máquinas) o general.

- FKs opcionales a `software`, `departamentos`, `equipos`.
- `equipo_id` (si existe) o `usuario_texto` (texto libre).
- `version` VARCHAR(200) — texto.
- `activo` BOOLEAN (soft-delete / promoción a inventario).

### `software_reactivacion_pendiente`
Cola de revisión: software inactivo que reaparece en una importación.

- FKs a `software`, `equipos`. `revisado` BOOLEAN, `accion` ENUM(`reactivar`,`ignorar`).

### `importaciones`
Log de auditoría ENS de cada importación confirmada.

- FK `equipo_id → equipos(id)`.
- Contadores `n_total/n_nuevos/n_actualizados/n_eliminados/n_cambios_version`,
  `metodo` ENUM(`paste`,`file`), `confirmada` BOOLEAN.

### `schema_version`
Control de migraciones aplicadas (la crea el runner de migraciones).

| Campo | Tipo |
|---|---|
| `id` | INT PK AUTO_INCREMENT |
| `migration_name` | VARCHAR(255) UNIQUE |
| `applied_at` | DATETIME DEFAULT CURRENT_TIMESTAMP |

---

## Relaciones (resumen)

```
departamentos 1───* equipos
departamentos 1───* software
software       1───* software_equipo *───1 equipos
software       0/1─* software_autorizado
software       1───* software_reactivacion_pendiente *───1 equipos
equipos        1───* importaciones
```

---

## Reglas de persistencia

1. **Versiones = TEXTO (VARCHAR), nunca numéricas.** Panda exporta `26.001.21563`,
   `7.4.2.1737`, `ad 9.0.10`; tratarlas como número rompe los puntos/ceros.
   - `utils/normalizer.py::clean_version()` normaliza cualquier entrada a `str`.
   - **No** se comparan versiones lexicográfica ni numéricamente. Para decidir si
     actualizar la versión de referencia se usa `version_changed(old, new)`
     (igualdad sobre el texto). Ver [adr/0002-versiones-como-texto.md](adr/0002-versiones-como-texto.md).

2. **Sin borrados físicos.** Bajas de equipo (`activo=FALSE`+`fecha_baja`),
   software desinstalado (`software_equipo.presente=FALSE`) y software dado de
   baja (`activo=FALSE`) se conservan para trazabilidad ENS.

3. **Nombres normalizados.** `nombre` (original) + `nombre_norm`
   (`UPPER(TRIM(colapsar espacios))`) para matching sin ambigüedad de mayúsculas.

4. **Trazabilidad.** Toda importación confirmada deja una fila en `importaciones`.

---

## Schema base vs. migraciones

- **`database/schema.sql`** — estado **base completo** para una instalación
  limpia (todas las tablas con `CREATE TABLE IF NOT EXISTS`). Es idempotente.
- **`migrations/*.sql`** — cambios **incrementales** versionados sobre el base
  (añadir columnas, índices, constraints, limpiezas de datos). Cada migración es
  idempotente (usa `IF NOT EXISTS` o comprobaciones en `INFORMATION_SCHEMA`).
- El runner ([`scripts/migrate_db.py`](../scripts/migrate_db.py)) crea
  `schema_version`, aplica en orden alfabético solo las **no registradas** y
  registra cada una. Re-ejecutarlo es seguro.

> En instalación limpia, `schema.sql` ya crea el estado actual completo, así que
> las migraciones se registran como aplicadas siendo prácticamente no-ops. En una
> BD preexistente, el runner las re-aplica (idempotente) y las registra.

Detalle de decisiones: [adr/0003-migraciones-db.md](adr/0003-migraciones-db.md).
