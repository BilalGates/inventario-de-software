"""
Iconos SVG monocromos inline → QIcon. Sin ficheros de recurso ni dependencias
nuevas (usa PySide6.QtSvg, ya incluido). Trazo simple estilo "feather".
"""
from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_TEMPLATE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="{color}" stroke-width="1.8" stroke-linecap="round" '
    'stroke-linejoin="round">{body}</svg>'
)

_PATHS: dict[str, str] = {
    "home": '<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>'
            '<polyline points="9 22 9 12 15 12 15 22"/>',
    "software": '<rect x="3" y="3" width="7" height="7" rx="1.5"/>'
                '<rect x="14" y="3" width="7" height="7" rx="1.5"/>'
                '<rect x="14" y="14" width="7" height="7" rx="1.5"/>'
                '<rect x="3" y="14" width="7" height="7" rx="1.5"/>',
    "device": '<rect x="2" y="3" width="20" height="14" rx="2"/>'
              '<line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>',
    "departments": '<polygon points="12 2 2 7 12 12 22 7 12 2"/>'
                   '<polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>'
              '<polyline points="9 12 11 14 15 10"/>',
    "refresh": '<polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>'
               '<path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>',
    "inbox": '<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/>'
             '<path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
    "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
              '<polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15 14"/>',
    "audit": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
             '<polyline points="14 2 14 8 20 8"/><polyline points="9 15 11 17 15 13"/>',
    "database": '<ellipse cx="12" cy="5" rx="9" ry="3"/>'
                '<path d="M3 5v6c0 1.66 4 3 9 3s9-1.34 9-3V5"/>'
                '<path d="M3 11v6c0 1.66 4 3 9 3s9-1.34 9-3v-6"/>',
    "settings": '<circle cx="12" cy="12" r="3"/>'
                '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06'
                'a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09'
                'a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06'
                'a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09'
                'a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06'
                'a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09'
                'a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06'
                'a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09'
                'a1.65 1.65 0 0 0-1.51 1z"/>',
    "dot": '<circle cx="12" cy="12" r="3"/>',
}


@lru_cache(maxsize=128)
def icon(name: str, color: str = "#6b7280", size: int = 18) -> QIcon:
    body = _PATHS.get(name, _PATHS["dot"])
    svg = _TEMPLATE.format(color=color, body=body)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)
