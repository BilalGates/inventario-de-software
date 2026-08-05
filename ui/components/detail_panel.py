"""
DetailPanel — panel lateral derecho para ver el detalle de la fila seleccionada
sin abrir modales. Muestra título, badges de estado, pares campo/valor y acciones.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
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
from ui.tokens import SPACING


class DetailPanel(QFrame):
    closed = Signal()

    def __init__(self, parent: QWidget | None = None, width: int = 320) -> None:
        super().__init__(parent)
        self.setObjectName("DetailPanel")
        self.setFixedWidth(width)
        self.setVisible(False)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(SPACING["lg"], SPACING["md"], SPACING["lg"], SPACING["lg"])
        outer.setSpacing(SPACING["sm"])

        header = QHBoxLayout()
        self._title = QLabel("Detalle")
        self._title.setObjectName("SectionTitle")
        self._title.setWordWrap(True)
        header.addWidget(self._title, stretch=1)

        close_btn = QPushButton("X")
        close_btn.setObjectName("subtle")
        close_btn.setFixedWidth(32)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setToolTip("Cerrar detalle")
        close_btn.clicked.connect(self._on_close)
        header.addWidget(close_btn)
        outer.addLayout(header)

        self._badges_row = QHBoxLayout()
        self._badges_row.setSpacing(SPACING["xs"])
        self._badges_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        outer.addLayout(self._badges_row)

        scroll = QScrollArea()
        scroll.setObjectName("DetailPanelScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.viewport().setObjectName("DetailPanelViewport")
        self._content = QWidget()
        self._content.setObjectName("DetailPanelContent")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, SPACING["xs"], 0, 0)
        self._content_layout.setSpacing(SPACING["sm"])
        self._content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._content)
        outer.addWidget(scroll, stretch=1)

        self._actions = QVBoxLayout()
        self._actions.setSpacing(SPACING["sm"])
        outer.addLayout(self._actions)

    # ------------------------------------------------------------------
    def show_details(
        self,
        title: str,
        rows: list[tuple[str, str]],
        badges: list[tuple[str, str | None]] | None = None,
        actions: list[QWidget] | None = None,
    ) -> None:
        self._title.setText(title or "Detalle")
        self._clear_layout(self._badges_row)
        for text, tone in (badges or []):
            self._badges_row.addWidget(StatusBadge(text, tone))
        self._badges_row.addStretch()

        self._clear_layout(self._content_layout)
        for label, value in rows:
            self._content_layout.addWidget(self._field(label, value))

        self._clear_layout(self._actions)
        for widget in (actions or []):
            self._actions.addWidget(widget)

        self.setVisible(True)

    def clear(self) -> None:
        self.setVisible(False)

    # ------------------------------------------------------------------
    def _field(self, label: str, value: str) -> QWidget:
        box = QWidget()
        box.setObjectName("DetailField")
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(1)
        cap = QLabel(label)
        cap.setObjectName("labelMuted")
        val = QLabel(str(value) if value not in (None, "") else "—")
        val.setObjectName("labelSecondary")
        val.setWordWrap(True)
        val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        v.addWidget(cap)
        v.addWidget(val)
        return box

    def _on_close(self) -> None:
        self.clear()
        self.closed.emit()

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
