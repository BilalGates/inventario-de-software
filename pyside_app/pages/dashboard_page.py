from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from database.connection import get_engine
from modules.equipos import estado_importacion, listar_estado_importaciones
from modules.exportacion import generar_excel_completo
from modules.software import dashboard_metricas, estado_departamentos

from pyside_app.widgets.data_table import DataTable
from pyside_app.widgets.metric_card import MetricCard

if TYPE_CHECKING:
    from pyside_app.main_window import MainWindow


class DashboardPage(QWidget):
    def __init__(self, main_window: MainWindow) -> None:
        super().__init__()
        self.main_window = main_window
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Inventario Software Asserta")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        self.metrics_layout = QHBoxLayout()
        self.metrics_layout.setSpacing(16)
        layout.addLayout(self.metrics_layout)

        dept_label = QLabel("Estado por departamento")
        dept_label_font = QFont()
        dept_label_font.setPointSize(12)
        dept_label_font.setBold(True)
        dept_label.setFont(dept_label_font)
        layout.addWidget(dept_label)

        self.dept_table = DataTable()
        layout.addWidget(self.dept_table, stretch=1)

        alert_label = QLabel("Alertas activas")
        alert_label_font = QFont()
        alert_label_font.setPointSize(12)
        alert_label_font.setBold(True)
        alert_label.setFont(alert_label_font)
        layout.addWidget(alert_label)

        self.alert_table = DataTable()
        layout.addWidget(self.alert_table, stretch=1)

        self.export_btn = QPushButton("Exportar todo a Excel")
        self.export_btn.setFixedWidth(220)
        self.export_btn.setStyleSheet("""
            QPushButton {
                background: #27ae60;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background: #219a52; }
        """)
        self.export_btn.clicked.connect(self._export_all)
        layout.addWidget(self.export_btn, alignment=Qt.AlignLeft)

        layout.addStretch()

    def on_activate(self) -> None:
        self._load_data()

    def _load_data(self) -> None:
        try:
            with get_engine().connect() as db:
                metricas = dashboard_metricas(db)
                departamentos = estado_departamentos(db)
                equipos_estado = listar_estado_importaciones(db)
        except Exception as exc:
            QMessageBox.critical(self, "Error de conexion", f"No se pudo conectar con MySQL.\n{exc}")
            return

        self._clear_layout(self.metrics_layout)
        cards = [
            ("Equipos activos", str(metricas["equipos_activos"])),
            ("Software activo", str(metricas["software_activo"])),
            ("Importaciones este mes", str(metricas["importaciones_mes"])),
        ]
        sw_sd = metricas["software_sin_dispositivo"]
        delta = "Revisar" if sw_sd else None
        cards.append(("Software sin dispositivo", str(sw_sd), delta))
        for card_data in cards:
            card = MetricCard(card_data[0], card_data[1], card_data[2] if len(card_data) > 2 else None)
            self.metrics_layout.addWidget(card)

        dept_data = []
        for dept in departamentos:
            dept_data.append({
                "Departamento": dept["departamento"],
                "Equipos activos": str(dept["equipos_activos"]),
                "Software visible": str(dept["software_visible"]),
                "Ultima importacion": str(dept["ultima_importacion"] or ""),
                "Estado": estado_importacion(dept["ultima_importacion"]),
            })
        self.dept_table.load_data(
            dept_data,
            ["Departamento", "Equipos activos", "Software visible", "Ultima importacion", "Estado"],
        )

        alertas = [
            {
                "Equipo": row["nombre"],
                "Departamento": row["departamento_nombre"],
                "Ultima importacion": str(row["ultima_importacion"] or ""),
                "Estado": row["estado_importacion"],
                "Responsable": row.get("responsable") or "",
            }
            for row in equipos_estado
            if row["dias_desde_importacion"] is None
            or row["dias_desde_importacion"] > 30
            or not row.get("responsable")
        ]
        if alertas:
            self.alert_table.load_data(
                alertas[:50],
                ["Equipo", "Departamento", "Ultima importacion", "Estado", "Responsable"],
            )
        else:
            self.alert_table.load_data([])

    def _export_all(self) -> None:
        try:
            with get_engine().connect() as db:
                data = generar_excel_completo(db)
            from PySide6.QtWidgets import QFileDialog
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Guardar Excel",
                f"Inventario_Asserta_Completo_{date.today().isoformat()}.xlsx",
                "Excel (*.xlsx)",
            )
            if filename:
                with open(filename, "wb") as f:
                    f.write(data)
                QMessageBox.information(self, "Exportado", f"Excel guardado en:\n{filename}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"No se pudo exportar:\n{exc}")

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
