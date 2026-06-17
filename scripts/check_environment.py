"""
Diagnóstico del entorno de Inventario Asserta.

Comprueba (sin modificar nada):
  - versión de Python,
  - dependencias instaladas,
  - presencia de .env,
  - seguridad de la configuración de BD (root / contraseña vacía),
  - conectividad con MySQL y estado de la base de datos / migraciones.

Uso:
  python scripts/check_environment.py

Código de salida 0 si todo lo crítico está OK; 1 si hay problemas.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REQUIRED_PACKAGES = ["sqlalchemy", "pymysql", "pandas", "openpyxl", "dotenv", "PySide6"]


def _check_python() -> bool:
    print(f"Python: {sys.version.split()[0]}")
    if sys.version_info < (3, 11):
        print("  [WARN] Se recomienda Python 3.11 o superior.")
    return True


def _check_packages() -> bool:
    ok = True
    print("Dependencias:")
    for module in REQUIRED_PACKAGES:
        try:
            importlib.import_module(module)
            print(f"  [OK]    {module}")
        except Exception as exc:  # noqa: BLE001 - queremos reportar cualquier fallo de import
            print(f"  [FALTA] {module} ({exc})")
            ok = False
    return ok


def _check_env_file() -> bool:
    env_path = ROOT / ".env"
    if env_path.exists():
        print(".env: presente")
        return True
    print(".env: AUSENTE — copia .env.example a .env y rellénalo.")
    return False


def _check_db_security() -> bool:
    from config import allow_insecure_local_db, check_db_security

    issues = check_db_security()
    if not issues:
        print("Seguridad BD: OK (usuario dedicado y contraseña definida).")
        return True
    detail = "; ".join(issues)
    if allow_insecure_local_db():
        print(f"Seguridad BD: insegura ({detail}) — permitido por ALLOW_INSECURE_LOCAL_DB.")
        return True
    print(f"Seguridad BD: INSEGURA ({detail}) — la app NO arrancará. Ver docs/OPERACION.md.")
    return False


def _check_connectivity() -> bool:
    from config import DB_CONFIG

    try:
        import pymysql
    except Exception as exc:  # noqa: BLE001
        print(f"Conexión MySQL: no se pudo importar pymysql ({exc}).")
        return False

    try:
        conn = pymysql.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            charset="utf8mb4",
            connect_timeout=5,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Conexión MySQL: ERROR ({exc}).")
        return False

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = %s",
                           (DB_CONFIG["database"],))
            db_exists = cursor.fetchone() is not None
            print(f"Conexión MySQL: OK. Base '{DB_CONFIG['database']}': "
                  + ("existe" if db_exists else "NO existe (ejecuta: python main.py --init-db)"))
            if db_exists:
                cursor.execute("USE `%s`" % DB_CONFIG["database"].replace("`", ""))
                cursor.execute(
                    "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
                    "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'schema_version'",
                    (DB_CONFIG["database"],),
                )
                if cursor.fetchone()[0]:
                    cursor.execute("SELECT COUNT(*) FROM schema_version")
                    print(f"  Migraciones registradas (schema_version): {cursor.fetchone()[0]}")
                else:
                    print("  schema_version: no existe todavía (se crea al inicializar/migrar).")
    finally:
        conn.close()
    return True


def main() -> int:
    print("=== Diagnóstico de entorno — Inventario Asserta ===")
    results = [
        _check_python(),
        _check_packages(),
        _check_env_file(),
        _check_db_security(),
        _check_connectivity(),
    ]
    print("===================================================")
    if all(results):
        print("Resultado: entorno OK.")
        return 0
    print("Resultado: hay problemas que revisar (ver mensajes anteriores).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
