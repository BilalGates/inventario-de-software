"""
Backup de la base de datos MySQL a un fichero .sql con marca de tiempo.

Usa `mysqldump` (debe estar en el PATH) y la configuración de `.env`.
El dump se genera con `--databases`, por lo que es autocontenido (incluye
CREATE DATABASE / USE) y puede restaurarse con `scripts/restore_db.py`.

Uso:
  python scripts/backup_db.py                 # -> backups/<db>_<timestamp>.sql
  python scripts/backup_db.py --out-dir ruta
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import DB_CONFIG


def backup(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = out_dir / f"{DB_CONFIG['database']}_{timestamp}.sql"

    cmd = [
        "mysqldump",
        "-h", str(DB_CONFIG["host"]),
        "-P", str(DB_CONFIG["port"]),
        "-u", str(DB_CONFIG["user"]),
        "--single-transaction",
        "--routines",
        "--default-character-set=utf8mb4",
        "--databases", str(DB_CONFIG["database"]),
    ]
    env = dict(os.environ)
    if DB_CONFIG["password"]:
        env["MYSQL_PWD"] = str(DB_CONFIG["password"])  # evita exponer la clave en la línea de comandos

    with target.open("wb") as handle:
        subprocess.run(cmd, check=True, stdout=handle, env=env)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup de la BD a un fichero .sql con timestamp.")
    parser.add_argument("--out-dir", default=str(ROOT / "backups"), help="Directorio de salida (por defecto: backups/).")
    args = parser.parse_args()

    try:
        path = backup(Path(args.out_dir))
    except FileNotFoundError:
        print("No se encontró 'mysqldump' en el PATH. Instala el cliente de MySQL.", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"mysqldump falló (código {exc.returncode}).", file=sys.stderr)
        return 1

    print(f"Backup creado: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
