from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from database.connection import get_engine
from modules.autorizado import autorizar_softwares
from modules.software import (
    actualizar_fabricante,
    fabricantes_vacios,
    software_comun_no_autorizado,
    versiones_sospechosas,
)

from pyside_app.widgets.data_table import DataTable

if TYPE_CHECKING:
    from pyside_app.main_window import MainWindow


class CalidadDatosPage(QWidget):
    def __init__(self, main_window: MainWindow) -> None:
        super().__init__()
        self.main_window = main_window
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("Calidad de Datos")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.versiones_tab = QWidget()
        self.fabricantes_tab = QWidget()
        self.comun_tab = QWidget()

        self.tabs.addTab(self.versiones_tab, "Versiones sospechosas")
        self.tabs.addTab(self.fabricantes_tab, "Fabricantes vacios")
        self.tabs.addTab(self.comun_tab, "Software comun no autorizado")

        self._setup_versiones_tab()
        self._setup_fabricantes_tab()
        self._setup_comun_tab()

    def _setup_versiones_tab(self) -> None:
        layout = QVBoxLayout(self.versiones_tab)
        layout.setContentsMargins(16, 16, 16, 16)
        self.versiones_table = DataTable()
        layout.addWidget(self.versiones_table)
        self.refresh_versiones_btn = QPushButton("Actualizar")
        self.refresh_versiones_btn.clicked.connect(self._load_versiones)
        layout.addWidget(self.refresh_versiones_btn)

    def _setup_fabricantes_tab(self) -> None:
        layout = QVBoxLayout(self.fabricantes_tab)
        layout.setContentsMargins(16, 16, 16, 16)
        self.fabricantes_table = DataTable()
        layout.addWidget(self.fabricantes_table)

        edit_layout = QHBoxLayout()
        edit_layout.addWidget(QLabel("ID Software:"))
        self.fabricante_id_input = QLineEdit()
        edit_layout.addWidget(self.fabricante_id_input)
        edit_layout.addWidget(QLabel("Nuevo fabricante:"))
        self.fabricante_value_input = QLineEdit()
        edit_layout.addWidget(self.fabricante_value_input, stretch=1)
        self.save_fabricante_btn = QPushButton("Guardar")
        self.save_fabricante_btn.clicked.connect(self._save_fabricante)
        edit_layout.addWidget(self.save_fabricante_btn)
        layout.addLayout(edit_layout)

        self.refresh_fabricantes_btn = QPushButton("Actualizar")
        self.refresh_fabricantes_btn.clicked.connect(self._load_fabricantes)
        layout.addWidget(self.refresh_fabricantes_btn)

    def _setup_comun_tab(self) -> None:
        layout = QVBoxLayout(self.comun_tab)
        layout.setContentsMargins(16, 16, 16, 16)
        self.comun_table = DataTable()
        layout.addWidget(self.comun_table)

        self.auth_comun_btn = QPushButton("Autorizar software seleccionado")
        self.auth_comun_btn.setStyleSheet("""
            QPushButton { background: #27ae60; color: white; padding: 8px 16px;
                          border: none; border-radius: 4px; font-weight: bold; }
        """)
        self.auth_comun_btn.clicked.connect(self._autorizar_comun)
        layout.addWidget(self.auth_comun_btn)

        self.refresh_comun_btn = QPushButton("Actualizar")
        self.refresh_comun_btn.clicked.connect(self._load_comun)
        layout.addWidget(self.refresh_comun_btn)

    def on_activate(self) -> None:
        self._load_versiones()
        self._load_fabricantes()
        self._load_comun()

    def _load_versiones(self) -> None:
        try:
            with get_engine().connect() as db:
                rows = versiones_sospechosas(db)
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return
        data = []
        for row in rows:
            data.append({
                "id": row["id"],
                "Nombre": row["nombre"],
                "Version": row.get("version_referencia") or "",
                "Fabricante": row.get("fabricante") or "",
            })
        self.versiones_table.load_data(data, ["Nombre", "Version", "Fabricante"])

    def _load_fabricantes(self) -> None:
        try:
            with get_engine().connect() as db:
                rows = fabricantes_vacios(db)
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return
        data = []
        for row in rows:
            data.append({
                "id": row["id"],
                "Nombre": row["nombre"],
                "Version": row.get("version_referencia") or "",
            })
        self.fabricantes_table.load_data(data, ["Nombre", "Version"])

    def _save_fabricante(self) -> None:
        sw_id = self.fabricante_id_input.text().strip()
        fabricante = self.fabricante_value_input.text().strip()
        if not sw_id or not sw_id.isdigit():
            QMessageBox.warning(self, "Error", "Introduce un ID de software valido")
            return
        with get_engine().begin() as db:
            actualizar_fabricante(db, int(sw_id), fabricante or None)
        QMessageBox.information(self, "Guardado", "Fabricante actualizado.")
        self.fabricante_id_input.clear()
        self.fabricante_value_input.clear()
        self._load_fabricantes()

    def _load_comun(self) -> None:
        try:
            with get_engine().connect() as db:
                rows = software_comun_no_autorizado(db)
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return
        data = []
        for row in rows:
            data.append({
                "software_id": row["software_id"],
                "Nombre": row["nombre"],
                "N departamentos": str(row["n_departamentos"]),
            })
        self.comun_table.load_data(data, ["Nombre", "N departamentos"])
        self._comun_data = rows

    def _autorizar_comun(self) -> None:
        if not hasattr(self, "_comun_data") or not self._comun_data:
            QMessageBox.warning(self, "Error", "No hay software para autorizar")
            return
        reply = QMessageBox.question(
            self,
            "Confirmar",
            f"Se autorizaran {len(self._comun_data)} programas.\nContinuar?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            with get_engine().begin() as db:
                inserted = autorizar_softwares(
                    db,
                    [item["software_id"] for item in self._comun_data],
                    "Autorizado automaticamente: comun en mas de 3 departamentos",
                )
            QMessageBox.information(self, "Hecho", f"Software autorizado: {inserted}")
            self._load_comun()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
