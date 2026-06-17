"""
Historial de importaciones confirmadas (todas las áreas), con filtro por
departamento y buscador.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget

from ui.components.sortable_table import SortableTable
from ui.components.ui_kit import FeedbackBar, FilterBar, PageHeader
from ui.components.worker import run_in_thread

if TYPE_CHECKING:
    from ui.main_window import MainWindow


_METODO_LABEL = {"paste": "Pegado", "file": "Archivo"}


def _fetch_historial():
    from database.connection import get_engine
    from modules.importacion import listar_importaciones
    from modules.software import listar_departamentos
    with get_engine().connect() as db:
        depts = listar_departamentos(db)
        rows = listar_importaciones(db, limit=500)
    result = []
    for r in rows:
        item = dict(r)
        item["fecha_str"] = str(item.get("fecha_importacion") or "")[:19]
        item["metodo_str"] = _METODO_LABEL.get(item.get("metodo"), item.get("metodo") or "")
        result.append(item)
    return depts, result


HEADERS = ["Fecha", "Equipo", "Departamento", "Método", "Nuevos", "Actualizados", "Eliminados", "Cambios versión"]
KEYS = ["fecha_str", "equipo", "departamento", "metodo_str", "n_nuevos", "n_actualizados", "n_eliminados", "n_cambios_version"]


class HistorialImportacionesPage(QWidget):
    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__()
        self.main_window = main_window
        self._all: list[dict] = []
        self._thread = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        layout.addWidget(PageHeader(
            "Historial de importaciones",
            "Registro de todas las importaciones confirmadas para trazabilidad ENS.",
        ))

        self._feedback = FeedbackBar()
        layout.addWidget(self._feedback)

        toolbar = FilterBar()
        self._search = FilterBar.search_box("Buscar por equipo, departamento...")
        self._search.textChanged.connect(self._apply_filters)
        toolbar.add_widget(self._search, stretch=1)
        self._dept_combo = QComboBox()
        self._dept_combo.setMinimumWidth(180)
        self._dept_combo.addItem("Todos los departamentos", None)
        self._dept_combo.currentIndexChanged.connect(self._apply_filters)
        toolbar.add_widget(self._dept_combo)
        layout.addWidget(toolbar)

        self._table = SortableTable(headers=HEADERS, keys=KEYS, badge_keys=["metodo_str"])
        self._table.set_empty_content(
            title="Sin importaciones",
            message="Todavía no se ha registrado ninguna importación.",
            icon="🕘",
            action_text="Ir a Importar Panda",
            on_action=lambda: self.main_window.navigate_to("import"),
        )
        layout.addWidget(self._table, stretch=1)

        self._status = QLabel("")
        self._status.setObjectName("labelMuted")
        layout.addWidget(self._status)

    def on_activate(self) -> None:
        self._load_data()

    def _load_data(self) -> None:
        self._feedback.show_message("Cargando historial...", "info")
        self._thread = run_in_thread(self, _fetch_historial, on_done=self._on_loaded, on_error=self._on_error)

    def _on_loaded(self, result) -> None:
        depts, rows = result
        self._all = rows
        cur = self._dept_combo.currentData()
        self._dept_combo.blockSignals(True)
        self._dept_combo.clear()
        self._dept_combo.addItem("Todos los departamentos", None)
        for d in depts:
            self._dept_combo.addItem(d["nombre"], d["nombre"])
        for i in range(self._dept_combo.count()):
            if self._dept_combo.itemData(i) == cur:
                self._dept_combo.setCurrentIndex(i)
                break
        self._dept_combo.blockSignals(False)
        self._apply_filters()
        self._feedback.clear()

    def _apply_filters(self) -> None:
        dept = self._dept_combo.currentData()
        rows = self._all if not dept else [r for r in self._all if r.get("departamento") == dept]
        self._table.load_data(rows)
        self._table.filter(self._search.text())
        self._status.setText(f"{self._table.row_count()} / {len(self._all)} importaciones")

    def _on_error(self, msg: str) -> None:
        self._feedback.show_message(f"Error cargando historial: {msg}", "error")
