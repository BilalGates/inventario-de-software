"""
Panel de navegación lateral, agrupado por tareas y con iconos simples.
"""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from config import APP_NAME, APP_VERSION
from ui.components.icons import icon
from ui.theme import COLORS
from ui.tokens import HEIGHT, SPACING

# groups: list[ (group_label | None, [ (key, label, icon_name), ... ]) ]
NavGroups = list


class Sidebar(QWidget):
    page_changed = Signal(str)

    def __init__(self, groups: NavGroups, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(216)

        self._buttons: dict[str, QPushButton] = {}
        self._icon_names: dict[str, str] = {}
        self._active_key: str | None = None
        self._first_key: str | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Cabecera (marca)
        header = QWidget()
        header.setObjectName("Sidebar")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["md"])
        header_layout.setSpacing(1)
        title = QLabel(APP_NAME)
        title.setObjectName("SidebarTitle")
        header_layout.addWidget(title)
        version_lbl = QLabel(f"v{APP_VERSION}")
        version_lbl.setObjectName("SidebarVersion")
        header_layout.addWidget(version_lbl)
        root.addWidget(header)

        # Navegación (scroll por si crece)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        nav = QWidget()
        nav.setObjectName("Sidebar")
        nav_layout = QVBoxLayout(nav)
        nav_layout.setContentsMargins(SPACING["sm"], SPACING["xs"], SPACING["sm"], SPACING["md"])
        nav_layout.setSpacing(1)

        for group_label, items in groups:
            if group_label:
                lbl = QLabel(group_label.upper())
                lbl.setObjectName("SidebarGroup")
                nav_layout.addWidget(lbl)
            for key, label, icon_name in items:
                nav_layout.addWidget(self._make_button(key, label, icon_name))
                if self._first_key is None:
                    self._first_key = key

        nav_layout.addStretch()
        scroll.setWidget(nav)
        root.addWidget(scroll, stretch=1)

        if self._first_key:
            self.set_active(self._first_key)

    def _make_button(self, key: str, label: str, icon_name: str) -> QPushButton:
        btn = QPushButton(f"  {label}")
        btn.setObjectName("navBtn")
        btn.setProperty("active", "false")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn.setFixedHeight(HEIGHT["button"])
        btn.setIcon(icon(icon_name, COLORS["text_secondary"]))
        btn.setIconSize(QSize(18, 18))
        btn.clicked.connect(lambda _checked=False, k=key: self._on_nav_click(k))
        self._buttons[key] = btn
        self._icon_names[key] = icon_name
        return btn

    def _on_nav_click(self, key: str) -> None:
        self.set_active(key)
        self.page_changed.emit(key)

    def set_active(self, key: str) -> None:
        if self._active_key and self._active_key in self._buttons:
            prev = self._buttons[self._active_key]
            prev.setProperty("active", "false")
            prev.setIcon(icon(self._icon_names[self._active_key], COLORS["text_secondary"]))
            prev.style().unpolish(prev)
            prev.style().polish(prev)

        self._active_key = key
        if key in self._buttons:
            btn = self._buttons[key]
            btn.setProperty("active", "true")
            btn.setIcon(icon(self._icon_names[key], COLORS["accent"]))
            btn.style().unpolish(btn)
            btn.style().polish(btn)
