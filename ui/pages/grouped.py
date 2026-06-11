"""
Paginas agrupadoras para simplificar la navegacion principal.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from ui.main_window import MainWindow


class _TabbedPage(QWidget):
    TABS: list[tuple[str, type[QWidget]]] = []

    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__()
        self.main_window = main_window
        self._pages: list[QWidget] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 18)
        layout.setSpacing(10)

        self._tabs = QTabWidget()
        self._tabs.currentChanged.connect(self._activate_current_tab)
        layout.addWidget(self._tabs, stretch=1)

        for label, PageClass in self.TABS:
            page = PageClass(self.main_window)
            self._pages.append(page)
            self._tabs.addTab(page, label)

    def on_activate(self) -> None:
        self._activate_current_tab()

    def _activate_current_tab(self, *_args) -> None:
        index = self._tabs.currentIndex()
        if 0 <= index < len(self._pages):
            page = self._pages[index]
            if hasattr(page, "on_activate"):
                page.on_activate()


class InventoryHubPage(_TabbedPage):
    from ui.pages.software_inventory import SoftwareInventoryPage
    from ui.pages.hardware_inventory import HardwareInventoryPage
    from ui.pages.departments import DepartmentsPage

    TABS = [
        ("Software", SoftwareInventoryPage),
        ("Hardware", HardwareInventoryPage),
        ("Departamentos", DepartmentsPage),
    ]


class AuditHubPage(_TabbedPage):
    from ui.pages.ens_compliance import ENSCompliancePage
    from ui.pages.data_quality import DataQualityPage

    TABS = [
        ("ENS", ENSCompliancePage),
        ("Calidad de datos", DataQualityPage),
    ]
