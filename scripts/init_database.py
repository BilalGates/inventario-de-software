from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app_paths import resource_path
from config import DB_CONFIG


class DatabaseInitError(RuntimeError):
    pass


def _connect(database: str | None = None):
    try:
        return pymysql.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            database=database,
            charset="utf8mb4",
            autocommit=True,
        )
    except pymysql.MySQLError as exc:
        raise DatabaseInitError(
            "No se pudo conectar con MySQL local. Revisa que el servicio este arrancado "
            "y que las credenciales del archivo .env sean correctas."
        ) from exc


def _strip_sql_comments(sql: str) -> str:
    lines = []
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.startswith("--") or stripped.startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines)


def _split_sql(sql: str) -> list[str]:
    sql = _strip_sql_comments(sql)
    statements = []
    current = []
    in_quote: str | None = None
    escape = False

    for char in sql:
        current.append(char)
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char in {"'", '"'}:
            if in_quote == char:
                in_quote = None
            elif in_quote is None:
                in_quote = char
            continue
        if char == ";" and in_quote is None:
            statement = "".join(current).strip().rstrip(";").strip()
            if statement:
                statements.append(statement)
            current = []

    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def _rewrite_database_name(sql: str) -> str:
    target = DB_CONFIG["database"]
    sql = re.sub(
        r"CREATE\s+DATABASE\s+IF\s+NOT\s+EXISTS\s+`?inventario_software`?",
        f"CREATE DATABASE IF NOT EXISTS `{target}`",
        sql,
        flags=re.IGNORECASE,
    )
    sql = re.sub(r"USE\s+`?inventario_software`?\s*;", f"USE `{target}`;", sql, flags=re.IGNORECASE)
    return sql


def _execute_sql_file(cursor, path: Path) -> None:
    if not path.exists():
        raise DatabaseInitError(f"No se encontro el archivo SQL: {path}")
    sql = _rewrite_database_name(path.read_text(encoding="utf-8"))
    for statement in _split_sql(sql):
        cursor.execute(statement)


def initialize_database() -> None:
    with _connect() as connection:
        with connection.cursor() as cursor:
            _execute_sql_file(cursor, resource_path("database", "schema.sql"))
            _execute_sql_file(cursor, resource_path("database", "seed.sql"))
            migrations_dir = resource_path("migrations")
            for migration in sorted(migrations_dir.glob("*.sql")):
                _execute_sql_file(cursor, migration)


_ALLOWED_TABLES = frozenset({"software", "equipos", "departamentos", "importaciones", "software_autorizado"})


def _table_count(table: str) -> int:
    if table not in _ALLOWED_TABLES:
        raise ValueError(f"Tabla no permitida: {table!r}")
    with _connect(DB_CONFIG["database"]) as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
            return int(cursor.fetchone()[0])


def import_historical_data(force: bool = False) -> dict[str, object]:
    if not force and (_table_count("software") > 0 or _table_count("equipos") > 0):
        return {"skipped": True, "reason": "La base ya contiene datos."}

    from migration.migrate_excel import migrate
    from scripts.importar_equipos_csv import import_csv

    excel_path = resource_path("Inventario_Software_ENS_Por_Departamento.xlsx")
    csv_path = resource_path("Inventario Equipos Informaticos Asserta(Equipos Asserta).csv")

    result: dict[str, object] = {"skipped": False}
    if excel_path.exists():
        result["software"] = migrate(excel_path)
    else:
        result["software"] = f"No se encontro {excel_path.name}"

    if csv_path.exists():
        result["equipos"] = import_csv(csv_path)
    else:
        result["equipos"] = f"No se encontro {csv_path.name}"

    return result


def setup_local_database(import_historical: bool = False, force_import: bool = False) -> dict[str, object]:
    initialize_database()
    result: dict[str, object] = {"database": "ready"}
    if import_historical:
        result["historical_import"] = import_historical_data(force=force_import)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Inicializa la base local de Inventario Software Asserta.")
    parser.add_argument("--import-historical", action="store_true", help="Importa Excel/CSV historicos si la base esta vacia.")
    parser.add_argument("--force-import", action="store_true", help="Fuerza la importacion aunque ya haya datos.")
    args = parser.parse_args()

    try:
        result = setup_local_database(args.import_historical, args.force_import)
    except DatabaseInitError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
