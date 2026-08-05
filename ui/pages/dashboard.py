from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QFileDialog, QMessageBox, QPushButton, QVBoxLayout, QWidget

from modules.simple_inventory import current_period
from ui.components.metric_card import MetricCard, MetricRow
from ui.components.sortable_table import SortableTable
from ui.components.ui_kit import FeedbackBar, FilterBar, PageHeader
from ui.components.worker import run_in_thread
from ui.tokens import SPACING

if TYPE_CHECKING:
    from ui.main_window import MainWindow


def _fetch_dashboard(periodo: str):
    from database.connection import get_engine
    from modules.simple_inventory import dashboard_simple, resumen_departamentos

    with get_engine().connect() as db:
        return dashboard_simple(periodo, db=db), resumen_departamentos(periodo, db=db)


def _export_excel(periodo: str) -> bytes:
    from modules.simple_inventory import exportar_inventario_excel

    return exportar_inventario_excel(periodo)


class DashboardPage(QWidget):
    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__()
        self.main_window = main_window
        self._thread = None
        self._pending_export_path: str | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(SPACING["lg"])

        self._export_btn = QPushButton("Exportar Excel")
        self._export_btn.setObjectName("primary")
        self._export_btn.clicked.connect(self._export_all)
        header = PageHeader("Inicio", "Resumen simple del inventario mensual.")
        header.add_action(self._export_btn)
        layout.addWidget(header)

        self._feedback = FeedbackBar()
        layout.addWidget(self._feedback)

        toolbar = FilterBar()
        self._period_edit = FilterBar.search_box("YYYY-MM")
        self._period_edit.setText(current_period())
        self._period_edit.setMaximumWidth(120)
        self._period_edit.editingFinished.connect(self._load_data)
        toolbar.add_widget(self._period_edit)
        self._refresh_btn = QPushButton("Actualizar")
        self._refresh_btn.clicked.connect(self._load_data)
        toolbar.add_widget(self._refresh_btn)
        toolbar.add_stretch()
        layout.addWidget(toolbar)

        kpis = MetricRow()
        self._equipos = MetricCard("Equipos activos", "-")
        self._departamentos = MetricCard("Departamentos", "-")
        self._importaciones = MetricCard("Equipos importados", "-")
        self._software = MetricCard("Software distinto", "-")
        for card in (self._equipos, self._departamentos, self._importaciones, self._software):
            kpis.add_card(card)
        layout.addWidget(kpis)

        self._table = SortableTable(
            headers=["Departamento", "Equipos", "Importados", "Software", "Estado"],
            keys=["nombre", "equipos", "importados", "software", "estado"],
            badge_keys=["estado"],
        )
        self._table.set_empty_content(
            title="Sin datos",
            message="Importa software de algun equipo para ver el resumen mensual.",
            icon="",
        )
        layout.addWidget(self._table, stretch=1)

    def on_activate(self) -> None:
        self._load_data()

    def _periodo(self) -> str:
        from modules.simple_inventory import validate_periodo

        return validate_periodo(self._period_edit.text())

    def _load_data(self) -> None:
        try:
            periodo = self._periodo()
        except ValueError as exc:
            self._feedback.show_message(str(exc), "warning")
            return
        self._feedback.show_message("Cargando resumen...", "info")
        self._thread = run_in_thread(self, _fetch_dashboard, periodo, on_done=self._on_loaded, on_error=self._on_error)

    def _on_loaded(self, result) -> None:
        metricas, departamentos = result
        self._equipos.update_value(metricas.get("equipos", 0))
        self._departamentos.update_value(metricas.get("departamentos", 0))
        self._importaciones.update_value(metricas.get("importaciones", 0))
        self._software.update_value(metricas.get("software", 0))
        self._table.load_data(departamentos)
        self._feedback.clear()
        self.main_window.set_status(f"Ultima actualizacion: {date.today().isoformat()}")

    def _export_all(self) -> None:
        try:
            periodo = self._periodo()
        except ValueError as exc:
            self._feedback.show_message(str(exc), "warning")
            return
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar Excel",
            f"Inventario_Asserta_{periodo}.xlsx",
            "Excel (*.xlsx)",
        )
        if not filename:
            return
        self._pending_export_path = filename
        self._export_btn.setEnabled(False)
        self._feedback.show_message("Generando Excel...", "info")
        self._thread = run_in_thread(self, _export_excel, periodo, on_done=self._on_export_ready, on_error=self._on_error)

    def _on_export_ready(self, data: bytes) -> None:
        path = self._pending_export_path
        self._pending_export_path = None
        self._export_btn.setEnabled(True)
        if not path:
            return
        try:
            with open(path, "wb") as f:
                f.write(data)
        except OSError as exc:
            QMessageBox.critical(self, "Error", f"No se pudo guardar el Excel:\n{exc}")
            return
        self._feedback.show_message(f"Excel guardado en {path}.", "success")

    def _on_error(self, msg: str) -> None:
        self._export_btn.setEnabled(True)
        self._feedback.show_message(f"Error: {msg}", "error")
