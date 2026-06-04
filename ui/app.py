"""
Configuración de QApplication y arranque de la ventana principal.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from config import APP_NAME
from ui.theme import apply_theme


def create_app(argv: list) -> QApplication:
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("Asserta")
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)
    apply_theme(app)

    from ui.main_window import MainWindow
    window = MainWindow()
    window.show()
    return app
