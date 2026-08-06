"""
Configuración de QApplication y arranque de la ventana principal.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from config import APP_ICON, APP_NAME
from ui.theme import apply_theme


def create_app(argv: list) -> QApplication:
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("Asserta")
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)
    if APP_ICON.exists():
        # Se hereda en la ventana principal, los dialogos y la barra de tareas.
        app.setWindowIcon(QIcon(str(APP_ICON)))
    apply_theme(app)

    from ui.main_window import MainWindow
    window = MainWindow()
    window.show()
    return app
