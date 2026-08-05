from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from ui.tokens import SPACING


class DepartmentCard(QFrame):
    clicked = Signal(int)

    def __init__(self, departamento_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.departamento_id = departamento_id
        self.setObjectName("DepartmentCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(98)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING["lg"], SPACING["md"], SPACING["lg"], SPACING["md"])
        layout.setSpacing(SPACING["xs"])

        self._title = QLabel("")
        self._title.setObjectName("DepartmentCardTitle")
        self._title.setWordWrap(True)
        layout.addWidget(self._title)

        self._metric = QLabel("")
        self._metric.setObjectName("DepartmentCardMetric")
        layout.addWidget(self._metric)

        self._import_status = QLabel("")
        self._import_status.setObjectName("DepartmentCardMeta")
        layout.addWidget(self._import_status)

        self._footer = QLabel("")
        self._footer.setObjectName("DepartmentCardMeta")
        layout.addWidget(self._footer)

    def update_content(
        self,
        name: str,
        active_count: int,
        inactive_count: int,
        imported_count: int,
        software_count: int,
        matched_count: int | None = None,
    ) -> None:
        self._title.setText(name)
        suffix = f" + {inactive_count} inactivos" if inactive_count else ""
        self._metric.setText(f"{active_count} activos{suffix}")
        self._import_status.setText(f"{imported_count} / {active_count} importados este mes")
        if matched_count is None:
            self._footer.setText(f"{software_count} programas distintos")
        else:
            self._footer.setText(f"{matched_count} resultados con la busqueda")

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.departamento_id)
        super().mousePressEvent(event)
