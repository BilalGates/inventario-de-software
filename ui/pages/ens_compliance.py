"""
Auditoria ENS: resumen de cumplimiento segun CCN-STIC Guia 105.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from config import ENS_GUIDE_VERSION
from ui.components.metric_card import MetricCard
from ui.components.sortable_table import SortableTable
from ui.components.ui_kit import FeedbackBar, PageHeader
from ui.components.worker import run_in_thread
from ui.theme import COLORS

if TYPE_CHECKING:
    from ui.main_window import MainWindow


def _fetch_ens_data():
    from database.connection import get_engine
    from modules.software import listar_inventario_empresa
    with get_engine().connect() as db:
        rows = listar_inventario_empresa(db)

    compliant, non_compliant, pending = [], [], []
    for row in rows:
        r = dict(row)
        r["version_referencia"] = str(r.get("version_referencia") or "")
        guia = r.get("en_guia_105")
        if guia is True:
            compliant.append(r)
        elif guia is False:
            non_compliant.append(r)
        else:
            pending.append(r)

    total = len(rows)
    score = round(len(compliant) / total * 100, 1) if total else 0.0
    return {
        "compliant": compliant,
        "non_compliant": non_compliant,
        "pending": pending,
        "total": total,
        "score": score,
    }


HEADERS_NC = ["Nombre norm.", "Fabricantes", "Versiones", "Departamentos", "Dispositivos"]
KEYS_NC = ["nombre_norm", "fabricantes", "versiones", "departamentos", "dispositivos"]

HEADERS_PEND = ["Nombre norm.", "Fabricantes", "Versiones", "Departamentos"]
KEYS_PEND = ["nombre_norm", "fabricantes", "versiones", "departamentos"]


class ENSCompliancePage(QWidget):
    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__()
        self.main_window = main_window
        self._thread = None
        self._last_result = None
        self._build_ui()

    def _build_ui(self) -> None:
        c = COLORS
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        self._refresh_btn = QPushButton("Actualizar")
        self._refresh_btn.clicked.connect(self._load_data)
        self._export_btn = QPushButton("Generar TXT")
        self._export_btn.clicked.connect(self._export_report)

        header = PageHeader(f"Auditoria ENS - {ENS_GUIDE_VERSION}", "Cumplimiento de software segun Guia 105.")
        header.add_action(self._refresh_btn)
        header.add_action(self._export_btn)
        layout.addWidget(header)

        self._feedback = FeedbackBar()
        layout.addWidget(self._feedback)

        from PySide6.QtWidgets import QHBoxLayout
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(12)
        self._card_score = MetricCard("Puntuacion global", "-", "% compliant", color=c["success"])
        self._card_compliant = MetricCard("Compliant (Si)", "-", color=c["success"])
        self._card_nc = MetricCard("No compliant", "-", color=c["danger"])
        self._card_pending = MetricCard("Pendiente", "-", color=c["warning"])
        for card in (self._card_score, self._card_compliant, self._card_nc, self._card_pending):
            kpi_row.addWidget(card)
        kpi_row.addStretch()
        layout.addLayout(kpi_row)

        nc_label = QLabel("Software marcado como no incluido en Guia 105")
        nc_label.setObjectName("labelSection")
        layout.addWidget(nc_label)
        self._nc_table = SortableTable(headers=HEADERS_NC, keys=KEYS_NC)
        self._nc_table.setFixedHeight(220)
        layout.addWidget(self._nc_table)

        pend_label = QLabel("Software pendiente de revision")
        pend_label.setObjectName("labelSection")
        layout.addWidget(pend_label)
        self._pend_table = SortableTable(headers=HEADERS_PEND, keys=KEYS_PEND)
        layout.addWidget(self._pend_table, stretch=1)

    def on_activate(self) -> None:
        self._load_data()

    def _load_data(self) -> None:
        self._refresh_btn.setEnabled(False)
        self._feedback.show_message("Cargando datos ENS...", "info")
        self._thread = run_in_thread(self, _fetch_ens_data,
                                     on_done=self._on_data_loaded, on_error=self._on_error)

    def _on_data_loaded(self, result: dict) -> None:
        self._refresh_btn.setEnabled(True)
        self._last_result = result
        score = result["score"]
        self._card_score.update_value(f"{score}%")
        self._card_compliant.update_value(len(result["compliant"]))
        self._card_nc.update_value(len(result["non_compliant"]))
        self._card_pending.update_value(len(result["pending"]))
        self._nc_table.load_data(result["non_compliant"])
        self._pend_table.load_data(result["pending"])
        self._feedback.clear()
        self.main_window.set_status("Auditoria ENS actualizada")

    def _on_error(self, msg: str) -> None:
        self._refresh_btn.setEnabled(True)
        self._feedback.show_message(f"Error cargando ENS: {msg}", "error")
        QMessageBox.critical(self, "Error", f"Error cargando datos ENS:\n{msg}")

    def _export_report(self) -> None:
        if not self._last_result:
            self._feedback.show_message("Carga los datos antes de generar el informe.", "warning")
            return
        result = self._last_result
        lines = [
            f"INFORME DE AUDITORIA ENS - {ENS_GUIDE_VERSION}",
            "=" * 60,
            f"Total software analizado : {result['total']}",
            f"Compliant (incluido)      : {len(result['compliant'])}",
            f"No compliant              : {len(result['non_compliant'])}",
            f"Pendiente de revision     : {len(result['pending'])}",
            f"Puntuacion global         : {result['score']}%",
            "",
            "SOFTWARE NO COMPLIANT:",
            "-" * 40,
        ]
        for r in result["non_compliant"]:
            lines.append(f"  - {r.get('nombre_norm', '')} | {r.get('fabricantes', '')} | {r.get('versiones', '')}")
        lines += ["", "SOFTWARE PENDIENTE DE REVISION:", "-" * 40]
        for r in result["pending"]:
            lines.append(f"  - {r.get('nombre_norm', '')} | {r.get('fabricantes', '')}")

        report_text = "\n".join(lines)
        from PySide6.QtWidgets import QFileDialog
        from datetime import date
        filename, _ = QFileDialog.getSaveFileName(
            self, "Guardar informe",
            f"informe_ENS_{date.today().isoformat()}.txt",
            "Texto (*.txt)",
        )
        if filename:
            self._export_btn.setEnabled(False)
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(report_text)
                self._feedback.show_message(f"Informe guardado en {filename}.", "success")
                self.main_window.set_status("Informe ENS exportado")
            finally:
                self._export_btn.setEnabled(True)
