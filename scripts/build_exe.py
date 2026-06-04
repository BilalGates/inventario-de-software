"""
Script de compilación a ejecutable Windows con PyInstaller.
Uso: python scripts/build_exe.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def build() -> None:
    icon_path = ROOT / "resources" / "icons" / "app.ico"
    icon_flag = f"--icon={icon_path}" if icon_path.exists() else []

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "InventarioAsserta",
        "--onedir",
        "--windowed",
        "--clean",
        "--noconfirm",
        f"--add-data={ROOT / 'resources'}{os.pathsep}resources",
        f"--add-data={ROOT / 'database'}{os.pathsep}database",
        f"--add-data={ROOT / 'migrations'}{os.pathsep}migrations",
        f"--add-data={ROOT / '.env'}{os.pathsep}.",
        "--hidden-import=pymysql",
        "--hidden-import=sqlalchemy.dialects.mysql",
        "--hidden-import=PySide6.QtSvg",
    ]

    if isinstance(icon_flag, str):
        cmd.append(icon_flag)
    elif icon_flag:
        cmd.append(icon_flag)

    cmd.append(str(ROOT / "main.py"))

    print("Compilando InventarioAsserta...")
    subprocess.run(cmd, check=True, cwd=ROOT)
    print(f"\nBuild completado: {ROOT / 'dist' / 'InventarioAsserta'}")


if __name__ == "__main__":
    build()
