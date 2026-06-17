"""
ConfirmDialog — confirmación clara para acciones críticas.

Uso:
    if confirm(self, "Revocar autorización",
               "Se revocará la autorización de 3 programas.",
               ok_text="Revocar", danger=True):
        ...
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.tokens import SPACING


class ConfirmDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        message: str,
        details: str | None = None,
        ok_text: str = "Confirmar",
        cancel_text: str = "Cancelar",
        danger: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING["xl"], SPACING["lg"], SPACING["xl"], SPACING["lg"])
        layout.setSpacing(SPACING["md"])

        heading = QLabel(title)
        heading.setObjectName("labelSection")
        layout.addWidget(heading)

        body = QLabel(message)
        body.setWordWrap(True)
        body.setObjectName("labelSecondary")
        layout.addWidget(body)

        if details:
            detail_lbl = QLabel(details)
            detail_lbl.setWordWrap(True)
            detail_lbl.setObjectName("labelMuted")
            layout.addWidget(detail_lbl)

        layout.addSpacing(SPACING["xs"])

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton(cancel_text)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        ok_btn = QPushButton(ok_text)
        ok_btn.setObjectName("danger" if danger else "primary")
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)


def confirm(
    parent: QWidget | None,
    title: str,
    message: str,
    *,
    details: str | None = None,
    ok_text: str = "Confirmar",
    cancel_text: str = "Cancelar",
    danger: bool = False,
) -> bool:
    """Devuelve True si el usuario confirma la acción."""
    dialog = ConfirmDialog(parent, title, message, details, ok_text, cancel_text, danger)
    return dialog.exec() == QDialog.DialogCode.Accepted
