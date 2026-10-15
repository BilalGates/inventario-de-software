# ADR 0003 — Migraciones de BD versionadas con `schema_version`

- **Estado:** Aceptada
- **Fecha:** 2026-06

## Contexto

La inicialización aplicaba `schema.sql` + `seed.sql` y luego **todas** las
`migrations/*.sql` en cada arranque, con los errores silenciados
(`ignore_errors=True`). Las migraciones eran idempotentes, pero:

- no había registro de qué migraciones se habían aplicado;
- los errores reales quedaban ocultos;
- migraciones pensadas para ejecutarse "una sola vez" se re-ejecutaban siempre.

No se quería introducir una herramienta pesada (Alembic) ni reescribir las
migraciones existentes.

## Decisión

Añadir control de versiones de schema **ligero y propio**, reutilizando el parser
de SQL existente de `scripts/init_database.py` (sin duplicarlo):

- Tabla `schema_version (id, migration_name UNIQUE, applied_at)`.
- `scripts/migrate_db.py`:
  - crea `schema_version` si no existe;
  - lee `migrations/*.sql` en orden alfabético;
  - aplica solo las **no registradas** y registra cada una;
  - **falla con error claro** (sin silenciar) si una migración falla.
- `initialize_database()` aplica primero el schema base y luego invoca el runner
  con tracking (en vez del bucle antiguo con errores silenciados).

Distinción mantenida: `database/schema.sql` = estado base completo;
`migrations/*.sql` = cambios incrementales.

## Consecuencias

- **+** Reproducible y trazable: se sabe qué se ha aplicado y cuándo.
- **+** Errores de migración visibles y bloqueantes.
- **+** Compatible con BD existentes: como las migraciones son idempotentes, en la
  primera ejecución del runner se re-aplican (no-op) y se registran.
- **−** Convención de nombres: hay números duplicados heredados (dos `002_*`, dos
  `003_*`); el orden alfabético los hace deterministas, pero **las migraciones
  nuevas deben usar prefijos únicos y crecientes** (`006_...`, `007_...`).
- La lógica pura `pending_migrations()` está cubierta por
  `tests/test_migrations.py` (incluye "no aplicar dos veces").
