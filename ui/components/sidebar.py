"""
Panel de navegacion lateral de la aplicacion.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from config import APP_NAME, APP_VERSION


class Sidebar(QWidget):
    page_changed = Signal(str)

    def __init__(self, pages: list[tuple], parent=None):
        """
        pages: lista de (key, label, PageClass, icon_text)
        """
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(196)

        self._buttons: dict[str, QPushButton] = {}
        self._active_key: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("Sidebar")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(14, 16, 14, 12)
        header_layout.setSpacing(2)

        title = QLabel(APP_NAME)
        title.setObjectName("SidebarTitle")
        header_layout.addWidget(title)

        version_lbl = QLabel(f"v{APP_VERSION}")
        version_lbl.setObjectName("SidebarVersion")
        header_layout.addWidget(version_lbl)

        layout.addWidget(header)

        nav_container = QWidget()
        nav_container.setObjectName("Sidebar")
        nav_layout = QVBoxLayout(nav_container)
        nav_layout.setContentsMargins(8, 6, 8, 8)
        nav_layout.setSpacing(2)

        main_group = QLabel("Trabajo")
        main_group.setObjectName("SidebarGroup")
        nav_layout.addWidget(main_group)

        for key, label, _page_class, _icon in pages:
            if key == "settings":
                nav_layout.addStretch()
                settings_group = QLabel("Sistema")
                settings_group.setObjectName("SidebarGroup")
                nav_layout.addWidget(settings_group)

            btn = QPushButton(f"  {label}")
            btn.setObjectName("navBtn")
            btn.setProperty("active", "false")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setFixedHeight(36)
            btn.clicked.connect(lambda checked, k=key: self._on_nav_click(k))
            nav_layout.addWidget(btn)
            self._buttons[key] = btn

        layout.addWidget(nav_container, stretch=1)

        if pages:
            self.set_active(pages[0][0])

    def _on_nav_click(self, key: str) -> None:
        self.set_active(key)
        self.page_changed.emit(key)

    def set_active(self, key: str) -> None:
        if self._active_key and self._active_key in self._buttons:
            btn = self._buttons[self._active_key]
            btn.setProperty("active", "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        self._active_key = key
        if key in self._buttons:
            btn = self._buttons[key]
            btn.setProperty("active", "true")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
