"""
Inventario de software: tabla con filtros, badges de estado y panel de detalle.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.components.detail_panel import DetailPanel
from ui.components.sortable_table import SortableTable
from ui.components.ui_kit import FeedbackBar, FilterBar, PageHeader
from ui.components.worker import run_in_thread

if TYPE_CHECKING:
    from ui.main_window import MainWindow


HEADERS = ["Nombre", "Editor", "Versión", "Equipos", "Estado", "Última detección"]
KEYS = ["nombre", "fabricante", "version", "n_equipos", "estado", "fecha"]


def _guia_str(value) -> str:
    return "Pendiente" if value is None else ("Sí" if value else "No")


def _n_equipos(dispositivos: str) -> str:
    if not dispositivos:
        return "0"
    return str(len([x for x in str(dispositivos).split(",") if x.strip()]))


def _normalize(rows: list[dict], dept_view: bool) -> list[dict]:
    out = []
    for raw in rows:
        r = dict(raw)
        if dept_view:
            fabricante = r.get("fabricante") or ""
            version = str(r.get("version_referencia") or "")
            departamento = r.get("departamento_nombre") or ""
            clasificacion = r.get("clasificacion_informacion") or ""
        else:
            fabricante = r.get("fabricantes") or ""
            version = str(r.get("versiones") or "")
            departamento = r.get("departamentos") or ""
            clasificacion = r.get("clasificaciones") or ""
        dispositivos = r.get("dispositivos") or ""
        r.update({
            "nombre": r.get("nombre") or "",
            "fabricante": fabricante,
            "version": version,
            "dispositivos": dispositivos,
            "departamento": departamento,
            "clasificacion": clasificacion,
            "n_equipos": _n_equipos(dispositivos),
            "estado": _guia_str(r.get("en_guia_105")),
            "fecha": str(r.get("fecha_ultima_actualizacion") or "")[:10],
        })
        out.append(r)
    return out


def _fetch_all_software():
    from database.connection import get_engine
    from modules.software import listar_departamentos, listar_inventario_empresa
    with get_engine().connect() as db:
        depts = listar_departamentos(db)
        rows = listar_inventario_empresa(db)
    return depts, _normalize(rows, dept_view=False)


def _fetch_software_by_dept(dept_id: int):
    from database.connection import get_engine
    from modules.software import listar_departamentos, listar_inventario
    with get_engine().connect() as db:
        depts = listar_departamentos(db)
        rows = listar_inventario(db, dept_id, en_guia_105="todos")
    return depts, _normalize(rows, dept_view=True)


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

        self._import_btn = QPushButton("Importar Panda")
        self._import_btn.clicked.connect(lambda: self.main_window.navigate_to("import"))
        self._export_btn = QPushButton("Exportar CSV")
        self._export_btn.setObjectName("primary")
        self._export_btn.clicked.connect(self._export_csv)
        header = PageHeader("Software", "Catálogo consolidado de software detectado en los equipos.")
        header.add_action(self._import_btn)
        header.add_action(self._export_btn)
        layout.addWidget(header)

        self._feedback = FeedbackBar()
        layout.addWidget(self._feedback)

        toolbar = FilterBar()
        self._search = FilterBar.search_box("Buscar por nombre, editor o versión...")
        self._search.textChanged.connect(self._apply_filters)
        toolbar.add_widget(self._search, stretch=1)

        self._dept_combo = QComboBox()
        self._dept_combo.setMinimumWidth(180)
        self._dept_combo.addItem("Todos los departamentos", None)
        self._dept_combo.currentIndexChanged.connect(self._on_dept_changed)
        toolbar.add_widget(self._dept_combo)

        self._guia_combo = QComboBox()
        self._guia_combo.setMinimumWidth(140)
        for label, data in (("Estado: todos", "Todos"), ("En Guía 105", "Sí"),
                            ("No en Guía 105", "No"), ("Pendiente", "Pendiente")):
            self._guia_combo.addItem(label, data)
        self._guia_combo.currentIndexChanged.connect(self._apply_filters)
        toolbar.add_widget(self._guia_combo)

        self._clear_btn = QPushButton("Limpiar")
        self._clear_btn.setObjectName("subtle")
        self._clear_btn.clicked.connect(self._clear_filters)
        toolbar.add_widget(self._clear_btn)
        layout.addWidget(toolbar)

        body = QHBoxLayout()
        body.setSpacing(12)
        self._table = SortableTable(headers=HEADERS, keys=KEYS, badge_keys=["estado"])
        self._table.set_empty_content(
            title="Sin software",
            message="No hay software para estos filtros. Importa desde Panda o limpia los filtros.",
            icon="🔎",
            action_text="Importar desde Panda",
            on_action=lambda: self.main_window.navigate_to("import"),
        )
        self._table.row_activated.connect(self._edit_row)
        self._table.selection_changed.connect(self._on_selection)
        body.addWidget(self._table, stretch=1)

        self._detail = DetailPanel()
        self._detail.closed.connect(self._table.clear_selection)
        body.addWidget(self._detail)
        layout.addLayout(body, stretch=1)

        self._status_label = QLabel("")
        self._status_label.setObjectName("labelMuted")
        layout.addWidget(self._status_label)

    # ------------------------------------------------------------------
    def on_activate(self) -> None:
        self._load_data()

    def apply_navigation(self, payload: dict) -> None:
        guia = payload.get("guia")
        if guia:
            for i in range(self._guia_combo.count()):
                if self._guia_combo.itemData(i) == guia:
                    self._guia_combo.setCurrentIndex(i)
                    break
            self._apply_filters()

    def _load_data(self) -> None:
        self._feedback.show_message("Cargando inventario de software...", "info")
        dept_id = self._dept_combo.currentData()
        fetch = (lambda: _fetch_software_by_dept(dept_id)) if dept_id else _fetch_all_software
        self._thread = run_in_thread(self, fetch, on_done=self._on_data_loaded, on_error=self._on_error)

    def _on_data_loaded(self, result) -> None:
        depts, data = result
        self._departamentos = depts
        self._sync_dept_combo(depts)
        self._all_data = data
        self._apply_filters()
        self._feedback.clear()

    def _sync_dept_combo(self, depts: list[dict]) -> None:
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

    def _apply_filters(self) -> None:
        guia = self._guia_combo.currentData()
        if guia in (None, "Todos"):
            filtered = self._all_data
        else:
            filtered = [r for r in self._all_data if r.get("estado") == guia]
        self._table.load_data(filtered)
        self._table.filter(self._search.text())
        self._status_label.setText(f"{self._table.row_count()} / {len(self._all_data)} registros")
        self._detail.clear()

    def _clear_filters(self) -> None:
        self._search.clear()
        self._guia_combo.setCurrentIndex(0)
        self._apply_filters()

    def _on_dept_changed(self) -> None:
        self._load_data()

    def _on_selection(self, row) -> None:
        if not row:
            self._detail.clear()
            return
        edit_btn = QPushButton("Editar revisión")
        edit_btn.setObjectName("primary")
        edit_btn.clicked.connect(lambda: self._edit_row(row))
        self._detail.show_details(
            title=row.get("nombre", ""),
            badges=[(row.get("estado", "Pendiente"), None)],
            rows=[
                ("Editor", row.get("fabricante")),
                ("Versión(es)", row.get("version")),
                ("Departamento(s)", row.get("departamento")),
                ("Equipos afectados", row.get("dispositivos")),
                ("Clasificación", row.get("clasificacion")),
                ("Observaciones ENS", row.get("observaciones")),
                ("Última detección", row.get("fecha")),
            ],
            actions=[edit_btn],
        )

    def _edit_row(self, row: dict) -> None:
        dlg = SoftwareEditDialog(row, self._departamentos, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._save_software(row["id"], dlg.get_values())

    def _save_software(self, software_id: int, values: dict) -> None:
        try:
            from database.connection import get_engine
            from modules.software import actualizar_software_revision
            with get_engine().begin() as db:
                actualizar_software_revision(db, software_id, values)
            self._feedback.show_message("Software actualizado.", "success")
            self._load_data()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"No se pudo guardar:\n{exc}")

    def _on_error(self, msg: str) -> None:
        self._feedback.show_message(f"Error cargando datos: {msg}", "error")

    def _export_csv(self) -> None:
        if not self._all_data:
            self._feedback.show_message("No hay datos para exportar.", "warning")
            return
        from datetime import date as dt

        from PySide6.QtWidgets import QFileDialog
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
            fields = ["nombre", "fabricante", "version", "departamento", "dispositivos", "estado", "clasificacion", "fecha"]
            with open(filename, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
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
        self._build_ui(row)

    def _build_ui(self, row: dict) -> None:
        layout = QFormLayout(self)
        layout.setSpacing(10)

        self._nombre = QLineEdit(str(row.get("nombre") or ""))
        self._nombre.setReadOnly(True)
        layout.addRow("Nombre:", self._nombre)

        self._fabricante = QLineEdit(str(row.get("fabricante") or ""))
        layout.addRow("Editor:", self._fabricante)

        self._version = QLineEdit(str(row.get("version") or ""))
        layout.addRow("Versión (texto):", self._version)

        self._clasificacion = QComboBox()
        for opt in ("Baja", "Media", "Alta", "Muy Alta"):
            self._clasificacion.addItem(opt)
        idx = self._clasificacion.findText(str(row.get("clasificacion") or "Media"))
        if idx >= 0:
            self._clasificacion.setCurrentIndex(idx)
        layout.addRow("Clasificación:", self._clasificacion)

        self._guia = QComboBox()
        self._guia.addItems(["Pendiente", "Sí", "No"])
        self._guia.setCurrentText(row.get("estado", "Pendiente"))
        layout.addRow("¿En Guía 105?:", self._guia)

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
            "en_guia_105": {"Sí": True, "No": False}.get(guia_raw),
            "observaciones_elena": self._obs.toPlainText().strip() or None,
        }
