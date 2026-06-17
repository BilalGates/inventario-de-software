"""
StatusBadge — etiqueta de estado con fondo suave y texto claro.

Regla de accesibilidad: el estado NUNCA depende solo del color; el badge
siempre muestra texto. Soporta estados de dominio (Autorizado, Pendiente,
No autorizado, Exclusivo, No presente, Reactivado, Error, Correcto, Incompleto,
Nuevo, Cambio versión, Eliminado, Sí/No...).
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QSize
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QStyledItemDelegate

from ui.theme import status_colors
from ui.tokens import FONT, RADIUS


class StatusBadge(QFrame):
    """Badge compacto para usar en formularios, cabeceras o paneles de detalle."""

    def __init__(self, text: str, tone: str | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("StatusBadge")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(0)
        self._label = QLabel("")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label)
        self.set_status(text, tone)

    def set_status(self, text: str, tone: str | None = None) -> None:
        text = str(text or "—")
        fg, bg = status_colors(tone or text)
        self._label.setText(text)
        self.setStyleSheet(
            f"#StatusBadge {{ background-color: {bg}; border: none;"
            f" border-radius: {RADIUS['pill']}px; }}"
            f" #StatusBadge QLabel {{ color: {fg}; background: transparent;"
            f" font-size: {FONT['tiny']}px; font-weight: 700; }}"
        )


class BadgeDelegate(QStyledItemDelegate):
    """
    Delegate que pinta el valor de una celda como un badge (pastilla).

    Úsalo con `view.setItemDelegateForColumn(col, BadgeDelegate(view))`.
    El tono se deriva del texto de la celda (ver tokens.STATUS_LABELS).
    """

    _H_PAD = 9
    _V_PAD = 4

    def paint(self, painter: QPainter, option, index) -> None:
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "").strip()

        # Fondo de selección / alternancia lo pinta el estilo base sin el texto.
        opt = option
        if not text:
            super().paint(painter, opt, index)
            return

        # Pintamos primero el fondo de la celda (selección incluida) sin texto.
        from PySide6.QtWidgets import QStyleOptionViewItem

        bg_opt = QStyleOptionViewItem(opt)
        self.initStyleOption(bg_opt, index)
        bg_opt.text = ""
        style = bg_opt.widget.style() if bg_opt.widget else None
        if style:
            from PySide6.QtWidgets import QStyle
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, bg_opt, painter, bg_opt.widget)

        fg, bg = status_colors(text)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        font = QFont(option.font)
        font.setPointSizeF(max(8.0, option.font.pointSizeF() - 0.5))
        font.setBold(True)
        painter.setFont(font)

        metrics = painter.fontMetrics()
        text_w = metrics.horizontalAdvance(text)
        text_h = metrics.height()
        badge_w = text_w + 2 * self._H_PAD
        badge_h = text_h + 2 * self._V_PAD

        rect = option.rect
        x = rect.left() + 8
        y = rect.top() + (rect.height() - badge_h) / 2
        pill = QRectF(x, y, badge_w, badge_h)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(bg))
        painter.drawRoundedRect(pill, badge_h / 2, badge_h / 2)

        painter.setPen(QPen(QColor(fg)))
        painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()

    def sizeHint(self, option, index) -> QSize:
        size = super().sizeHint(option, index)
        return QSize(size.width() + 2 * self._H_PAD + 16, max(size.height(), 30))
