"""
Ventana principal — sidebar izquierdo + QStackedWidget de páginas.
"""
from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from config import APP_NAME, APP_VERSION, WINDOW_MIN_HEIGHT, WINDOW_MIN_WIDTH
from ui.components.sidebar import Sidebar

# Importaciones diferidas para reducir tiempo de arranque
from ui.pages.dashboard import DashboardPage
from ui.pages.software_inventory import SoftwareInventoryPage
from ui.pages.hardware_inventory import HardwareInventoryPage
from ui.pages.ens_compliance import ENSCompliancePage
from ui.pages.data_quality import DataQualityPage
from ui.pages.departments import DepartmentsPage
from ui.pages.import_panda import ImportPandaPage
from ui.pages.settings import SettingsPage


PAGES = [
    ("dashboard",   "Inicio",              DashboardPage,          "home"),
    ("software",    "Inventario Software", SoftwareInventoryPage,  "laptop"),
    ("hardware",    "Inventario Hardware", HardwareInventoryPage,  "cpu"),
    ("ens",         "Auditoría ENS",       ENSCompliancePage,      "shield"),
    ("quality",     "Calidad de Datos",    DataQualityPage,        "chart"),
    ("departments", "Departamentos",       DepartmentsPage,        "building"),
    ("import",      "Importar Panda",      ImportPandaPage,        "upload"),
    ("settings",    "Configuración",       SettingsPage,           "settings"),
]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self._restore_geometry()
        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._stack = QStackedWidget()
        self._pages: dict[str, QWidget] = {}

        for key, label, PageClass, icon in PAGES:
            page = PageClass(self)
            self._pages[key] = page
            self._stack.addWidget(page)

        self._sidebar = Sidebar(PAGES)
        self._sidebar.page_changed.connect(self._navigate_to)

        layout.addWidget(self._sidebar)
        layout.addWidget(self._stack, stretch=1)

        self.statusBar().showMessage("Listo")

        # Navegar a la primera página y dispararle on_activate
        first_key = PAGES[0][0]
        self._navigate_to(first_key)

    def _navigate_to(self, key: str) -> None:
        if key not in self._pages:
            return
        page = self._pages[key]
        self._stack.setCurrentWidget(page)
        self._sidebar.set_active(key)
        if hasattr(page, "on_activate"):
            page.on_activate()

    def navigate_to(self, key: str) -> None:
        """API pública para que las páginas puedan navegar entre sí."""
        self._navigate_to(key)

    def set_status(self, message: str) -> None:
        self.statusBar().showMessage(message)

    def _restore_geometry(self) -> None:
        settings = QSettings("Asserta", "InventarioAsserta")
        geometry = settings.value("window/geometry")
        if geometry:
            self.restoreGeometry(geometry)

    def closeEvent(self, event) -> None:
        settings = QSettings("Asserta", "InventarioAsserta")
        settings.setValue("window/geometry", self.saveGeometry())
        super().closeEvent(event)
