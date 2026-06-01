from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from pyside_app.pages.dashboard_page import DashboardPage
from pyside_app.pages.inventario_index_page import InventarioIndexPage
from pyside_app.pages.departamento_page import DepartamentoPage
from pyside_app.pages.estado_importaciones_page import EstadoImportacionesPage
from pyside_app.pages.software_empresa_page import SoftwareEmpresaPage
from pyside_app.pages.calidad_datos_page import CalidadDatosPage
from pyside_app.pages.equipos_page import EquiposPage
from pyside_app.pages.software_autorizado_page import SoftwareAutorizadoPage


NAV_ITEMS = [
    ("Inicio", "Dashboard"),
    ("Inventario de software", None),
    ("  Resumen", "inventario_index"),
    ("  Direccion", "dept_gerencia"),
    ("  IT", "dept_it"),
    ("  Silicon", "dept_silicon"),
    ("  Data Science", "dept_data_science"),
    ("  Administracion", "dept_administracion"),
    ("  Servidores", "dept_servidores"),
    ("Gestion", None),
    ("  Estado Importaciones", "estado_importaciones"),
    ("  Software Empresa", "software_empresa"),
    ("  Calidad Datos", "calidad_datos"),
    ("  Equipos", "equipos"),
    ("  Software Autorizado", "software_autorizado"),
]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Inventario Software Asserta")
        self.resize(1400, 900)

        self.stack = QStackedWidget()
        self.nav_list = QListWidget()
        self.pages: dict[str, int] = {}

        self._setup_ui()
        self._create_pages()
        self._populate_nav()

        self.nav_list.currentRowChanged.connect(self._on_nav_changed)
        self.nav_list.setCurrentRow(1)

        self.statusBar().showMessage("Conectado a MySQL")

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)

        nav_widget = QWidget()
        nav_layout = QVBoxLayout(nav_widget)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(0)

        title = QLabel("Inventario Software")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(11)
        title.setFont(title_font)
        title.setStyleSheet("padding: 12px; background: #1a1a2e; color: white;")
        title.setFixedHeight(48)
        nav_layout.addWidget(title)

        self.nav_list.setStyleSheet("""
            QListWidget {
                background: #16213e;
                color: #ccc;
                border: none;
                font-size: 10pt;
                outline: none;
            }
            QListWidget::item {
                padding: 8px 12px;
                border-bottom: 1px solid #1a1a2e;
            }
            QListWidget::item:selected {
                background: #0f3460;
                color: white;
            }
            QListWidget::item:hover:!selected {
                background: #1a1a2e;
            }
        """)
        self.nav_list.setFixedWidth(220)
        nav_layout.addWidget(self.nav_list)

        splitter.addWidget(nav_widget)

        self.stack.setStyleSheet("background: #f5f5f5;")
        splitter.addWidget(self.stack)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([220, 1180])

        layout.addWidget(splitter)

    def _populate_nav(self) -> None:
        for label, page_key in NAV_ITEMS:
            item = QListWidgetItem(label)
            if page_key is None:
                item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
                item.setForeground(Qt.gray)
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            else:
                item.setData(Qt.UserRole, page_key)
            self.nav_list.addItem(item)

    def _create_pages(self) -> None:
        def add_page(widget: QWidget, key: str) -> None:
            self.pages[key] = self.stack.addWidget(widget)

        add_page(DashboardPage(self), "dashboard")
        add_page(InventarioIndexPage(self), "inventario_index")
        add_page(DepartamentoPage(self, "gerencia"), "dept_gerencia")
        add_page(DepartamentoPage(self, "it"), "dept_it")
        add_page(DepartamentoPage(self, "silicon"), "dept_silicon")
        add_page(DepartamentoPage(self, "data_science"), "dept_data_science")
        add_page(DepartamentoPage(self, "administracion"), "dept_administracion")
        add_page(DepartamentoPage(self, "servidores"), "dept_servidores")
        add_page(EstadoImportacionesPage(self), "estado_importaciones")
        add_page(SoftwareEmpresaPage(self), "software_empresa")
        add_page(CalidadDatosPage(self), "calidad_datos")
        add_page(EquiposPage(self), "equipos")
        add_page(SoftwareAutorizadoPage(self), "software_autorizado")

    def _on_nav_changed(self, row: int) -> None:
        item = self.nav_list.item(row)
        if not item:
            return
        page_key = item.data(Qt.UserRole)
        if page_key is None:
            return
        index = self.pages.get(page_key)
        if index is not None:
            self.stack.setCurrentIndex(index)
            page_widget = self.stack.widget(index)
            if hasattr(page_widget, "on_activate"):
                page_widget.on_activate()

    def navigate_to(self, page_key: str) -> None:
        for row in range(self.nav_list.count()):
            item = self.nav_list.item(row)
            if item and item.data(Qt.UserRole) == page_key:
                self.nav_list.blockSignals(True)
                self.nav_list.setCurrentRow(row)
                self.nav_list.blockSignals(False)
                index = self.pages.get(page_key)
                if index is not None:
                    self.stack.setCurrentIndex(index)
                    page_widget = self.stack.widget(index)
                    if hasattr(page_widget, "on_activate"):
                        page_widget.on_activate()
                break
