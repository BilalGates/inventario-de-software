from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem


def _to_qcolor(hex_color: str) -> QColor:
    return QColor(hex_color)


HEADER_STYLE = """
QHeaderView::section {
    background-color: #366092;
    color: white;
    font-weight: bold;
    padding: 6px;
    border: 1px solid #2a4a6e;
}
"""


class DataTable(QTableWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAlternatingRowColors(True)
        self.setStyleSheet("""
            QTableWidget {
                gridline-color: #ddd;
                alternate-background-color: #f9f9f9;
                font-size: 9pt;
            }
            QTableWidget::item {
                padding: 4px 8px;
            }
        """ + HEADER_STYLE)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)

    def load_data(self, data: list[dict], columns: list[str] | None = None) -> None:
        if not data:
            self.setRowCount(1)
            self.setColumnCount(1)
            self.setHorizontalHeaderLabels(["Sin datos"])
            self.setItem(0, 0, QTableWidgetItem("No hay datos disponibles"))
            return

        if columns is None:
            columns = list(data[0].keys())

        self.setColumnCount(len(columns))
        self.setHorizontalHeaderLabels(columns)
        self.setRowCount(len(data))

        for row_idx, record in enumerate(data):
            for col_idx, col in enumerate(columns):
                value = record.get(col)
                display = str(value) if value is not None else ""
                item = QTableWidgetItem(display)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.setItem(row_idx, col_idx, item)

        self.resizeColumnsToContents()
        total_width = sum(self.columnWidth(i) for i in range(len(columns)))
        viewport_width = self.viewport().width()
        if total_width < viewport_width:
            self.horizontalHeader().setStretchLastSection(True)

    def get_selected_row_data(self) -> dict | None:
        row = self.currentRow()
        if row < 0:
            return None
        result = {}
        for col in range(self.columnCount()):
            header = self.horizontalHeaderItem(col).text()
            item = self.item(row, col)
            result[header] = item.text() if item else ""
        return result
