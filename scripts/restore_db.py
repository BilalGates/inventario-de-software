"""
Restaura la base de datos MySQL desde un fichero .sql (generado por backup_db.py).

ADVERTENCIA: operación DESTRUCTIVA. Sobrescribe el contenido de la base de datos
con el del fichero de backup. Pide confirmación salvo que se pase --yes.

Usa `mysql` (debe estar en el PATH) y la configuración de `.env`.

Uso:
  python scripts/restore_db.py --file backups/inventario_software_20260101_120000.sql
  python scripts/restore_db.py --file <dump.sql> --yes
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import DB_CONFIG


def restore(path: Path, assume_yes: bool = False) -> bool:
    if not path.exists():
        raise FileNotFoundError(path)

    if not assume_yes:
        print(f"ATENCIÓN: esto SOBRESCRIBIRÁ la base de datos '{DB_CONFIG['database']}' "
              f"en {DB_CONFIG['host']}:{DB_CONFIG['port']} con el contenido de {path.name}.")
        resp = input("Escribe 'si' para continuar: ").strip().lower()
        if resp not in {"si", "sí", "yes"}:
            print("Restauración cancelada.")
            return False

    # El dump (generado con --databases) ya contiene CREATE DATABASE / USE,
    # por lo que no se especifica base de datos en la línea de comandos.
    cmd = [
        "mysql",
        "-h", str(DB_CONFIG["host"]),
        "-P", str(DB_CONFIG["port"]),
        "-u", str(DB_CONFIG["user"]),
        "--default-character-set=utf8mb4",
    ]
    env = dict(os.environ)
    if DB_CONFIG["password"]:
        env["MYSQL_PWD"] = str(DB_CONFIG["password"])

    with path.open("rb") as handle:
        subprocess.run(cmd, check=True, stdin=handle, env=env)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Restaura la BD desde un fichero .sql de backup.")
    parser.add_argument("--file", required=True, help="Ruta al fichero .sql a restaurar.")
    parser.add_argument("--yes", action="store_true", help="No pedir confirmación (uso no interactivo).")
    args = parser.parse_args()

    try:
        ok = restore(Path(args.file).expanduser().resolve(), assume_yes=args.yes)
    except FileNotFoundError as exc:
        print(f"No existe el fichero de backup: {exc}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"mysql falló (código {exc.returncode}).", file=sys.stderr)
        return 1

    if not ok:
        return 1
    print("Restauración completada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
