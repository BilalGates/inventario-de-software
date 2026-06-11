"""
Componentes pequenos de interfaz para layouts consistentes.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class PageHeader(QWidget):
    def __init__(self, title: str, subtitle: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 2)
        layout.setSpacing(12)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(3)

        title_label = QLabel(title)
        title_label.setObjectName("PageHeaderTitle")
        text_col.addWidget(title_label)

        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("PageHeaderSubtitle")
            subtitle_label.setWordWrap(True)
            text_col.addWidget(subtitle_label)

        layout.addLayout(text_col, stretch=1)
        self._actions = QHBoxLayout()
        self._actions.setSpacing(8)
        layout.addLayout(self._actions)

    def add_action(self, widget: QWidget) -> None:
        self._actions.addWidget(widget)


class FilterBar(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Toolbar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)
        self._layout = layout

    def add_widget(self, widget: QWidget, stretch: int = 0) -> None:
        self._layout.addWidget(widget, stretch)

    def add_stretch(self) -> None:
        self._layout.addStretch()

    @staticmethod
    def search_box(placeholder: str) -> QLineEdit:
        search = QLineEdit()
        search.setPlaceholderText(placeholder)
        search.setMinimumWidth(220)
        return search


class FeedbackBar(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("FeedbackBar")
        self.setProperty("status", "info")
        self.setVisible(False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(8)

        self._label = QLabel("")
        self._label.setObjectName("FeedbackText")
        self._label.setWordWrap(True)
        layout.addWidget(self._label, stretch=1)

    def show_message(self, message: str, status: str = "info") -> None:
        self.setProperty("status", status)
        self._label.setText(message)
        self.setVisible(bool(message))
        self.style().unpolish(self)
        self.style().polish(self)

    def clear(self) -> None:
        self._label.clear()
        self.setVisible(False)


class EmptyState(QFrame):
    def __init__(self, message: str = "Sin datos para mostrar", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("EmptyState")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label = QLabel(message)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        layout.addWidget(label)
