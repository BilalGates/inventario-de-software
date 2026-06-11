"""
Pagina de inicio: KPIs y estado por departamento.
"""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from ui.components.metric_card import MetricCard
from ui.components.sortable_table import SortableTable
from ui.components.ui_kit import FeedbackBar, PageHeader
from ui.components.worker import run_in_thread
from ui.theme import COLORS

if TYPE_CHECKING:
    from ui.main_window import MainWindow


def _fetch_dashboard():
    from database.connection import get_engine
    from modules.software import dashboard_metricas, estado_departamentos
    from modules.equipos import listar_estado_importaciones

    with get_engine().connect() as db:
        metricas = dashboard_metricas(db)
        departamentos = estado_departamentos(db)
        equipos = listar_estado_importaciones(db)
    return metricas, departamentos, equipos


class DashboardPage(QWidget):
    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__()
        self.main_window = main_window
        self._thread = None
        self._build_ui()

    def _build_ui(self) -> None:
        c = COLORS
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        self._export_btn = QPushButton("Exportar Excel")
        self._export_btn.setObjectName("primary")
        self._export_btn.clicked.connect(self._export_all)

        header = PageHeader("Inventario Asserta", "Resumen de equipos, software y alertas operativas.")
        header.add_action(self._export_btn)
        layout.addWidget(header)

        self._feedback = FeedbackBar()
        layout.addWidget(self._feedback)

        self._kpi_layout = QVBoxLayout()
        self._kpi_layout.setSpacing(10)

        kpi_row = QVBoxLayout()
        kpi_row.setSpacing(10)
        layout.addLayout(kpi_row)

        from PySide6.QtWidgets import QHBoxLayout
        cards = QHBoxLayout()
        cards.setSpacing(12)
        kpi_row.addLayout(cards)

        self._card_equipos = MetricCard("Equipos activos", "-")
        self._card_software = MetricCard("Software activo", "-")
        self._card_importaciones = MetricCard("Importaciones este mes", "-")
        self._card_sin_disp = MetricCard("Software sin dispositivo", "-", color=c["warning"])

        for card in (self._card_equipos, self._card_software, self._card_importaciones, self._card_sin_disp):
            cards.addWidget(card)
        cards.addStretch()

        dept_label = QLabel("Estado por departamento")
        dept_label.setObjectName("labelSection")
        layout.addWidget(dept_label)

        self._dept_table = SortableTable(
            headers=["Departamento", "Equipos activos", "Software visible", "Ultima importacion", "Estado"],
            keys=["departamento", "equipos_activos", "software_visible", "ultima_importacion", "estado_importacion"],
        )
        self._dept_table.setFixedHeight(220)
        layout.addWidget(self._dept_table)

        alert_label = QLabel("Equipos con alertas")
        alert_label.setObjectName("labelSection")
        layout.addWidget(alert_label)

        self._alert_table = SortableTable(
            headers=["Equipo", "Departamento", "Ultima importacion", "Estado", "Responsable"],
            keys=["nombre", "departamento_nombre", "ultima_importacion", "estado_importacion", "responsable"],
        )
        self._alert_table.set_empty_message("No hay equipos con alertas pendientes")
        layout.addWidget(self._alert_table, stretch=1)

    def on_activate(self) -> None:
        self._load_data()

    def _load_data(self) -> None:
        self._feedback.show_message("Actualizando datos del inicio...", "info")
        self._thread = run_in_thread(
            self,
            _fetch_dashboard,
            on_done=self._on_data_loaded,
            on_error=self._on_error,
        )

    def _on_data_loaded(self, result) -> None:
        metricas, departamentos, equipos = result
        self._card_equipos.update_value(metricas["equipos_activos"])
        self._card_software.update_value(metricas["software_activo"])
        self._card_importaciones.update_value(metricas["importaciones_mes"])
        sw_sd = metricas["software_sin_dispositivo"]
        self._card_sin_disp.update_value(sw_sd, "Revisar" if sw_sd else "OK")

        from modules.equipos import estado_importacion
        dept_data = []
        for d in departamentos:
            dept_data.append({
                "departamento": d["departamento"],
                "equipos_activos": str(d["equipos_activos"]),
                "software_visible": str(d["software_visible"]),
                "ultima_importacion": str(d.get("ultima_importacion") or ""),
                "estado_importacion": estado_importacion(d.get("ultima_importacion")),
            })
        self._dept_table.load_data(dept_data)

        alertas = [
            {
                **row,
                "estado_importacion": row.get("estado_importacion", ""),
                "responsable": row.get("responsable") or "",
                "ultima_importacion": str(row.get("ultima_importacion") or ""),
            }
            for row in equipos
            if row.get("dias_desde_importacion") is None
            or row.get("dias_desde_importacion", 0) > 30
            or not row.get("responsable")
        ]
        self._alert_table.load_data(alertas[:100])

        self._feedback.clear()
        if self.main_window:
            self.main_window.set_status(f"Ultima actualizacion: {date.today()}")

    def _on_error(self, msg: str) -> None:
        self._feedback.show_message(f"No se pudo cargar el dashboard: {msg}", "error")
        QMessageBox.critical(self, "Error de conexion", f"No se pudo cargar el dashboard:\n{msg}")

    def _export_all(self) -> None:
        self._export_btn.setEnabled(False)
        try:
            from database.connection import get_engine
            from modules.exportacion import generar_excel_completo
            with get_engine().connect() as db:
                data = generar_excel_completo(db)
            from PySide6.QtWidgets import QFileDialog
            filename, _ = QFileDialog.getSaveFileName(
                self, "Guardar Excel",
                f"Inventario_Asserta_Completo_{date.today().isoformat()}.xlsx",
                "Excel (*.xlsx)",
            )
            if filename:
                with open(filename, "wb") as f:
                    f.write(data)
                self._feedback.show_message(f"Excel guardado en {filename}.", "success")
                if self.main_window:
                    self.main_window.set_status("Excel exportado")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"No se pudo exportar:\n{exc}")
        finally:
            self._export_btn.setEnabled(True)
