"""
Runner de migraciones versionadas para Inventario Asserta.

Qué hace:
  - Crea la tabla `schema_version` si no existe.
  - Lee `migrations/*.sql` en orden alfabético.
  - Aplica SOLO las migraciones que aún no están registradas en `schema_version`.
  - Registra cada migración aplicada (nombre de fichero + fecha).
  - Falla con un error claro si una migración falla (sin silenciar errores).

Reutiliza el parser de SQL y la resolución de BD de `scripts/init_database.py`
para no duplicar lógica.

Diferencia entre `database/schema.sql` y `migrations/`:
  * `database/schema.sql`  -> estado BASE completo para instalaciones limpias.
  * `migrations/*.sql`     -> cambios INCREMENTALes versionados sobre el base.
Todas las migraciones de este proyecto son idempotentes (usan IF NOT EXISTS /
comprobaciones de columna), por lo que re-ejecutarlas sobre una BD que ya las
tenía es seguro: la primera ejecución del runner sobre una BD preexistente las
re-aplica (no-op) y las registra. Ver docs/MODELO_DATOS.md.

Uso:
  python scripts/migrate_db.py           # aplica migraciones pendientes
  python scripts/migrate_db.py --list    # muestra aplicadas / pendientes
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import DB_CONFIG, resource_path
from scripts.init_database import (
    DatabaseInitError,
    _connect,
    _rewrite_database_name,
    _split_sql,
)


SCHEMA_VERSION_DDL = """
CREATE TABLE IF NOT EXISTS schema_version (
    id INT PRIMARY KEY AUTO_INCREMENT,
    migration_name VARCHAR(255) NOT NULL UNIQUE,
    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""


def migration_files(migrations_dir: Path | str | None = None) -> list[Path]:
    """Ficheros de migración ordenados alfabéticamente por nombre."""
    base = Path(migrations_dir) if migrations_dir is not None else Path(resource_path("migrations"))
    return sorted(base.glob("*.sql"), key=lambda path: path.name)


def pending_migrations(all_files: list[Path], applied: set[str]) -> list[Path]:
    """
    Función pura: devuelve, en orden, los ficheros cuyo nombre no esté ya aplicado.

    Aislada para poder testear la lógica de "no aplicar dos veces" sin MySQL.
    """
    return [path for path in all_files if path.name not in applied]


def _ensure_schema_version(cursor) -> None:
    cursor.execute(SCHEMA_VERSION_DDL)


def _applied_migrations(cursor) -> set[str]:
    cursor.execute("SELECT migration_name FROM schema_version")
    return {row[0] for row in cursor.fetchall()}


def _apply_migration(cursor, path: Path) -> None:
    sql = _rewrite_database_name(path.read_text(encoding="utf-8"))
    for statement in _split_sql(sql):
        try:
            cursor.execute(statement)
        except Exception as exc:
            raise DatabaseInitError(
                f"Falló la migración '{path.name}': {exc}\n"
                f"Sentencia que falló:\n{statement}"
            ) from exc
    cursor.execute(
        "INSERT INTO schema_version (migration_name) VALUES (%s)",
        (path.name,),
    )


def apply_pending_migrations(verbose: bool = False) -> list[str]:
    """
    Aplica las migraciones pendientes contra la BD configurada.
    Devuelve la lista de migraciones aplicadas en esta ejecución.
    """
    applied_now: list[str] = []
    with _connect(DB_CONFIG["database"]) as connection:
        with connection.cursor() as cursor:
            _ensure_schema_version(cursor)
            already = _applied_migrations(cursor)
            for path in pending_migrations(migration_files(), already):
                if verbose:
                    print(f"[migrate] aplicando {path.name} ...", flush=True)
                _apply_migration(cursor, path)
                applied_now.append(path.name)
    return applied_now


def _print_status() -> int:
    with _connect(DB_CONFIG["database"]) as connection:
        with connection.cursor() as cursor:
            _ensure_schema_version(cursor)
            already = _applied_migrations(cursor)
    files = migration_files()
    print("Migraciones aplicadas:")
    for path in files:
        if path.name in already:
            print(f"  [x] {path.name}")
    print("Migraciones pendientes:")
    pendientes = pending_migrations(files, already)
    if not pendientes:
        print("  (ninguna)")
    for path in pendientes:
        print(f"  [ ] {path.name}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Aplica migraciones pendientes (migrations/*.sql).")
    parser.add_argument("--list", action="store_true", help="Muestra migraciones aplicadas y pendientes y termina.")
    args = parser.parse_args()

    try:
        if args.list:
            return _print_status()
        applied = apply_pending_migrations(verbose=True)
    except DatabaseInitError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if applied:
        print(f"Migraciones aplicadas ({len(applied)}): {', '.join(applied)}")
    else:
        print("No hay migraciones pendientes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
