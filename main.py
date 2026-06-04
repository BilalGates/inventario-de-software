"""
Punto de entrada de la aplicación Inventario Asserta.
"""
from __future__ import annotations

import os
import sys

# Workaround para compatibilidad con shiboken/PySide6 en entornos PyInstaller
os.environ.setdefault("SHIBOKEN_DISABLE", "1")
os.environ.setdefault("PYDEVD_DISABLE_FILE_VALIDATION", "1")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication, QMessageBox

from ui.app import create_app


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Inventario Software Asserta")
    parser.add_argument("--init-db", action="store_true", help="Inicializa la BD y termina.")
    parser.add_argument("--import-historical", action="store_true", help="Importa Excel/CSV históricos.")
    parser.add_argument("--force-import", action="store_true", help="Fuerza la importación histórica.")
    args = parser.parse_args()

    try:
        from scripts.init_database import DatabaseInitError, setup_local_database
        setup_local_database(
            import_historical=args.import_historical,
            force_import=args.force_import,
        )
    except Exception as exc:
        app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(
            None,
            "Error de base de datos",
            f"No se pudo conectar con MySQL.\n\n{exc}",
        )
        sys.exit(1)

    if args.init_db:
        sys.exit(0)

    app = create_app(sys.argv)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
