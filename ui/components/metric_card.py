"""
Tarjeta de métrica KPI reutilizable.
"""
from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class MetricCard(QFrame):
    def __init__(
        self,
        title: str,
        value: str | int,
        subtitle: str | None = None,
        color: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("MetricCard")
        self.setMinimumSize(180, 90)
        self.setMaximumHeight(110)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("MetricTitle")
        layout.addWidget(self.title_label)

        self.value_label = QLabel(str(value))
        self.value_label.setObjectName("MetricValue")
        if color:
            self.value_label.setStyleSheet(f"color: {color};")
        layout.addWidget(self.value_label)

        self._subtitle_label: QLabel | None = None
        if subtitle:
            self._subtitle_label = QLabel(subtitle)
            self._subtitle_label.setObjectName("MetricSubtitle")
            layout.addWidget(self._subtitle_label)

    def update_value(self, value: str | int, subtitle: str | None = None) -> None:
        self.value_label.setText(str(value))
        if subtitle is not None:
            if self._subtitle_label is None:
                self._subtitle_label = QLabel()
                self._subtitle_label.setObjectName("MetricSubtitle")
                self.layout().addWidget(self._subtitle_label)
            self._subtitle_label.setText(subtitle)


class WorkerBase:
    """Mixin para páginas con operaciones en QThread."""
    pass
