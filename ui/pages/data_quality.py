"""
Calidad de datos: anomalías por tipo, cada una con acción recomendada.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from ui.components.metric_card import MetricCard, MetricRow
from ui.components.sortable_table import SortableTable
from ui.components.ui_kit import FeedbackBar, PageHeader
from ui.components.worker import run_in_thread

if TYPE_CHECKING:
    from ui.main_window import MainWindow


def _fetch_quality_data():
    from database.connection import get_engine
    from modules.software import (
        contar_software_sin_dispositivos,
        fabricantes_vacios,
        versiones_sospechosas,
    )
    with get_engine().connect() as db:
        versiones = versiones_sospechosas(db)
        fabricantes = fabricantes_vacios(db)
        sin_disp = contar_software_sin_dispositivos(db)
    return {"versiones": versiones, "fabricantes": fabricantes, "sin_disp": sin_disp}


HEADERS_SW = ["Nombre", "Versión", "Fabricante"]
KEYS_SW = ["nombre", "version_referencia", "fabricante"]


class DataQualityPage(QWidget):
    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__()
        self.main_window = main_window
        self._thread = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        self._refresh_btn = QPushButton("Actualizar")
        self._refresh_btn.clicked.connect(self._load_data)
        header = PageHeader("Calidad de datos", "Anomalías a corregir para mantener un inventario fiable.")
        header.add_action(self._refresh_btn)
        layout.addWidget(header)

        self._feedback = FeedbackBar()
        layout.addWidget(self._feedback)

        kpis = MetricRow()
        self._k_versiones = MetricCard("Versiones sospechosas", "—")
        self._k_fabricantes = MetricCard("Sin fabricante", "—")
        self._k_huerfanos = MetricCard("Software huérfano", "—")
        for c in (self._k_versiones, self._k_fabricantes, self._k_huerfanos):
            kpis.add_card(c)
        kpis.add_stretch()
        layout.addWidget(kpis)

        layout.addWidget(self._section_label("Versiones sospechosas — revisa y corrige el texto de versión"))
        self._v_table = SortableTable(headers=HEADERS_SW, keys=KEYS_SW)
        self._v_table.set_empty_content(title="Sin anomalías", message="Las versiones tienen un formato razonable.", icon="✓")
        self._v_table.setMinimumHeight(150)
        layout.addWidget(self._v_table)

        layout.addWidget(self._section_label("Software sin fabricante — completa el editor/proveedor"))
        self._f_table = SortableTable(headers=HEADERS_SW, keys=KEYS_SW)
        self._f_table.set_empty_content(title="Sin anomalías", message="Todo el software tiene fabricante.", icon="✓")
        self._f_table.setMinimumHeight(150)
        layout.addWidget(self._f_table)

        layout.addWidget(self._section_label("Software activo sin dispositivos — revisa en cada departamento"))
        self._d_table = SortableTable(headers=["Departamento", "Registros huérfanos"], keys=["departamento", "total"])
        self._d_table.set_empty_content(title="Sin huérfanos", message="No hay software activo sin dispositivos.", icon="✓")
        self._d_table.setMinimumHeight(130)
        layout.addWidget(self._d_table)
        layout.addStretch()

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("labelSection")
        return lbl

    def on_activate(self) -> None:
        self._load_data()

    def _load_data(self) -> None:
        self._refresh_btn.setEnabled(False)
        self._feedback.show_message("Analizando calidad de datos...", "info")
        self._thread = run_in_thread(self, _fetch_quality_data, on_done=self._on_data_loaded, on_error=self._on_error)

    def _on_data_loaded(self, result: dict) -> None:
        self._refresh_btn.setEnabled(True)

        versiones = result["versiones"]
        for r in versiones:
            r["version_referencia"] = str(r.get("version_referencia") or "")
        self._v_table.load_data(versiones)
        self._k_versiones.update_value(len(versiones), tone="warning" if versiones else "success")

        fabricantes = result["fabricantes"]
        for r in fabricantes:
            r["version_referencia"] = str(r.get("version_referencia") or "")
        self._f_table.load_data(fabricantes)
        self._k_fabricantes.update_value(len(fabricantes), tone="warning" if fabricantes else "success")

        sin_disp = result["sin_disp"]
        self._d_table.load_data([{"departamento": r["departamento"], "total": str(r["total"])} for r in sin_disp])
        total_huerfanos = sum(int(r["total"]) for r in sin_disp)
        self._k_huerfanos.update_value(total_huerfanos, tone="warning" if total_huerfanos else "success")

        self._feedback.clear()
        self.main_window.set_status("Calidad de datos actualizada")

    def _on_error(self, msg: str) -> None:
        self._refresh_btn.setEnabled(True)
        self._feedback.show_message(f"Error en calidad de datos: {msg}", "error")
