"""
Inicio: centro de control. Responde a ¿está sano el inventario?, ¿qué requiere
atención? y ¿qué puedo hacer ahora?
"""
from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.components.metric_card import MetricCard, MetricRow
from ui.components.sortable_table import SortableTable
from ui.components.status_badge import StatusBadge
from ui.components.ui_kit import FeedbackBar, PageHeader, SectionCard
from ui.components.worker import run_in_thread
from ui.tokens import SPACING

if TYPE_CHECKING:
    from ui.main_window import MainWindow


def _estado_label(dias) -> str:
    if dias is None:
        return "Nunca importado"
    if dias < 30:
        return "Al día"
    if dias <= 60:
        return "Atención"
    return "Atrasado"


def _dias_desde(fecha) -> int | None:
    if fecha is None:
        return None
    if isinstance(fecha, datetime):
        fecha = fecha.date()
    if not isinstance(fecha, date):
        try:
            fecha = datetime.fromisoformat(str(fecha)[:19]).date()
        except (ValueError, TypeError):
            return None
    return (date.today() - fecha).days


def _fetch_dashboard():
    from database.connection import get_engine
    from modules.autorizado import detectar_software_exclusivo
    from modules.equipos import listar_estado_importaciones
    from modules.importacion import contar_reactivaciones_pendientes
    from modules.software import dashboard_metricas, estado_departamentos, listar_inventario_empresa

    with get_engine().connect() as db:
        metricas = dashboard_metricas(db)
        departamentos = estado_departamentos(db)
        equipos = listar_estado_importaciones(db)
        empresa = listar_inventario_empresa(db)
        pendientes_ens = sum(1 for r in empresa if r.get("en_guia_105") is None)
        exclusivos = len(detectar_software_exclusivo(db))
        reactivaciones = contar_reactivaciones_pendientes(db)

    equipos_atrasados = sum(
        1 for r in equipos
        if r.get("dias_desde_importacion") is None or (r.get("dias_desde_importacion") or 0) > 30
    )
    alerts = {
        "pendientes_ens": pendientes_ens,
        "exclusivos": exclusivos,
        "reactivaciones": reactivaciones,
        "equipos_atrasados": equipos_atrasados,
    }
    return metricas, departamentos, equipos, alerts


class _AlertRow(QWidget):
    def __init__(self, text: str, action_text: str, on_action) -> None:
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(SPACING["md"])
        self._badge = StatusBadge("0", "neutral")
        self._badge.setFixedWidth(48)
        row.addWidget(self._badge)
        self._label = QLabel(text)
        self._label.setObjectName("labelSecondary")
        row.addWidget(self._label, stretch=1)
        self._btn = QPushButton(action_text)
        self._btn.setObjectName("link")
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.clicked.connect(on_action)
        row.addWidget(self._btn)

    def set_count(self, count: int) -> None:
        self._badge.set_status(str(count), "warning" if count else "success")
        self.setVisible(True)


