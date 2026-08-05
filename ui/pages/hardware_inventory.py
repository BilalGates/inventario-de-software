from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.components.detail_panel import DetailPanel
from ui.components.sortable_table import SortableTable
from ui.components.ui_kit import FeedbackBar, FilterBar, PageHeader
from ui.components.worker import run_in_thread

if TYPE_CHECKING:
    from ui.main_window import MainWindow


HEADERS = ["Equipo", "Departamento", "Usuario", "Sistema operativo", "Activo"]
KEYS = ["nombre", "departamento_nombre", "usuario", "sistema_operativo", "activo_str"]


def _fetch_devices():
    from database.connection import get_engine
    from modules.equipos import listar_equipos

    with get_engine().connect() as db:
        rows = listar_equipos(db, solo_activos=False)
    result = []
    for row in rows:
        item = dict(row)
        item["usuario"] = item.get("notas") or item.get("responsable") or ""
        item["activo_str"] = "Activo" if item.get("activo") else "Inactivo"
        item["sistema_operativo"] = item.get("sistema_operativo") or ""
        result.append(item)
    return result


class HardwareInventoryPage(QWidget):
    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__()
        self.main_window = main_window
        self._rows: list[dict] = []
        self._thread = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        self._import_btn = QPushButton("Importar equipos")
        self._import_btn.clicked.connect(self._import_devices)
        self._export_btn = QPushButton("Exportar equipos")
        self._export_btn.setObjectName("primary")
        self._export_btn.clicked.connect(self._export_devices)
        header = PageHeader("Dispositivos", "Listado de equipos de la empresa.")
        header.add_action(self._import_btn)
        header.add_action(self._export_btn)
        layout.addWidget(header)

        self._feedback = FeedbackBar()
        layout.addWidget(self._feedback)

        toolbar = FilterBar()
        self._search = FilterBar.search_box("Buscar equipo, usuario, departamento...")
        self._search.textChanged.connect(self._apply_filter)
        toolbar.add_widget(self._search, stretch=1)
        self._refresh_btn = QPushButton("Actualizar")
        self._refresh_btn.clicked.connect(self._load_data)
        toolbar.add_widget(self._refresh_btn)
        layout.addWidget(toolbar)

        body = QHBoxLayout()
        self._table = SortableTable(headers=HEADERS, keys=KEYS, badge_keys=["activo_str"])
        self._table.set_empty_content(
            title="Sin dispositivos",
            message="Importa un Excel/CSV de equipos para empezar.",
            icon="",
        )
        self._table.selection_changed.connect(self._on_selection)
        body.addWidget(self._table, stretch=1)
        self._detail = DetailPanel()
        self._detail.closed.connect(self._table.clear_selection)
        body.addWidget(self._detail)
        layout.addLayout(body, stretch=1)

        self._status = QLabel("")
        self._status.setObjectName("labelMuted")
        layout.addWidget(self._status)

    def on_activate(self) -> None:
        self._load_data()

    def _load_data(self) -> None:
        self._feedback.show_message("Cargando dispositivos...", "info")
        self._thread = run_in_thread(self, _fetch_devices, on_done=self._on_loaded, on_error=self._on_error)

    def _on_loaded(self, rows: list[dict]) -> None:
        self._rows = rows
        self._table.load_data(rows)
        self._apply_filter()
        self._feedback.clear()

    def _apply_filter(self) -> None:
        self._table.filter(self._search.text())
        self._status.setText(f"{self._table.row_count()} / {len(self._rows)} dispositivos")

    def _on_selection(self, row) -> None:
        if not row:
            self._detail.clear()
            return
        self._detail.show_details(
            row.get("nombre", ""),
            [
                ("Departamento", row.get("departamento_nombre")),
                ("Usuario", row.get("usuario")),
                ("Sistema operativo", row.get("sistema_operativo")),
                ("Procesador", row.get("procesador")),
                ("RAM", row.get("ram")),
                ("Almacenamiento", row.get("almacenamiento")),
                ("Serie", row.get("num_serie")),
                ("MAC", row.get("mac_address")),
            ],
            badges=[(row.get("activo_str", ""), None)],
        )

    def _import_devices(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Importar equipos", "", "Excel/CSV (*.xlsx *.csv)")
        if not path:
            return
        try:
            from database.connection import get_engine
            from modules.equipos import importar_equipos_desde_lista
            from modules.software import listar_departamentos
            from utils.parser import parse_equipos_file

            with open(path, "rb") as f:
                equipos_data = parse_equipos_file(f.read(), path)
            with get_engine().begin() as db:
                result = importar_equipos_desde_lista(db, equipos_data, listar_departamentos(db))
            self._feedback.show_message(f"Equipos importados: {result}", "success")
            self._load_data()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"No se pudo importar:\n{exc}")

    def _export_devices(self) -> None:
        if not self._rows:
            self._feedback.show_message("No hay dispositivos para exportar.", "warning")
            return
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar equipos",
            f"Equipos_Asserta_{date.today().isoformat()}.xlsx",
            "Excel (*.xlsx)",
        )
        if not filename:
            return
        try:
            from modules.equipos import exportar_equipos_excel

            data = exportar_equipos_excel(self._rows, "Equipos")
            with open(filename, "wb") as f:
                f.write(data)
            self._feedback.show_message(f"Excel guardado en {filename}.", "success")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"No se pudo exportar:\n{exc}")

    def _on_error(self, msg: str) -> None:
        self._feedback.show_message(f"Error: {msg}", "error")
