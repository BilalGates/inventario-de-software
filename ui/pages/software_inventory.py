"""
Inventario de software: tabla principal con filtros, edicion y exportacion.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.components.sortable_table import SortableTable
from ui.components.ui_kit import FeedbackBar, FilterBar, PageHeader
from ui.components.worker import run_in_thread

if TYPE_CHECKING:
    from ui.main_window import MainWindow


HEADERS = ["ID", "Codigo", "Nombre", "Fabricante", "Version", "Dispositivos", "Departamento", "Guia 105", "Clasificacion", "Observaciones"]
KEYS = ["id", "codigo", "nombre", "fabricante", "version_referencia", "dispositivos", "departamento_nombre", "en_guia_105_str", "clasificacion_informacion", "observaciones"]


def _fetch_all_software():
    from database.connection import get_engine
    from modules.software import listar_inventario_empresa, listar_departamentos
    with get_engine().connect() as db:
        depts = listar_departamentos(db)
        rows = listar_inventario_empresa(db)
    dept_map = {d["id"]: d["nombre"] for d in depts}
    result = []
    for row in rows:
        r = dict(row)
        r["departamento_nombre"] = dept_map.get(r.get("departamento_id", 0), "")
        r["en_guia_105_str"] = "Pendiente" if r.get("en_guia_105") is None else ("Si" if r.get("en_guia_105") else "No")
        r["version_referencia"] = str(r.get("version_referencia") or "")
        result.append(r)
    return result


def _fetch_software_by_dept(dept_id: int):
    from database.connection import get_engine
    from modules.software import listar_inventario, obtener_departamento
    with get_engine().connect() as db:
        dept = obtener_departamento(db, dept_id)
        rows = listar_inventario(db, dept_id, en_guia_105="todos")
    dept_name = dept["nombre"] if dept else ""
    result = []
    for row in rows:
        r = dict(row)
        r["departamento_nombre"] = dept_name
        r["en_guia_105_str"] = "Pendiente" if r.get("en_guia_105") is None else ("Si" if r.get("en_guia_105") else "No")
        r["version_referencia"] = str(r.get("version_referencia") or "")
        result.append(r)
    return result


def _fetch_departamentos():
    from database.connection import get_engine
    from modules.software import listar_departamentos
    with get_engine().connect() as db:
        return listar_departamentos(db)


class SoftwareInventoryPage(QWidget):
    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__()
        self.main_window = main_window
        self._all_data: list[dict] = []
        self._departamentos: list[dict] = []
        self._thread = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        layout.addWidget(PageHeader("Inventario de Software", "Busca, filtra y revisa el software registrado. Doble clic para editar."))

        self._feedback = FeedbackBar()
        layout.addWidget(self._feedback)

        toolbar = FilterBar()
        self._search = FilterBar.search_box("Buscar en todas las columnas...")
        self._search.textChanged.connect(self._apply_filters)
        toolbar.add_widget(self._search, stretch=1)

        self._dept_combo = QComboBox()
        self._dept_combo.setMinimumWidth(180)
        self._dept_combo.addItem("Todos los departamentos", None)
        self._dept_combo.currentIndexChanged.connect(self._on_dept_changed)
        toolbar.add_widget(self._dept_combo)

        self._guia_combo = QComboBox()
        self._guia_combo.addItems(["Todos", "Si", "No", "Pendiente"])
        self._guia_combo.currentIndexChanged.connect(self._apply_filters)
        toolbar.add_widget(self._guia_combo)

        self._export_btn = QPushButton("Exportar CSV")
        self._export_btn.clicked.connect(self._export_csv)
        toolbar.add_widget(self._export_btn)
        layout.addWidget(toolbar)

        self._table = SortableTable(headers=HEADERS, keys=KEYS)
        self._table.row_activated.connect(self._on_row_activated)
        self._table.selection_changed.connect(self._on_selection_changed)
        layout.addWidget(self._table, stretch=1)

        self._status_label = QLabel("")
        self._status_label.setObjectName("labelMuted")
        layout.addWidget(self._status_label)

    def on_activate(self) -> None:
        self._load_departamentos()
        self._load_data()

    def _load_departamentos(self) -> None:
        run_in_thread(self, _fetch_departamentos, on_done=self._on_depts_loaded)

    def _on_depts_loaded(self, depts: list[dict]) -> None:
        self._departamentos = depts
        self._dept_combo.blockSignals(True)
        current = self._dept_combo.currentData()
        self._dept_combo.clear()
        self._dept_combo.addItem("Todos los departamentos", None)
        for d in depts:
            self._dept_combo.addItem(d["nombre"], d["id"])
        for i in range(self._dept_combo.count()):
            if self._dept_combo.itemData(i) == current:
                self._dept_combo.setCurrentIndex(i)
                break
        self._dept_combo.blockSignals(False)

    def _load_data(self) -> None:
        self._feedback.show_message("Cargando inventario de software...", "info")
        dept_id = self._dept_combo.currentData()
        if dept_id:
            self._thread = run_in_thread(self, _fetch_software_by_dept, dept_id,
                                         on_done=self._on_data_loaded, on_error=self._on_error)
        else:
            self._thread = run_in_thread(self, _fetch_all_software,
                                         on_done=self._on_data_loaded, on_error=self._on_error)

    def _on_data_loaded(self, data: list[dict]) -> None:
        self._all_data = data
        self._apply_filters()
        self._feedback.clear()

    def _apply_filters(self) -> None:
        guia_filter = self._guia_combo.currentText()
        search_text = self._search.text()

        if guia_filter == "Todos":
            filtered = self._all_data
        else:
            filtered = [r for r in self._all_data if r.get("en_guia_105_str") == guia_filter]

        self._table.load_data(filtered)
        self._table.filter(search_text)
        self._status_label.setText(f"{self._table.row_count()} / {len(self._all_data)} registros")

    def _on_dept_changed(self) -> None:
        self._load_data()

    def _on_row_activated(self, row: dict) -> None:
        dlg = SoftwareEditDialog(row, self._departamentos, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._save_software(row["id"], dlg.get_values())

    def _on_selection_changed(self, row) -> None:
        pass

    def _save_software(self, software_id: int, values: dict) -> None:
        try:
            from database.connection import get_engine
            from modules.software import actualizar_software_revision
            with get_engine().begin() as db:
                actualizar_software_revision(db, software_id, values)
            self._feedback.show_message("Software actualizado.", "success")
            self._load_data()
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"No se pudo guardar:\n{exc}")

    def _on_error(self, msg: str) -> None:
        self._feedback.show_message(f"Error cargando datos: {msg}", "error")
        QMessageBox.critical(self, "Error", f"Error cargando datos:\n{msg}")

    def _export_csv(self) -> None:
        if not self._all_data:
            self._feedback.show_message("No hay datos para exportar.", "warning")
            return
        from PySide6.QtWidgets import QFileDialog
        from datetime import date as dt
        filename, _ = QFileDialog.getSaveFileName(
            self, "Exportar CSV",
            f"inventario_software_{dt.today().isoformat()}.csv",
            "CSV (*.csv)",
        )
        if not filename:
            return
        import csv
        self._export_btn.setEnabled(False)
        try:
            with open(filename, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=KEYS, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(self._all_data)
            self._feedback.show_message(f"CSV guardado en {filename}.", "success")
            self.main_window.set_status("CSV exportado")
        finally:
            self._export_btn.setEnabled(True)


class SoftwareEditDialog(QDialog):
    def __init__(self, row: dict, departamentos: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar software")
        self.setMinimumWidth(480)
        self._build_ui(row, departamentos)

    def _build_ui(self, row: dict, departamentos: list[dict]) -> None:
        layout = QFormLayout(self)
        layout.setSpacing(10)

        self._nombre = QLineEdit(str(row.get("nombre") or ""))
        layout.addRow("Nombre:", self._nombre)

        self._fabricante = QLineEdit(str(row.get("fabricante") or ""))
        layout.addRow("Fabricante:", self._fabricante)

        self._version = QLineEdit(str(row.get("version_referencia") or ""))
        layout.addRow("Version (texto):", self._version)

        self._clasificacion = QComboBox()
        for opt in ("Media", "Baja", "Alta", "Muy Alta"):
            self._clasificacion.addItem(opt)
        idx = self._clasificacion.findText(str(row.get("clasificacion_informacion") or "Media"))
        if idx >= 0:
            self._clasificacion.setCurrentIndex(idx)
        layout.addRow("Clasificacion:", self._clasificacion)

        self._guia = QComboBox()
        self._guia.addItems(["Pendiente", "Si", "No"])
        val_map = {True: "Si", False: "No", None: "Pendiente"}
        current = val_map.get(row.get("en_guia_105"), "Pendiente")
        self._guia.setCurrentText(current)
        layout.addRow("Guia 105:", self._guia)

        self._obs = QTextEdit(str(row.get("observaciones") or ""))
        self._obs.setFixedHeight(80)
        layout.addRow("Observaciones:", self._obs)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_values(self) -> dict:
        guia_raw = self._guia.currentText()
        return {
            "fabricante": self._fabricante.text().strip() or None,
            "version_referencia": self._version.text().strip() or None,
            "clasificacion_informacion": self._clasificacion.currentText(),
            "en_guia_105": {"Si": True, "No": False}.get(guia_raw),
            "observaciones_elena": self._obs.toPlainText().strip() or None,
        }
