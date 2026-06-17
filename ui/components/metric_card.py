"""
Tarjeta de métrica (KPI) reutilizable: etiqueta, valor, nota y estado opcional.
Puede ser clicable para servir de acceso directo desde el dashboard.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.theme import status_colors
from ui.tokens import SPACING


class MetricCard(QFrame):
    clicked = Signal()

    def __init__(
        self,
        title: str,
        value: str | int = "—",
        subtitle: str | None = None,
        tone: str | None = None,
        color: str | None = None,
        clickable: bool = False,
        accent: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("MetricCard")
        self.setMinimumSize(180, 96)
        self.setMaximumHeight(120)
        if accent:
            self.setProperty("accent", "true")
        self._clickable = clickable
        if clickable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING["lg"], SPACING["md"], SPACING["lg"], SPACING["md"])
        layout.setSpacing(SPACING["xs"])

        self.title_label = QLabel(title)
        self.title_label.setObjectName("MetricTitle")
        layout.addWidget(self.title_label)

        self.value_label = QLabel(str(value))
        self.value_label.setObjectName("MetricValue")
        layout.addWidget(self.value_label)

        layout.addStretch()

        self._subtitle_label = QLabel(subtitle or "")
        self._subtitle_label.setObjectName("MetricSubtitle")
        self._subtitle_label.setVisible(bool(subtitle))
        layout.addWidget(self._subtitle_label)

        self._apply_tone(tone, color)

    def _apply_tone(self, tone: str | None, color: str | None) -> None:
        chosen = color
        if tone and not color:
            chosen, _ = status_colors(tone)
        if chosen:
            self.value_label.setStyleSheet(f"color: {chosen};")
        else:
            self.value_label.setStyleSheet("")

    def update_value(
        self,
        value: str | int,
        subtitle: str | None = None,
        tone: str | None = None,
        color: str | None = None,
    ) -> None:
        self.value_label.setText(str(value))
        if subtitle is not None:
            self._subtitle_label.setText(subtitle)
            self._subtitle_label.setVisible(bool(subtitle))
        if tone is not None or color is not None:
            self._apply_tone(tone, color)

    def mouseReleaseEvent(self, event) -> None:
        if self._clickable and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


# Mantengo el mixin histórico por compatibilidad de imports.
class WorkerBase:
    """Mixin para páginas con operaciones en QThread."""
    pass


class MetricRow(QWidget):
    """Fila horizontal de MetricCards con espaciado consistente."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(0, 0, 0, 0)
        self._row.setSpacing(SPACING["md"])

    def add_card(self, card: MetricCard, stretch: int = 1) -> None:
        self._row.addWidget(card, stretch)

    def add_stretch(self) -> None:
        self._row.addStretch()
