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


def _prewarm_imports() -> None:
    """
    Pre-importa módulos pesados ANTES de que Qt empiece.

    SQLAlchemy, pandas y los módulos de negocio son grandes (~8s en primera importación).
    Si se importan desde un worker thread mientras el event loop Qt corre, el GIL
    y el import lock causan contención de 3-8s adicionales por módulo.

    Importar aquí (hilo principal, antes de QApplication) elimina esa contención.
    Los imports posteriores en los workers son instantáneos (sys.modules ya los tiene).
    """
    try:
        # Parchear shiboken/six antes de importar pandas o dateutil
        import six
        importer = getattr(six, "_importer", None)
        if importer is not None and not hasattr(importer, "_path"):
            importer._path = []
    except ImportError:
        pass

    try:
        import sqlalchemy                    # noqa — motor ORM
        from database.connection import get_engine
        get_engine()                         # inicializar pool de conexiones

        import modules.software              # noqa
        import modules.equipos               # noqa
        import modules.importacion           # noqa
        import modules.autorizado            # noqa
        import modules.exportacion           # noqa
        import utils.normalizer              # noqa
        import utils.parser                  # noqa — importa pandas/openpyxl
    except Exception:
        pass  # No crítico — si falla aquí, el error real se muestra después


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Inventario Software Asserta")
    parser.add_argument("--init-db", action="store_true", help="Inicializa la BD y termina.")
    parser.add_argument("--import-historical", action="store_true", help="Importa Excel/CSV históricos.")
    parser.add_argument("--force-import", action="store_true", help="Fuerza la importación histórica.")
    args = parser.parse_args()

    # Pre-importar módulos pesados ANTES de arrancar Qt para evitar import lock
    # contention en los worker threads
    _prewarm_imports()

    from PySide6.QtWidgets import QApplication, QMessageBox

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

    from ui.app import create_app
    app = create_app(sys.argv)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
