from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from database.connection import get_engine
from modules.software import listar_departamentos_con_estadisticas

if TYPE_CHECKING:
    from pyside_app.main_window import MainWindow


DEPT_PAGE_MAP = {
    "gerencia": "dept_gerencia",
    "it": "dept_it",
    "silicon": "dept_silicon",
    "data_science": "dept_data_science",
    "administracion": "dept_administracion",
    "servidores": "dept_servidores",
}


class InventarioIndexPage(QWidget):
    def __init__(self, main_window: MainWindow) -> None:
        super().__init__()
        self.main_window = main_window
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Inventario de Software")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        subtitle = QLabel("Selecciona un departamento para ver su inventario")
        subtitle.setStyleSheet("color: #666; font-size: 10pt;")
        layout.addWidget(subtitle)

        self.cards_grid = QGridLayout()
        self.cards_grid.setSpacing(16)
        layout.addLayout(self.cards_grid)

        layout.addStretch()

    def on_activate(self) -> None:
        self._load_departments()

    def _load_departments(self) -> None:
        try:
            with get_engine().connect() as db:
                dept_list = listar_departamentos_con_estadisticas(db)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"No se pudo conectar:\n{exc}")
            return

        while self.cards_grid.count():
            child = self.cards_grid.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for i, dept in enumerate(dept_list):
            card = self._create_dept_card(dept)
            row, col = divmod(i, 3)
            self.cards_grid.addWidget(card, row, col)

    def _create_dept_card(self, dept: dict) -> QWidget:
        card = QWidget()
        card.setFixedSize(300, 140)
        card.setStyleSheet("""
            QWidget {
                background: white;
                border: 1px solid #ddd;
                border-radius: 8px;
            }
            QWidget:hover {
                border: 2px solid #0f3460;
            }
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)

        name_label = QLabel(dept["nombre"])
        name_font = QFont()
        name_font.setPointSize(13)
        name_font.setBold(True)
        name_label.setFont(name_font)
        layout.addWidget(name_label)

        stats_label = QLabel(
            f"{dept['n_equipos']} dispositivos  ·  {dept['n_software']} software"
        )
        stats_label.setStyleSheet("color: #666; font-size: 9pt;")
        layout.addWidget(stats_label)

        layout.addStretch()

        btn = QPushButton("Abrir inventario")
        btn.setStyleSheet("""
            QPushButton {
                background: #0f3460;
                color: white;
                padding: 6px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background: #1a5276; }
        """)
        codigo = dept["codigo"]
        page_key = DEPT_PAGE_MAP.get(codigo)
        if page_key:
            btn.clicked.connect(lambda checked=False, pk=page_key: self.main_window.navigate_to(pk))
        layout.addWidget(btn)

        return card
