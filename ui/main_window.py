"""
Ventana principal: sidebar agrupado por tareas + páginas planas en un QStackedWidget.
"""
from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QStackedWidget, QWidget

from config import APP_NAME, APP_VERSION, WINDOW_MIN_HEIGHT, WINDOW_MIN_WIDTH
from ui.components.sidebar import Sidebar
from ui.pages.dashboard import DashboardPage
from ui.pages.data_quality import DataQualityPage
from ui.pages.departments import DepartmentsPage
from ui.pages.ens_compliance import ENSCompliancePage
from ui.pages.hardware_inventory import HardwareInventoryPage
from ui.pages.historial import HistorialImportacionesPage
from ui.pages.import_panda import ImportPandaPage
from ui.pages.reactivaciones import ReactivacionesPage
from ui.pages.review_center import ReviewCenterPage
from ui.pages.settings import SettingsPage
from ui.pages.software_autorizado import SoftwareAutorizadoPage
from ui.pages.software_inventory import SoftwareInventoryPage


# Navegación agrupada por tareas: (grupo | None, [(key, etiqueta, icono)])
NAV_GROUPS = [
    (None, [("dashboard", "Inicio", "home")]),
    ("Inventario", [
        ("software", "Software", "software"),
        ("equipos", "Equipos", "device"),
        ("departments", "Departamentos", "departments"),
    ]),
    ("Control", [
        ("autorizado", "Software autorizado", "shield"),
        ("reactivaciones", "Reactivaciones", "refresh"),
        ("review", "Centro de revisión", "inbox"),
    ]),
    ("Importación", [
        ("import", "Importar Panda", "upload"),
        ("historial", "Historial", "clock"),
    ]),
    ("Auditoría", [
        ("ens", "ENS / Guía 105", "audit"),
        ("quality", "Calidad de datos", "database"),
    ]),
    ("Administración", [
        ("settings", "Configuración", "settings"),
    ]),
]

PAGE_FACTORIES = {
    "dashboard": DashboardPage,
    "software": SoftwareInventoryPage,
    "equipos": HardwareInventoryPage,
    "departments": DepartmentsPage,
    "autorizado": SoftwareAutorizadoPage,
    "reactivaciones": ReactivacionesPage,
    "review": ReviewCenterPage,
    "import": ImportPandaPage,
    "historial": HistorialImportacionesPage,
    "ens": ENSCompliancePage,
    "quality": DataQualityPage,
    "settings": SettingsPage,
}

# Alias para navegación interna entre páginas (compatibilidad con claves antiguas).
NAV_ALIASES = {
    "hardware": "equipos",
    "inventory": "software",
    "audit": "ens",
}


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} · v{APP_VERSION}")
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
        for key, PageClass in PAGE_FACTORIES.items():
            page = PageClass(self)
            self._pages[key] = page
            self._stack.addWidget(page)

        self._sidebar = Sidebar(NAV_GROUPS)
        self._sidebar.page_changed.connect(self._navigate_to)

        layout.addWidget(self._sidebar)
        layout.addWidget(self._stack, stretch=1)

        self.statusBar().showMessage("Listo")
        self._navigate_to("dashboard")

    def _navigate_to(self, key: str, payload: dict | None = None) -> None:
        key = NAV_ALIASES.get(key, key)
        if key not in self._pages:
            return
        page = self._pages[key]
        self._stack.setCurrentWidget(page)
        self._sidebar.set_active(key)
        if hasattr(page, "on_activate"):
            page.on_activate()
        if payload and hasattr(page, "apply_navigation"):
            page.apply_navigation(payload)

    def navigate_to(self, key: str, payload: dict | None = None) -> None:
        """API pública para que las páginas naveguen entre sí (con filtros opcionales)."""
        self._navigate_to(key, payload)

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
