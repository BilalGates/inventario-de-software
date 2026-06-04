"""
Modelo base para todas las tablas — QAbstractTableModel, nunca QTableWidget.
"""
from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt


class BaseTableModel(QAbstractTableModel):
    """
    Modelo genérico para mostrar una lista de dicts en un QTableView.

    Uso:
        model = BaseTableModel(data=rows, headers=["Nombre", "Versión", ...])
        table_view.setModel(model)
    """

    def __init__(
        self,
        data: list[dict],
        headers: list[str],
        keys: list[str] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._data: list[dict] = data
        self._headers: list[str] = headers
        # Si no se pasan keys explícitas, se infieren del primer registro
        if keys is not None:
            self._keys = keys
        else:
            self._keys = list(data[0].keys()) if data else []

    # ------------------------------------------------------------------
    # QAbstractTableModel obligatorios
    # ------------------------------------------------------------------

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._data)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._headers)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if index.row() >= len(self._data) or index.column() >= len(self._keys):
            return None

        row = self._data[index.row()]
        key = self._keys[index.column()]

        if role == Qt.ItemDataRole.DisplayRole:
            value = row.get(key)
            if value is None:
                return ""
            if isinstance(value, bool):
                return "Sí" if value else "No"
            return str(value)

        if role == Qt.ItemDataRole.UserRole:
            return row

        if role == Qt.ItemDataRole.ToolTipRole:
            value = row.get(key)
            return str(value) if value is not None else ""

        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return self._headers[section] if section < len(self._headers) else ""
        return None

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def refresh(self, data: list[dict]) -> None:
        """Recarga el modelo sin recrear la vista (preserva ancho de columnas)."""
        self.beginResetModel()
        self._data = data
        if data and not self._keys:
            self._keys = list(data[0].keys())
        self.endResetModel()

    def get_row(self, index: int) -> dict:
        return self._data[index] if 0 <= index < len(self._data) else {}

    def all_rows(self) -> list[dict]:
        return list(self._data)
