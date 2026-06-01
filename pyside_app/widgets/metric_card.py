from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class MetricCard(QWidget):
    def __init__(self, title: str, value: str | int, delta: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(220, 100)
        self.setStyleSheet("""
            MetricCard {
                background: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #666; font-size: 9pt;")
        layout.addWidget(self.title_label)

        value_font = QFont()
        value_font.setPointSize(22)
        value_font.setBold(True)
        self.value_label = QLabel(str(value))
        self.value_label.setFont(value_font)
        self.value_label.setStyleSheet("color: #1a1a2e;")
        layout.addWidget(self.value_label)

        if delta:
            delta_label = QLabel(delta)
            is_inverse = delta in ("Revisar",)
            color = "#e74c3c" if is_inverse else "#27ae60"
            delta_label.setStyleSheet(f"color: {color}; font-size: 9pt; font-weight: bold;")
            layout.addWidget(delta_label)
