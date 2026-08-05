"""
Componentes pequeños de interfaz para layouts consistentes.

Agrupa varios componentes ligeros (PageHeader, FilterBar/Toolbar, FeedbackBar,
EmptyState, SectionCard) en un único módulo para no fragmentar en exceso.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.tokens import SPACING


class PageHeader(QWidget):
    """Título + descripción breve + acciones principales a la derecha."""

    def __init__(self, title: str, subtitle: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING["md"])

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        title_label = QLabel(title)
        title_label.setObjectName("PageHeaderTitle")
        text_col.addWidget(title_label)
        self._title_label = title_label

        self._subtitle_label = QLabel(subtitle or "")
        self._subtitle_label.setObjectName("PageHeaderSubtitle")
        self._subtitle_label.setWordWrap(True)
        self._subtitle_label.setVisible(bool(subtitle))
        text_col.addWidget(self._subtitle_label)

        layout.addLayout(text_col, stretch=1)
        self._actions = QHBoxLayout()
        self._actions.setSpacing(SPACING["sm"])
        self._actions.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        layout.addLayout(self._actions)

    def add_action(self, widget: QWidget) -> None:
        self._actions.addWidget(widget)

    def set_title(self, title: str) -> None:
        self._title_label.setText(title)

    def set_subtitle(self, subtitle: str) -> None:
        self._subtitle_label.setText(subtitle or "")
        self._subtitle_label.setVisible(bool(subtitle))


class FilterBar(QFrame):
    """Barra blanca para buscador + filtros + acciones (alias: Toolbar)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("FilterBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACING["md"], SPACING["sm"], SPACING["md"], SPACING["sm"])
        layout.setSpacing(SPACING["sm"])
        self._layout = layout

    def add_widget(self, widget: QWidget, stretch: int = 0) -> None:
        self._layout.addWidget(widget, stretch)

    def add_stretch(self) -> None:
        self._layout.addStretch()

    @staticmethod
    def search_box(placeholder: str) -> QLineEdit:
        search = QLineEdit()
        search.setPlaceholderText(placeholder)
        search.setClearButtonEnabled(True)
        search.setMinimumWidth(240)
        return search

    @staticmethod
    def combo(items: list[tuple[str, object]] | None = None, min_width: int = 170) -> QComboBox:
        combo = QComboBox()
        combo.setMinimumWidth(min_width)
        for label, data in items or []:
            combo.addItem(label, data)
        return combo


# Alias semántico solicitado en el brief.
Toolbar = FilterBar


class FeedbackBar(QFrame):
    """Mensaje en línea con estado (info/success/warning/error)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("FeedbackBar")
        self.setProperty("status", "info")
        self.setVisible(False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACING["md"], SPACING["sm"], SPACING["md"], SPACING["sm"])
        layout.setSpacing(SPACING["sm"])

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
    """
    Estado vacío útil: icono simple + título + mensaje + acción recomendada.

    Hace que la app parezca guiada, no rota.
    """

    def __init__(
        self,
        message: str = "Sin datos para mostrar",
        title: str | None = None,
        icon: str = "○",
        action_text: str | None = None,
        on_action: Callable | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("EmptyState")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING["xl"], SPACING["xl"], SPACING["xl"], SPACING["xl"])
        layout.setSpacing(SPACING["sm"])
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._icon = QLabel(icon)
        self._icon.setObjectName("EmptyStateIcon")
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._icon)

        self._title = QLabel(title or "")
        self._title.setObjectName("EmptyStateTitle")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setVisible(bool(title))
        layout.addWidget(self._title)

        self._body = QLabel(message)
        self._body.setObjectName("EmptyStateBody")
        self._body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._body.setWordWrap(True)
        layout.addWidget(self._body)

        self._action_btn = QPushButton("")
        self._action_btn.setObjectName("primary")
        self._action_btn.setVisible(False)
        self._action_handler: Callable | None = None
        self._action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self._action_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        if action_text:
            self.set_action(action_text, on_action)

    def set_message(self, message: str) -> None:
        self._body.setText(message)

    def set_content(
        self,
        title: str | None = None,
        message: str | None = None,
        icon: str | None = None,
        action_text: str | None = None,
        on_action: Callable | None = None,
    ) -> None:
        if icon is not None:
            self._icon.setText(icon)
        if title is not None:
            self._title.setText(title)
            self._title.setVisible(bool(title))
        if message is not None:
            self._body.setText(message)
        self.set_action(action_text, on_action)

    def set_action(self, action_text: str | None, on_action: Callable | None) -> None:
        if self._action_handler is not None:
            self._action_btn.clicked.disconnect(self._action_handler)
            self._action_handler = None
        if action_text and on_action:
            self._action_btn.setText(action_text)
            self._action_btn.clicked.connect(on_action)
            self._action_handler = on_action
            self._action_btn.setVisible(True)
        else:
            self._action_btn.setVisible(False)


class SectionCard(QFrame):
    """Tarjeta blanca con título opcional y un layout de contenido."""

    def __init__(self, title: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SectionCard")
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(SPACING["lg"], SPACING["md"], SPACING["lg"], SPACING["lg"])
        self._outer.setSpacing(SPACING["md"])

        self._has_header = bool(title)
        self._header_row = QHBoxLayout()
        self._header_row.setSpacing(SPACING["sm"])
        self._title = QLabel(title or "")
        self._title.setObjectName("SectionTitle")
        self._title.setVisible(bool(title))
        self._header_row.addWidget(self._title)
        self._header_row.addStretch()
        if self._has_header:
            self._outer.addLayout(self._header_row)

        self.body = QVBoxLayout()
        self.body.setSpacing(SPACING["sm"])
        self._outer.addLayout(self.body)

    def set_title(self, title: str) -> None:
        self._title.setText(title or "")
        self._title.setVisible(bool(title))
        if title and not self._has_header:
            self._outer.insertLayout(0, self._header_row)
            self._has_header = True

    def add_header_action(self, widget: QWidget) -> None:
        if not self._has_header:
            self._outer.insertLayout(0, self._header_row)
            self._has_header = True
        self._header_row.addWidget(widget)

    def add_widget(self, widget: QWidget, stretch: int = 0) -> None:
        self.body.addWidget(widget, stretch)

    def add_layout(self, layout) -> None:
        self.body.addLayout(layout)
