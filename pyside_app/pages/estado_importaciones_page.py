from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from database.connection import get_engine
from modules.equipos import listar_estado_importaciones
from modules.software import listar_departamentos

from pyside_app.widgets.data_table import DataTable
from pyside_app.widgets.metric_card import MetricCard

if TYPE_CHECKING:
    from pyside_app.main_window import MainWindow


class EstadoImportacionesPage(QWidget):
    def __init__(self, main_window: MainWindow) -> None:
        super().__init__()
        self.main_window = main_window
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Estado de Importaciones")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Departamento:"))
        self.dept_combo = QComboBox()
        self.dept_combo.addItem("Todos", None)
        filter_layout.addWidget(self.dept_combo)
        filter_layout.addWidget(QLabel("Estado:"))
        self.estado_combo = QComboBox()
        self.estado_combo.addItems(["Todos", "Al dia", "Pendiente", "Nunca importado"])
        filter_layout.addWidget(self.estado_combo)
        self.filter_btn = QPushButton("Filtrar")
        self.filter_btn.clicked.connect(self._load_data)
        filter_layout.addWidget(self.filter_btn)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        self.metrics_layout = QHBoxLayout()
        layout.addLayout(self.metrics_layout)

        self.table = DataTable()
        layout.addWidget(self.table, stretch=1)

    def on_activate(self) -> None:
        try:
            with get_engine().connect() as db:
                depts = listar_departamentos(db)
            for dept in depts:
                self.dept_combo.addItem(dept["nombre"], dept["id"])
        except Exception:
            pass
        self._load_data()

    def _load_data(self) -> None:
        try:
            with get_engine().connect() as db:
                departamento_id = self.dept_combo.currentData()
                rows = listar_estado_importaciones(db, departamento_id=departamento_id)
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        estado_filter = self.estado_combo.currentText()
        if estado_filter != "Todos":
            if estado_filter == "Al dia":
                rows = [r for r in rows if r.get("dias_desde_importacion") is not None and r["dias_desde_importacion"] < 30]
            elif estado_filter == "Pendiente":
                rows = [r for r in rows if r.get("dias_desde_importacion") is not None and r["dias_desde_importacion"] >= 30]
            elif estado_filter == "Nunca importado":
                rows = [r for r in rows if r.get("dias_desde_importacion") is None]

        total = len(rows)
        al_dia = sum(1 for r in rows if r.get("dias_desde_importacion") is not None and r["dias_desde_importacion"] < 30)
        pendientes = sum(1 for r in rows if r.get("dias_desde_importacion") is not None and r["dias_desde_importacion"] >= 30)
        nunca = sum(1 for r in rows if r.get("dias_desde_importacion") is None)

        self._clear_metrics()
        self.metrics_layout.addWidget(MetricCard("Total equipos", str(total)))
        self.metrics_layout.addWidget(MetricCard("Al dia", str(al_dia)))
        self.metrics_layout.addWidget(MetricCard("Pendientes", str(pendientes)))
        self.metrics_layout.addWidget(MetricCard("Nunca importados", str(nunca)))

        data = []
        for row in rows:
            data.append({
                "Equipo": row["nombre"],
                "Departamento": row["departamento_nombre"],
                "Ultima importacion": str(row.get("ultima_importacion") or ""),
                "Dias": str(row.get("dias_desde_importacion") or ""),
                "Estado": row["estado_importacion"],
            })
        self.table.load_data(data, ["Equipo", "Departamento", "Ultima importacion", "Dias", "Estado"])

    def _clear_metrics(self) -> None:
        while self.metrics_layout.count():
            child = self.metrics_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
