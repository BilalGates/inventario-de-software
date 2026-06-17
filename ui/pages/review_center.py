"""
Centro de revisión: reúne en una sola pantalla todo lo que requiere acción para
no tener que recorrer cinco módulos. Cada bloque enlaza a su pantalla.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.components.status_badge import StatusBadge
from ui.components.ui_kit import FeedbackBar, PageHeader
from ui.components.worker import run_in_thread
from ui.tokens import SPACING

if TYPE_CHECKING:
    from ui.main_window import MainWindow


def _fetch_review():
    from database.connection import get_engine
    from modules.autorizado import detectar_software_exclusivo
    from modules.importacion import contar_reactivaciones_pendientes
    from modules.software import (
        fabricantes_vacios,
        listar_inventario_empresa,
        versiones_sospechosas,
    )
    from modules.equipos import listar_estado_importaciones
    with get_engine().connect() as db:
        empresa = listar_inventario_empresa(db)
        pendientes_ens = sum(1 for r in empresa if r.get("en_guia_105") is None)
        exclusivos = len(detectar_software_exclusivo(db))
        reactivaciones = contar_reactivaciones_pendientes(db)
        estados = listar_estado_importaciones(db)
        equipos_atrasados = sum(
            1 for r in estados
            if r.get("dias_desde_importacion") is None or (r.get("dias_desde_importacion") or 0) > 30
        )
        sin_fabricante = len(fabricantes_vacios(db))
        versiones = len(versiones_sospechosas(db))
    return {
        "pendientes_ens": pendientes_ens,
        "exclusivos": exclusivos,
        "reactivaciones": reactivaciones,
        "equipos_atrasados": equipos_atrasados,
        "sin_fabricante": sin_fabricante,
        "versiones": versiones,
    }


class _ReviewCard(QFrame):
    def __init__(self, title: str, description: str, action_text: str, on_action) -> None:
        super().__init__()
        self.setObjectName("SectionCard")
        row = QHBoxLayout(self)
        row.setContentsMargins(SPACING["lg"], SPACING["md"], SPACING["lg"], SPACING["md"])
        row.setSpacing(SPACING["lg"])

        self._count = QLabel("—")
        self._count.setObjectName("MetricValue")
        self._count.setFixedWidth(64)
        self._count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self._count)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title_lbl = QLabel(title)
        title_lbl.setObjectName("SectionTitle")
        text_col.addWidget(title_lbl)
        desc_lbl = QLabel(description)
        desc_lbl.setObjectName("labelMuted")
        desc_lbl.setWordWrap(True)
        text_col.addWidget(desc_lbl)
        row.addLayout(text_col, stretch=1)

        self._badge = StatusBadge("—", "neutral")
        row.addWidget(self._badge)

        self._btn = QPushButton(action_text)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.clicked.connect(on_action)
        row.addWidget(self._btn)

    def set_count(self, count: int) -> None:
        self._count.setText(str(count))
        if count > 0:
            self._badge.set_status("Requiere acción", "warning")
            self._btn.setObjectName("primary")
        else:
            self._badge.set_status("Al día", "success")
            self._btn.setObjectName("subtle")
        # Re-aplicar estilo tras cambiar objectName
        self._btn.style().unpolish(self._btn)
        self._btn.style().polish(self._btn)


class ReviewCenterPage(QWidget):
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
        header = PageHeader(
            "Centro de revisión",
            "Todo lo que requiere tu atención, en un solo lugar.",
        )
        header.add_action(self._refresh_btn)
        layout.addWidget(header)

        self._feedback = FeedbackBar()
        layout.addWidget(self._feedback)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        col = QVBoxLayout(content)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(SPACING["md"])
        col.setAlignment(Qt.AlignmentFlag.AlignTop)

        nav = self.main_window.navigate_to
        self._cards = {
            "pendientes_ens": _ReviewCard(
                "Pendiente de clasificar (ENS)",
                "Software detectado sin marcar en la Guía 105.",
                "Revisar", lambda: nav("software", {"guia": "Pendiente"})),
            "exclusivos": _ReviewCard(
                "Exclusivos por autorizar",
                "Software instalado en un único equipo, sin autorizar.",
                "Revisar", lambda: nav("autorizado")),
            "reactivaciones": _ReviewCard(
                "Reactivaciones pendientes",
                "Software inactivo que ha vuelto a detectarse.",
                "Revisar", lambda: nav("reactivaciones")),
            "equipos_atrasados": _ReviewCard(
                "Equipos sin importación reciente",
                "Más de 30 días sin importar, o nunca importados.",
                "Revisar", lambda: nav("equipos")),
            "sin_fabricante": _ReviewCard(
                "Software sin fabricante",
                "Registros con el fabricante vacío.",
                "Revisar", lambda: nav("quality")),
            "versiones": _ReviewCard(
                "Versiones sospechosas",
                "Versiones con formato dudoso a revisar.",
                "Revisar", lambda: nav("quality")),
        }
        for card in self._cards.values():
            col.addWidget(card)

        scroll.setWidget(content)
        layout.addWidget(scroll, stretch=1)

    def on_activate(self) -> None:
        self._load_data()

    def _load_data(self) -> None:
        self._feedback.show_message("Calculando elementos pendientes...", "info")
        self._thread = run_in_thread(self, _fetch_review, on_done=self._on_loaded, on_error=self._on_error)

    def _on_loaded(self, counts: dict) -> None:
        for key, card in self._cards.items():
            card.set_count(int(counts.get(key, 0)))
        total = sum(int(v) for v in counts.values())
        self._feedback.clear()
        self.main_window.set_status(f"{total} elementos requieren revisión")

    def _on_error(self, msg: str) -> None:
        self._feedback.show_message(f"Error: {msg}", "error")