class DashboardPage(QWidget):
    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__()
        self.main_window = main_window
        self._thread = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(SPACING["lg"])

        self._export_btn = QPushButton("Exportar Excel")
        self._export_btn.setObjectName("primary")
        self._export_btn.clicked.connect(self._export_all)
        header = PageHeader("Inicio", "Estado del inventario y acciones recomendadas.")
        header.add_action(self._export_btn)
        layout.addWidget(header)

        self._feedback = FeedbackBar()
        layout.addWidget(self._feedback)

        # Accesos rápidos
        quick = QHBoxLayout()
        quick.setSpacing(SPACING["sm"])
        for text, key, payload, primary in (
            ("Importar desde Panda", "import", None, True),
            ("Revisar software nuevo", "software", {"guia": "Pendiente"}, False),
            ("Exportar informe ENS", "ens", None, False),
            ("Ver calidad de datos", "quality", None, False),
        ):
            btn = QPushButton(text)
            if primary:
                btn.setObjectName("primary")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _c=False, k=key, p=payload: self.main_window.navigate_to(k, p))
            quick.addWidget(btn)
        quick.addStretch()
        layout.addLayout(quick)

        # KPIs
        kpis = MetricRow()
        self._card_equipos = MetricCard("Equipos activos", "—")
        self._card_software = MetricCard("Software detectado", "—")
        self._card_sin_disp = MetricCard("Software sin dispositivo", "—")
        self._card_import_mes = MetricCard("Importaciones (mes)", "—")
        self._card_atrasados = MetricCard("Equipos sin importar (30d)", "—")
        for card in (self._card_equipos, self._card_software, self._card_sin_disp,
                     self._card_import_mes, self._card_atrasados):
            kpis.add_card(card)
        layout.addWidget(kpis)

        # Requiere revisión
        self._alerts_card = SectionCard("Requiere revisión")
        self._alert_rows = {
            "pendientes_ens": _AlertRow(
                "Software pendiente de clasificar (Guía 105)", "Revisar →",
                lambda: self.main_window.navigate_to("software", {"guia": "Pendiente"})),
            "exclusivos": _AlertRow(
                "Software exclusivo por autorizar", "Revisar →",
                lambda: self.main_window.navigate_to("autorizado")),
            "reactivaciones": _AlertRow(
                "Reactivaciones pendientes", "Revisar →",
                lambda: self.main_window.navigate_to("reactivaciones")),
            "equipos_atrasados": _AlertRow(
                "Equipos sin importación reciente", "Revisar →",
                lambda: self.main_window.navigate_to("equipos")),
        }
        for r in self._alert_rows.values():
            self._alerts_card.add_widget(r)
        layout.addWidget(self._alerts_card)

        # Estado por departamento
        dept_label = QLabel("Estado por departamento")
        dept_label.setObjectName("labelSection")
        layout.addWidget(dept_label)
        self._dept_table = SortableTable(
            headers=["Departamento", "Equipos", "Software", "Última importación", "Estado"],
            keys=["departamento", "equipos_activos", "software_visible", "ultima_importacion", "estado"],
            badge_keys=["estado"],
        )
        self._dept_table.setMinimumHeight(200)
        layout.addWidget(self._dept_table, stretch=1)

    def on_activate(self) -> None:
        self._load_data()

    def apply_navigation(self, payload: dict) -> None:  # noqa: ARG002
        pass

    def _load_data(self) -> None:
        self._feedback.show_message("Actualizando inicio...", "info")
        self._thread = run_in_thread(self, _fetch_dashboard, on_done=self._on_data_loaded, on_error=self._on_error)

    def _on_data_loaded(self, result) -> None:
        metricas, departamentos, _equipos, alerts = result
        self._card_equipos.update_value(metricas["equipos_activos"])
        self._card_software.update_value(metricas["software_activo"])
        sw_sd = metricas["software_sin_dispositivo"]
        self._card_sin_disp.update_value(sw_sd, "Revisar" if sw_sd else "OK",
                                         tone="warning" if sw_sd else "success")
        self._card_import_mes.update_value(metricas["importaciones_mes"])
        atr = alerts["equipos_atrasados"]
        self._card_atrasados.update_value(atr, "Requiere acción" if atr else "OK",
                                          tone="warning" if atr else "success")

        for key, row in self._alert_rows.items():
            row.set_count(int(alerts.get(key, 0)))

        dept_rows = []
        for d in departamentos:
            dias = _dias_desde(d.get("ultima_importacion"))
            dept_rows.append({
                "departamento": d["departamento"],
                "equipos_activos": str(d["equipos_activos"]),
                "software_visible": str(d["software_visible"]),
                "ultima_importacion": str(d.get("ultima_importacion") or "—")[:10],
                "estado": _estado_label(dias),
            })
        self._dept_table.load_data(dept_rows)

        self._feedback.clear()
        self.main_window.set_status(f"Última actualización: {date.today().isoformat()}")

    def _on_error(self, msg: str) -> None:
        self._feedback.show_message(f"No se pudo cargar el inicio: {msg}", "error")

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
                self.main_window.set_status("Excel exportado")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"No se pudo exportar:\n{exc}")
        finally:
            self._export_btn.setEnabled(True)
