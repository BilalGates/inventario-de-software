"""
Tarjeta de métrica KPI reutilizable.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from ui.theme import COLORS


class MetricCard(QWidget):
    def __init__(
        self,
        title: str,
        value: str | int,
        subtitle: str | None = None,
        color: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setMinimumSize(180, 90)
        self.setMaximumHeight(110)
        c = COLORS
        self.setStyleSheet(f"""
            MetricCard {{
                background-color: {c['bg_tertiary']};
                border: 1px solid {c['border']};
                border-radius: 8px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"color: {c['text_muted']}; font-size: 11px; font-weight: bold; text-transform: uppercase; letter-spacing: 0.04em;")
        layout.addWidget(self.title_label)

        val_color = color or c["text_primary"]
        self.value_label = QLabel(str(value))
        self.value_label.setStyleSheet(f"color: {val_color}; font-size: 24px; font-weight: bold;")
        layout.addWidget(self.value_label)

        if subtitle:
            sub_label = QLabel(subtitle)
            sub_label.setStyleSheet(f"color: {c['text_muted']}; font-size: 11px;")
            layout.addWidget(sub_label)

    def update_value(self, value: str | int, subtitle: str | None = None) -> None:
        self.value_label.setText(str(value))


class WorkerBase:
    """Mixin para páginas con operaciones en QThread."""
    pass
