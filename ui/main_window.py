from __future__ import annotations

from datetime import date

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from config import APP_NAME, APP_VERSION, WINDOW_MIN_HEIGHT, WINDOW_MIN_WIDTH
from modules.simple_inventory import current_period
from ui.components.ui_kit import FilterBar
from ui.pages.inventory import InventoryPage
from ui.pages.settings import SettingsDialog


MONTHS = [
    ("Ene", 1),
    ("Feb", 2),
    ("Mar", 3),
    ("Abr", 4),
    ("May", 5),
    ("Jun", 6),
    ("Jul", 7),
    ("Ago", 8),
    ("Sep", 9),
    ("Oct", 10),
    ("Nov", 11),
    ("Dic", 12),
]

PAGE_FACTORIES = {
    "inventory": InventoryPage,
}

NAV_ALIASES = {
    "dashboard": "inventory",
    "hardware": "inventory",
    "equipos": "inventory",
    "departments": "inventory",
    "software": "inventory",
    "monthly_v3": "inventory",
    "import": "inventory",
}


def _parts_from_period(periodo: str) -> tuple[int, int]:
    try:
        year, month = [int(part) for part in periodo.split("-", 1)]
        if 1 <= month <= 12:
            return year, month
    except (AttributeError, TypeError, ValueError):
        pass
    today = date.today()
    return today.year, today.month


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} - v{APP_VERSION}")
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self._period_change_guard = False
        self._restore_geometry()
        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._content = QWidget()
        self._content.setObjectName("Surface")
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self._stack = QStackedWidget()
        self._pages: dict[str, QWidget] = {}
        for key, PageClass in PAGE_FACTORIES.items():
            page = PageClass(self)
            self._pages[key] = page
            self._stack.addWidget(page)

        self._build_search_bar(content_layout)
        content_layout.addWidget(self._stack, stretch=1)
        root.addWidget(self._content, stretch=1)

        self.statusBar().showMessage("Listo")
        self._navigate_to("inventory")

    def _build_search_bar(self, parent_layout: QVBoxLayout) -> None:
        self._search_bar = FilterBar()
        self._search_bar.setObjectName("GlobalSearchBar")

        self._settings_btn = QPushButton("Configuracion")
        self._settings_btn.clicked.connect(self._open_settings)
        self._search_bar.add_widget(self._settings_btn)

        self._global_search = QLineEdit()
        self._global_search.setPlaceholderText("Buscar")
        self._global_search.setClearButtonEnabled(True)
        self._global_search.textChanged.connect(self._on_global_search)
        self._search_bar.add_widget(self._global_search, stretch=1)

        period_label = QLabel("Periodo")
        period_label.setObjectName("GlobalSearchLabel")
        self._search_bar.add_widget(period_label)

        self._month_combo = QComboBox()
        self._month_combo.setObjectName("GlobalPeriodCombo")
        for label, value in MONTHS:
            self._month_combo.addItem(label, value)
        self._month_combo.currentIndexChanged.connect(self._on_global_period)
        self._month_combo.setFixedWidth(76)
        self._search_bar.add_widget(self._month_combo)

        self._year_combo = QComboBox()
        self._year_combo.setObjectName("GlobalPeriodCombo")
        self._year_combo.setEditable(False)
        self._year_combo.setFixedWidth(88)
        current_year = date.today().year
        for year in range(2026, max(current_year + 75, 2101)):
            self._year_combo.addItem(str(year), year)
        self._year_combo.currentIndexChanged.connect(self._on_global_period)
        self._search_bar.add_widget(self._year_combo)

        self._set_global_period_controls(current_period())
        parent_layout.addWidget(self._search_bar)

    def _navigate_to(self, key: str, payload: dict | None = None) -> None:
        key = NAV_ALIASES.get(key, key)
        if key not in self._pages:
            return
        if payload and payload.get("periodo"):
            self._set_global_period_controls(str(payload["periodo"]))
        page = self._pages[key]
        self._stack.setCurrentWidget(page)
        if payload and hasattr(page, "apply_navigation"):
            page.apply_navigation(payload)
        elif hasattr(page, "on_activate"):
            page.on_activate()
        self._apply_global_period(page)
        self._apply_global_search(page)

    def navigate_to(self, key: str, payload: dict | None = None) -> None:
        self._navigate_to(key, payload)

    def set_status(self, message: str) -> None:
        self.statusBar().showMessage(message)

    def _open_settings(self) -> None:
        SettingsDialog(self).exec()

    def _on_global_search(self, _text: str) -> None:
        self._apply_global_search(self._stack.currentWidget())

    def _apply_global_search(self, page: QWidget | None) -> None:
        if page is not None and hasattr(page, "set_global_search"):
            page.set_global_search(self._global_search.text())

    def _on_global_period(self, _index=None) -> None:
        if self._period_change_guard:
            return
        self._apply_global_period(self._stack.currentWidget())

    def _apply_global_period(self, page: QWidget | None) -> None:
        if page is not None and hasattr(page, "set_period"):
            page.set_period(self._period_from_controls())

    def _period_from_controls(self) -> str:
        year = int(self._year_combo.currentData() or date.today().year)
        year = max(year, 2026)
        month = int(self._month_combo.currentData() or date.today().month)
        return f"{year:04d}-{month:02d}"

    def _set_global_period_controls(self, periodo: str) -> None:
        year, month = _parts_from_period(periodo)
        self._period_change_guard = True
        for index in range(self._month_combo.count()):
            if self._month_combo.itemData(index) == month:
                self._month_combo.setCurrentIndex(index)
                break
        year_index = self._year_combo.findData(year)
        if year_index == -1:
            self._year_combo.addItem(str(year), year)
            self._year_combo.model().sort(0)
            year_index = self._year_combo.findData(year)
        if year_index >= 0:
            self._year_combo.setCurrentIndex(year_index)
        self._period_change_guard = False

    def _restore_geometry(self) -> None:
        settings = QSettings("Asserta", "InventarioAsserta")
        geometry = settings.value("window/geometry")
        if geometry:
            self.restoreGeometry(geometry)

    def closeEvent(self, event) -> None:
        settings = QSettings("Asserta", "InventarioAsserta")
        settings.setValue("window/geometry", self.saveGeometry())
        super().closeEvent(event)
