"""
Calidad de datos — validaciones y detección de anomalías.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.components.sortable_table import SortableTable
from ui.components.worker import run_in_thread
from ui.theme import COLORS

if TYPE_CHECKING:
    from ui.main_window import MainWindow


def _fetch_quality_data():
    from database.connection import get_engine
    from modules.software import (
        versiones_sospechosas,
        fabricantes_vacios,
        contar_software_sin_dispositivos,
    )
    with get_engine().connect() as db:
        versiones = versiones_sospechosas(db)
        fabricantes = fabricantes_vacios(db)
        sin_disp = contar_software_sin_dispositivos(db)
    return {
        "versiones_sospechosas": versiones,
        "fabricantes_vacios": fabricantes,
        "sin_dispositivos": sin_disp,
    }


HEADERS_SW = ["ID", "Nombre", "Versión", "Fabricante"]
KEYS_SW    = ["id", "nombre", "version_referencia", "fabricante"]


class DataQualityPage(QWidget):
    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__()
        self.main_window = main_window
        self._thread = None
        self._build_ui()

    def _build_ui(self) -> None:
        c = COLORS
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        hdr = QHBoxLayout()
        title = QLabel("Calidad de Datos")
        title.setObjectName("labelTitle")
        hdr.addWidget(title)
        hdr.addStretch()
        self._refresh_btn = QPushButton("Actualizar")
        self._refresh_btn.clicked.connect(self._load_data)
        hdr.addWidget(self._refresh_btn)
        layout.addLayout(hdr)

        # Bloque versiones sospechosas
        v_label = QLabel("Versiones sospechosas (nulas, muy cortas o con caracteres raros)")
        v_label.setObjectName("labelSection")
        layout.addWidget(v_label)
        self._v_count = QLabel("—")
        self._v_count.setObjectName("labelSecondary")
        layout.addWidget(self._v_count)
        self._v_table = SortableTable(headers=HEADERS_SW, keys=KEYS_SW)
        self._v_table.setFixedHeight(180)
        layout.addWidget(self._v_table)

        # Bloque fabricantes vacíos
        f_label = QLabel("Software sin fabricante asignado")
        f_label.setObjectName("labelSection")
        layout.addWidget(f_label)
        self._f_count = QLabel("—")
        self._f_count.setObjectName("labelSecondary")
        layout.addWidget(self._f_count)
        self._f_table = SortableTable(headers=HEADERS_SW, keys=KEYS_SW)
        self._f_table.setFixedHeight(180)
        layout.addWidget(self._f_table)

        # Bloque sin dispositivos
        d_label = QLabel("Software activo sin dispositivos asignados (huérfanos)")
        d_label.setObjectName("labelSection")
        layout.addWidget(d_label)

        HDRS_DEPT = ["Departamento", "Registros huérfanos"]
        KEYS_DEPT = ["departamento", "total"]
        self._d_table = SortableTable(headers=HDRS_DEPT, keys=KEYS_DEPT)
        self._d_table.setFixedHeight(160)
        layout.addWidget(self._d_table)
        layout.addStretch()

    def on_activate(self) -> None:
        self._load_data()

    def _load_data(self) -> None:
        self._refresh_btn.setEnabled(False)
        self._thread = run_in_thread(self, _fetch_quality_data,
                                     on_done=self._on_data_loaded, on_error=self._on_error)

    def _on_data_loaded(self, result: dict) -> None:
        self._refresh_btn.setEnabled(True)
        c = COLORS

        versiones = result["versiones_sospechosas"]
        self._v_count.setText(f"{len(versiones)} registros")
        for r in versiones:
            r["version_referencia"] = str(r.get("version_referencia") or "")
        self._v_table.load_data(versiones)

        fabricantes = result["fabricantes_vacios"]
        self._f_count.setText(f"{len(fabricantes)} registros")
        for r in fabricantes:
            r["version_referencia"] = str(r.get("version_referencia") or "")
        self._f_table.load_data(fabricantes)

        sin_disp = result["sin_dispositivos"]
        self._d_table.load_data([{"departamento": r["departamento"], "total": str(r["total"])} for r in sin_disp])

    def _on_error(self, msg: str) -> None:
        self._refresh_btn.setEnabled(True)
        QMessageBox.critical(self, "Error", f"Error en calidad de datos:\n{msg}")
