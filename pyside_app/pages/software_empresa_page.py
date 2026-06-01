from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from database.connection import get_engine
from modules.equipos import listar_equipos
from modules.software import listar_departamentos, listar_inventario_empresa

from pyside_app.widgets.data_table import DataTable

if TYPE_CHECKING:
    from pyside_app.main_window import MainWindow


class SoftwareEmpresaPage(QWidget):
    def __init__(self, main_window: MainWindow) -> None:
        super().__init__()
        self.main_window = main_window
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("Software de la Empresa")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Departamentos:"))
        self.dept_combo = QComboBox()
        self.dept_combo.addItem("Todos", None)
        filter_layout.addWidget(self.dept_combo)

        filter_layout.addWidget(QLabel("Dispositivo:"))
        self.equipo_combo = QComboBox()
        self.equipo_combo.addItem("Todos", None)
        filter_layout.addWidget(self.equipo_combo)

        self.solo_comun_check = QCheckBox("Solo comun (>1 depto)")

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar...")
        filter_layout.addWidget(self.search_input, stretch=1)

        self.filter_btn = QPushButton("Filtrar")
        self.filter_btn.clicked.connect(self._load_data)
        filter_layout.addWidget(self.filter_btn)
        layout.addLayout(filter_layout)

        self.vista_basica_btn = QPushButton("Basica")
        self.vista_detallada_btn = QPushButton("Detallada")
        for btn in (self.vista_basica_btn, self.vista_detallada_btn):
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton { padding: 4px 12px; border: 1px solid #ccc; border-radius: 4px; }
                QPushButton:checked { background: #0f3460; color: white; border-color: #0f3460; }
            """)
        self.vista_basica_btn.setChecked(True)
        self.vista_basica_btn.clicked.connect(lambda: self._set_vista("basica"))
        self.vista_detallada_btn.clicked.connect(lambda: self._set_vista("detallada"))

        view_layout = QHBoxLayout()
        view_layout.addWidget(self.vista_basica_btn)
        view_layout.addWidget(self.vista_detallada_btn)
        view_layout.addStretch()
        layout.addLayout(view_layout)

        self.table = DataTable()
        layout.addWidget(self.table, stretch=1)

        self.vista = "basica"

    def _set_vista(self, vista: str) -> None:
        self.vista = vista
        self.vista_basica_btn.setChecked(vista == "basica")
        self.vista_detallada_btn.setChecked(vista == "detallada")
        self._load_data()

    def on_activate(self) -> None:
        try:
            with get_engine().connect() as db:
                depts = listar_departamentos(db)
                self.dept_combo.clear()
                self.dept_combo.addItem("Todos", None)
                for dept in depts:
                    self.dept_combo.addItem(dept["nombre"], dept["id"])

                equipos = listar_equipos(db, solo_activos=True)
                self.equipo_combo.clear()
                self.equipo_combo.addItem("Todos", None)
                for eq in equipos:
                    self.equipo_combo.addItem(f"{eq['nombre']} ({eq['departamento_nombre']})", eq["id"])
        except Exception:
            pass
        self._load_data()

    def _load_data(self) -> None:
        try:
            with get_engine().connect() as db:
                dept_id = self.dept_combo.currentData()
                departamento_ids = [dept_id] if dept_id else None
                equipo_id = self.equipo_combo.currentData()
                equipo_ids = [equipo_id] if equipo_id else None

                rows = listar_inventario_empresa(
                    db,
                    departamento_ids=departamento_ids,
                    equipo_ids=equipo_ids,
                    solo_comun=self.solo_comun_check.isChecked(),
                    texto_libre=self.search_input.text().strip() or None,
                )
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        if not rows:
            self.table.load_data([])
            return

        base_cols = ["nombre", "fabricantes", "versiones", "departamentos"]
        detail_cols = ["dispositivos", "clasificaciones", "observaciones"]
        display_keys = base_cols + (detail_cols if self.vista == "detallada" else [])

        header_map = {
            "nombre": "Software",
            "fabricantes": "Fabricantes",
            "versiones": "Versiones",
            "departamentos": "Departamentos",
            "dispositivos": "Dispositivos",
            "clasificaciones": "Clasificacion",
            "observaciones": "Observaciones",
        }

        def fmt_en_guia(val):
            if val is None:
                return "Pendiente"
            return "Si" if val else "No"

        data = []
        for row in rows:
            entry = {}
            for key in display_keys:
                val = row.get(key, "")
                if key == "en_guia_105":
                    val = fmt_en_guia(val)
                entry[header_map[key]] = str(val) if val is not None else ""
            data.append(entry)

        self.table.load_data(data, [header_map[k] for k in display_keys])
