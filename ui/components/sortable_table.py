"""
Widget de tabla con sort, filtro por texto y selección de fila.
Siempre QTableView + QAbstractTableModel — nunca QTableWidget.
"""
from __future__ import annotations

import re
from typing import Callable

from PySide6.QtCore import QSortFilterProxyModel, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QMenu,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ui.components.base_table_model import BaseTableModel
from ui.components.status_badge import BadgeDelegate
from ui.components.ui_kit import EmptyState
from ui.tokens import HEIGHT


def _natural_key(value: object) -> list[tuple[int, object]]:
    parts = re.split(r"(\d+)", str(value or "").casefold())
    key: list[tuple[int, object]] = []
    for part in parts:
        if not part:
            continue
        if part.isdigit():
            key.append((0, int(part)))
        else:
            key.append((1, part))
    return key


class NaturalSortProxyModel(QSortFilterProxyModel):
    def lessThan(self, left, right) -> bool:
        left_value = left.data(Qt.ItemDataRole.DisplayRole)
        right_value = right.data(Qt.ItemDataRole.DisplayRole)
        return _natural_key(left_value) < _natural_key(right_value)


class SortableTable(QWidget):
    """
    Tabla reutilizable con:
    - QTableView + BaseTableModel
    - QSortFilterProxyModel (sort por columna, filtro por texto en todas las cols)
    - Selección de fila completa, alto de fila cómodo
    - Columnas de estado renderizadas como badges (badge_keys)
    - Señal row_activated (doble clic / Enter) → dict de la fila
    - Señal selection_changed → dict | None (para paneles de detalle)
    """

    row_activated = Signal(dict)
    selection_changed = Signal(object)  # dict | None

    _MAX_COL_WIDTH = 340
    _MIN_COL_WIDTH = 70

    def __init__(
        self,
        headers: list[str],
        keys: list[str] | None = None,
        badge_keys: list[str] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._headers = headers
        self._keys = keys or []
        self._badge_keys = badge_keys or []
        self._context_menu_handler: Callable[[dict, object], bool | None] | None = None
        self._source_model = BaseTableModel([], headers, keys)
        self._empty_message = "No hay registros para mostrar"

        self._proxy = NaturalSortProxyModel(self)
        self._proxy.setSourceModel(self._source_model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setFilterKeyColumn(-1)

        self._view = QTableView()
        self._view.setModel(self._proxy)
        self._view.setSortingEnabled(True)
        self._view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._view.setAlternatingRowColors(False)
        self._view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._view.horizontalHeader().setStretchLastSection(True)
        self._view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._view.horizontalHeader().setHighlightSections(False)
        self._view.horizontalHeader().setMinimumSectionSize(self._MIN_COL_WIDTH)
        self._view.verticalHeader().setVisible(False)
        self._view.verticalHeader().setDefaultSectionSize(HEIGHT["row"])
        self._view.horizontalHeader().setFixedHeight(HEIGHT["header_row"])
        self._view.setShowGrid(False)
        self._view.setWordWrap(False)
        self._view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._view.doubleClicked.connect(self._on_double_click)
        self._view.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self._view.customContextMenuRequested.connect(self._on_context_menu)

        self._apply_badge_delegates()

        self._empty_state = EmptyState(self._empty_message)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)
        layout.addWidget(self._empty_state)
        self._update_empty_state()

    # ------------------------------------------------------------------
    # Configuración
    # ------------------------------------------------------------------

    def _apply_badge_delegates(self) -> None:
        for key in self._badge_keys:
            if key in self._keys:
                col = self._keys.index(key)
                self._view.setItemDelegateForColumn(col, BadgeDelegate(self._view))

    def view(self) -> QTableView:
        return self._view

    def set_context_menu_handler(self, handler: Callable[[dict, object], bool | None] | None) -> None:
        self._context_menu_handler = handler

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------

    def load_data(self, data: list[dict]) -> None:
        self._source_model.refresh(data)
        self._auto_size_columns()
        self._update_empty_state()

    def _auto_size_columns(self) -> None:
        n = len(self._headers)
        for i in range(n - 1):  # la última columna estira
            self._view.resizeColumnToContents(i)
            width = self._view.columnWidth(i)
            self._view.setColumnWidth(i, max(self._MIN_COL_WIDTH, min(width + 16, self._MAX_COL_WIDTH)))

    def filter(self, text: str) -> None:
        self._proxy.setFilterFixedString(text)
        self._empty_message = (
            "No hay resultados para este filtro" if text else "No hay registros para mostrar"
        )
        self._update_empty_state()

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
        proxy_index = self._view.indexAt(pos)
        if proxy_index.isValid():
            self._view.selectRow(proxy_index.row())
        row = self.selected_row()
        if not row:
            return
        global_pos = self._view.viewport().mapToGlobal(pos)
        if self._context_menu_handler and self._context_menu_handler(row, global_pos):
            return
        menu = QMenu(self)
        copy_action = menu.addAction("Copiar nombre")
        action = menu.exec(global_pos)
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

    def set_empty_message(self, message: str) -> None:
        self._empty_message = message
        self._update_empty_state()

    def set_empty_content(
        self,
        title: str | None = None,
        message: str | None = None,
        icon: str | None = None,
        action_text: str | None = None,
        on_action: Callable | None = None,
    ) -> None:
        if message is not None:
            self._empty_message = message
        self._empty_state.set_content(title, message, icon, action_text, on_action)
        self._update_empty_state()

    def _update_empty_state(self) -> None:
        is_empty = self._proxy.rowCount() == 0
        self._view.setVisible(not is_empty)
        self._empty_state.setVisible(is_empty)
        label = self._empty_state.findChild(QLabel, "EmptyStateBody")
        if label:
            label.setText(self._empty_message)
