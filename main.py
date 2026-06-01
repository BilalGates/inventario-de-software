from __future__ import annotations

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shiboken_compat import apply as apply_shiboken_compat

apply_shiboken_compat()

from PySide6.QtWidgets import QApplication, QMessageBox
from pyside_app.main_window import MainWindow
from scripts.init_database import DatabaseInitError, setup_local_database


def main() -> None:
    parser = argparse.ArgumentParser(description="Inventario Software Asserta")
    parser.add_argument("--init-db", action="store_true", help="Inicializa la base de datos y termina.")
    parser.add_argument("--import-historical", action="store_true", help="Importa Excel/CSV historicos si la base esta vacia.")
    parser.add_argument("--force-import", action="store_true", help="Fuerza la importacion historica.")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setApplicationName("Inventario Software Asserta")
    app.setOrganizationName("Asserta")

    try:
        setup_local_database(import_historical=args.import_historical, force_import=args.force_import)
    except DatabaseInitError as exc:
        QMessageBox.critical(
            None,
            "Error de base de datos",
            f"No se pudo conectar con MySQL local.\n\n{exc}",
        )
        sys.exit(1)

    if args.init_db:
        sys.exit(0)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
