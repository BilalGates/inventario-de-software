"""
Widget de tabla con sort, filter por texto y selección de fila.
Siempre QTableView + QAbstractTableModel — nunca QTableWidget.
"""
from __future__ import annotations

from PySide6.QtCore import QSortFilterProxyModel, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QMenu,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtWidgets import QTableView

from ui.components.base_table_model import BaseTableModel


class SortableTable(QWidget):
    """
    Tabla reutilizable con:
    - QTableView + BaseTableModel
    - QSortFilterProxyModel (sort por columna, filter por texto en todas las cols)
    - Selección de fila completa
    - Señal row_activated (doble clic o Enter) → dict de la fila
    - Señal selection_changed → dict | None
    """

    row_activated = Signal(dict)
    selection_changed = Signal(object)  # dict | None

    def __init__(
        self,
        headers: list[str],
        keys: list[str] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._headers = headers
        self._keys = keys or []
        self._source_model = BaseTableModel([], headers, keys)

        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._source_model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setFilterKeyColumn(-1)

        self._view = QTableView()
        self._view.setModel(self._proxy)
        self._view.setSortingEnabled(True)
        self._view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._view.setAlternatingRowColors(True)
        self._view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._view.horizontalHeader().setStretchLastSection(True)
        self._view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._view.verticalHeader().setVisible(False)
        self._view.setShowGrid(False)
        self._view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._view.doubleClicked.connect(self._on_double_click)
        self._view.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self._view.customContextMenuRequested.connect(self._on_context_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------

    def load_data(self, data: list[dict]) -> None:
        self._source_model.refresh(data)
        # Ajustar columnas al contenido en la carga inicial
        for i in range(len(self._headers) - 1):
            self._view.resizeColumnToContents(i)

    def filter(self, text: str) -> None:
        self._proxy.setFilterFixedString(text)

    # ------------------------------------------------------------------
    # Selección
    # ------------------------------------------------------------------

    def selected_row(self) -> dict | None:
        indexes = self._view.selectionModel().selectedRows()
        if not indexes:
            return None
        source_index = self._proxy.mapToSource(indexes[0])
        return self._source_model.get_row(source_index.row())

    def clear_selection(self) -> None:
        self._view.clearSelection()

    # ------------------------------------------------------------------
    # Señales internas
    # ------------------------------------------------------------------

    def _on_double_click(self, proxy_index) -> None:
        source_index = self._proxy.mapToSource(proxy_index)
        row = self._source_model.get_row(source_index.row())
        if row:
            self.row_activated.emit(row)

    def _on_selection_changed(self, selected, deselected) -> None:
        self.selection_changed.emit(self.selected_row())

    def _on_context_menu(self, pos) -> None:
        row = self.selected_row()
        if not row:
            return
        menu = QMenu(self)
        copy_action = menu.addAction("Copiar nombre")
        action = menu.exec(self._view.viewport().mapToGlobal(pos))
        if action == copy_action:
            from PySide6.QtWidgets import QApplication
            name = row.get("nombre") or row.get("name") or str(next(iter(row.values()), ""))
            QApplication.clipboard().setText(name)

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    def set_column_widths(self, widths: list[int]) -> None:
        for i, w in enumerate(widths):
            if i < len(self._headers) - 1:
                self._view.setColumnWidth(i, w)

    def row_count(self) -> int:
        return self._proxy.rowCount()
