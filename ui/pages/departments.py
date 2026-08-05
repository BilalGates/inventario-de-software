from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QFileDialog, QMessageBox, QPushButton, QTabWidget, QVBoxLayout, QWidget

from modules.simple_inventory import current_period
from ui.components.sortable_table import SortableTable
from ui.components.ui_kit import FeedbackBar, FilterBar, PageHeader
from ui.components.worker import run_in_thread

if TYPE_CHECKING:
    from ui.main_window import MainWindow


SOFTWARE_HEADERS = ["Programa", "Editor/Fabricante", "Versiones", "N equipos", "Equipos"]
SOFTWARE_KEYS = ["nombre", "fabricantes", "versiones", "n_equipos", "equipos"]
DEVICE_HEADERS = ["Equipo", "Usuario", "Estado", "Fecha importacion", "Programas"]
DEVICE_KEYS = ["nombre", "usuario", "estado_importacion", "fecha_importacion_str", "n_programas"]


def _fetch_department(periodo: str, departamento_id: int | None):
    from database.connection import get_engine
    from modules.simple_inventory import equipos_estado_mensual, software_por_departamento, validate_periodo
    from modules.software import listar_departamentos

    validate_periodo(periodo)
    with get_engine().connect() as db:
        departamentos = listar_departamentos(db)
        selected = departamento_id or (departamentos[0]["id"] if departamentos else None)
        software = software_por_departamento(periodo, selected, db=db) if selected else []
        equipos = equipos_estado_mensual(periodo, selected, db=db) if selected else []
    return departamentos, selected, software, equipos


def _export_excel(periodo: str) -> bytes:
    from modules.simple_inventory import exportar_inventario_excel

    return exportar_inventario_excel(periodo)


class DepartmentsPage(QWidget):
    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__()
        self.main_window = main_window
        self._departamentos: list[dict] = []
        self._thread = None
        self._pending_export_path: str | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        self._export_btn = QPushButton("Exportar Excel")
        self._export_btn.setObjectName("primary")
        self._export_btn.clicked.connect(self._export_all)
        header = PageHeader("Departamentos", "Software instalado por departamento y equipos donde aparece.")
        header.add_action(self._export_btn)
        layout.addWidget(header)

        self._feedback = FeedbackBar()
        layout.addWidget(self._feedback)

        toolbar = FilterBar()
        self._period_edit = FilterBar.search_box("YYYY-MM")
        self._period_edit.setText(current_period())
        self._period_edit.setMaximumWidth(120)
        self._period_edit.editingFinished.connect(self._load_data)
        toolbar.add_widget(self._period_edit)
        self._dept_combo = FilterBar.combo(min_width=240)
        self._dept_combo.currentIndexChanged.connect(self._load_data)
        toolbar.add_widget(self._dept_combo)
        self._refresh_btn = QPushButton("Actualizar")
        self._refresh_btn.clicked.connect(self._load_data)
        toolbar.add_widget(self._refresh_btn)
        self._import_btn = QPushButton("Importar software")
        self._import_btn.clicked.connect(lambda: self.main_window.navigate_to("import"))
        toolbar.add_widget(self._import_btn)
        toolbar.add_stretch()
        layout.addWidget(toolbar)

        self._tabs = QTabWidget()
        self._software_table = SortableTable(headers=SOFTWARE_HEADERS, keys=SOFTWARE_KEYS)
        self._software_table.set_empty_content(
            title="Sin software",
            message="Importa algun equipo de este departamento para ver el recuento.",
            icon="",
        )
        self._device_table = SortableTable(headers=DEVICE_HEADERS, keys=DEVICE_KEYS, badge_keys=["estado_importacion"])
        self._device_table.set_empty_content(
            title="Sin equipos",
            message="No hay equipos activos en este departamento.",
            icon="",
        )
        self._tabs.addTab(self._software_table, "Software")
        self._tabs.addTab(self._device_table, "Equipos")
        layout.addWidget(self._tabs, stretch=1)

    def on_activate(self) -> None:
        self._load_data()

    def _periodo(self) -> str:
        from modules.simple_inventory import validate_periodo

        return validate_periodo(self._period_edit.text())

    def _load_data(self) -> None:
        try:
            periodo = self._periodo()
        except ValueError as exc:
            self._feedback.show_message(str(exc), "warning")
            return
        self._feedback.show_message("Cargando departamento...", "info")
        self._thread = run_in_thread(
            self,
            _fetch_department,
            periodo,
            self._dept_combo.currentData(),
            on_done=self._on_loaded,
            on_error=self._on_error,
        )

    def _on_loaded(self, result) -> None:
        departamentos, selected, software, equipos = result
        self._sync_departamentos(departamentos, selected)
        self._software_table.load_data(software)
        self._device_table.load_data(equipos)
        self._feedback.clear()

    def _sync_departamentos(self, departamentos: list[dict], selected: int | None) -> None:
        self._departamentos = departamentos
        self._dept_combo.blockSignals(True)
        self._dept_combo.clear()
        for dept in departamentos:
            self._dept_combo.addItem(dept["nombre"], dept["id"])
        for i in range(self._dept_combo.count()):
            if self._dept_combo.itemData(i) == selected:
                self._dept_combo.setCurrentIndex(i)
                break
        self._dept_combo.blockSignals(False)

    def _export_all(self) -> None:
        try:
            periodo = self._periodo()
        except ValueError as exc:
            self._feedback.show_message(str(exc), "warning")
            return
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar inventario",
            f"Inventario_Asserta_{periodo}.xlsx",
            "Excel (*.xlsx)",
        )
        if not filename:
            return
        self._pending_export_path = filename
        self._export_btn.setEnabled(False)
        self._feedback.show_message("Generando Excel...", "info")
        self._thread = run_in_thread(self, _export_excel, periodo, on_done=self._on_export_ready, on_error=self._on_error)

    def _on_export_ready(self, data: bytes) -> None:
        self._export_btn.setEnabled(True)
        path = self._pending_export_path
        self._pending_export_path = None
        if not path:
            return
        try:
            with open(path, "wb") as f:
                f.write(data)
            self._feedback.show_message(f"Excel guardado en {path}.", "success")
        except OSError as exc:
            QMessageBox.critical(self, "Error", f"No se pudo guardar:\n{exc}")

    def _on_error(self, msg: str) -> None:
        self._export_btn.setEnabled(True)
        self._feedback.show_message(f"Error: {msg}", "error")
