"""
Importacion desde Panda Adaptive Defense: wizard de 3 pasos.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.components.sortable_table import SortableTable
from ui.components.ui_kit import FeedbackBar, PageHeader
from ui.components.worker import run_in_thread

if TYPE_CHECKING:
    from ui.main_window import MainWindow


def _fetch_equipos_all():
    from database.connection import get_engine
    from modules.equipos import listar_equipos
    with get_engine().connect() as db:
        return listar_equipos(db, solo_activos=True)


def _calcular_diff(equipo_id: int, text: str):
    from database.connection import get_engine
    from modules.importacion import calcular_diff
    from utils.parser import parse_paste
    programas = parse_paste(text)
    if not programas:
        return None, None
    with get_engine().connect() as db:
        diff = calcular_diff(equipo_id, programas, db)
    return programas, diff


def _calcular_diff_file(equipo_id: int, file_bytes: bytes, filename: str):
    from database.connection import get_engine
    from modules.importacion import calcular_diff
    from utils.parser import parse_file
    programas = parse_file(file_bytes, filename)
    if not programas:
        return None, None
    with get_engine().connect() as db:
        diff = calcular_diff(equipo_id, programas, db)
    return programas, diff


def _aplicar_diff(equipo_id: int, programas, diff, metodo: str):
    from database.connection import get_engine
    from modules.importacion import aplicar_diff
    with get_engine().begin() as db:
        importacion_id = aplicar_diff(equipo_id, programas, diff, db, metodo)
    return importacion_id, len(diff.get("nuevos", [])), len(diff.get("actualizados", []))


HDRS_DIFF = ["Estado", "Programa", "Fabricante", "Version"]
KEYS_DIFF = ["estado", "nombre", "fabricante", "version_str"]


class ImportPandaPage(QWidget):
    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__()
        self.main_window = main_window
        self._equipos: list[dict] = []
        self._pending_diff = None
        self._pending_programas = None
        self._pending_equipo_id = None
        self._pending_metodo = None
        self._thread = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        layout.addWidget(PageHeader("Importar Panda", "Carga un listado, revisa los cambios y confirma la importacion."))

        self._feedback = FeedbackBar()
        layout.addWidget(self._feedback)

        self._stack = QStackedWidget()
        layout.addWidget(self._stack, stretch=1)

        self._page_load = self._build_page_load()
        self._page_preview = self._build_page_preview()
        self._page_result = self._build_page_result()

        self._stack.addWidget(self._page_load)
        self._stack.addWidget(self._page_preview)
        self._stack.addWidget(self._page_result)

    def _build_page_load(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(12)

        form = QFormLayout()
        self._equipo_combo = QComboBox()
        self._equipo_combo.setMinimumWidth(320)
        form.addRow("Dispositivo destino:", self._equipo_combo)
        layout.addLayout(form)

        layout.addWidget(QLabel("Listado de Panda Adaptive Defense"))
        self._paste_area = QTextEdit()
        self._paste_area.setPlaceholderText(
            "Nombre\tEditor\tFecha de instalacion\tTamano\tVersion\n"
            "Adobe Acrobat\tAdobe\t18/05/2026\t1,2 GB\t26.001.21563"
        )
        self._paste_area.setFixedHeight(180)
        layout.addWidget(self._paste_area)

        btn_row = QHBoxLayout()
        self._analyze_btn = QPushButton("Analizar texto")
        self._analyze_btn.setObjectName("primary")
        self._analyze_btn.clicked.connect(self._analyze_paste)
        btn_row.addWidget(self._analyze_btn)

        self._file_btn = QPushButton("Cargar CSV/XLSX")
        self._file_btn.clicked.connect(self._upload_file)
        btn_row.addWidget(self._file_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        layout.addStretch()
        return w

    def _build_page_preview(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(12)

        self._preview_summary = QLabel("")
        self._preview_summary.setObjectName("labelSection")
        layout.addWidget(self._preview_summary)

        self._preview_table = SortableTable(headers=HDRS_DIFF, keys=KEYS_DIFF)
        layout.addWidget(self._preview_table, stretch=1)

        btn_row = QHBoxLayout()
        self._confirm_btn = QPushButton("Confirmar importacion")
        self._confirm_btn.setObjectName("primary")
        self._confirm_btn.clicked.connect(self._confirm_import)
        btn_row.addWidget(self._confirm_btn)

        self._cancel_btn = QPushButton("Volver")
        self._cancel_btn.clicked.connect(self._go_to_load)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        return w

    def _build_page_result(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(16)

        self._result_label = QLabel("")
        self._result_label.setWordWrap(True)
        layout.addWidget(self._result_label)

        btn_row = QHBoxLayout()
        self._view_inv_btn = QPushButton("Ver inventario")
        self._view_inv_btn.setObjectName("primary")
        self._view_inv_btn.clicked.connect(self._go_to_inventory)
        btn_row.addWidget(self._view_inv_btn)

        self._new_import_btn = QPushButton("Nueva importacion")
        self._new_import_btn.clicked.connect(self._go_to_load)
        btn_row.addWidget(self._new_import_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        layout.addStretch()
        return w

    def on_activate(self) -> None:
        self._thread = run_in_thread(self, _fetch_equipos_all, on_done=self._on_equipos_loaded)

    def _on_equipos_loaded(self, equipos: list[dict]) -> None:
        self._equipos = equipos
        current = self._equipo_combo.currentData()
        self._equipo_combo.blockSignals(True)
        self._equipo_combo.clear()
        for eq in equipos:
            self._equipo_combo.addItem(f"{eq['departamento_nombre']} - {eq['nombre']} (id {eq['id']})", eq["id"])
        for i in range(self._equipo_combo.count()):
            if self._equipo_combo.itemData(i) == current:
                self._equipo_combo.setCurrentIndex(i)
                break
        self._equipo_combo.blockSignals(False)

    def _analyze_paste(self) -> None:
        text = self._paste_area.toPlainText().strip()
        if not text:
            self._feedback.show_message("Pega el listado primero.", "warning")
            return
        equipo_id = self._equipo_combo.currentData()
        if not equipo_id:
            self._feedback.show_message("Selecciona un dispositivo.", "warning")
            return
        self._feedback.show_message("Analizando cambios...", "info")
        self._set_load_buttons_enabled(False)
        run_in_thread(self, _calcular_diff, equipo_id, text,
                      on_done=lambda r: self._on_diff_ready(r, "paste"),
                      on_error=self._on_analyze_error)

    def _upload_file(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar fichero", "", "CSV o XLSX (*.csv *.xlsx)")
        if not path:
            return
        equipo_id = self._equipo_combo.currentData()
        if not equipo_id:
            self._feedback.show_message("Selecciona un dispositivo.", "warning")
            return
        with open(path, "rb") as f:
            file_bytes = f.read()
        import os
        filename = os.path.basename(path)
        self._feedback.show_message("Analizando archivo...", "info")
        self._set_load_buttons_enabled(False)
        run_in_thread(self, _calcular_diff_file, equipo_id, file_bytes, filename,
                      on_done=lambda r: self._on_diff_ready(r, "file"),
                      on_error=self._on_analyze_error)

    def _on_analyze_error(self, msg: str) -> None:
        self._set_load_buttons_enabled(True)
        self._feedback.show_message(f"Error analizando datos: {msg}", "error")

    def _on_diff_ready(self, result, metodo: str) -> None:
        self._set_load_buttons_enabled(True)
        programas, diff = result
        if programas is None:
            self._feedback.show_message("No se detectaron programas en los datos.", "warning")
            return

        self._pending_programas = programas
        self._pending_diff = diff
        self._pending_equipo_id = self._equipo_combo.currentData()
        self._pending_metodo = metodo

        rows = []
        for item in diff.get("nuevos", []):
            rows.append({"estado": "Nuevo", "nombre": item.get("nombre", ""), "fabricante": item.get("fabricante", ""), "version_str": str(item.get("version", ""))})
        for item in diff.get("actualizados", []):
            rows.append({"estado": "Sin cambios", "nombre": item.get("nombre", ""), "fabricante": item.get("fabricante", ""), "version_str": str(item.get("version", ""))})
        for item in diff.get("cambios_version", []):
            rows.append({"estado": "Cambio version", "nombre": item.get("nombre", ""), "fabricante": item.get("fabricante", ""), "version_str": f"{item.get('version_anterior','')} -> {item.get('version_nueva','')}"})
        for item in diff.get("eliminados", []):
            rows.append({"estado": "Eliminado", "nombre": item.get("nombre", ""), "fabricante": item.get("fabricante", ""), "version_str": ""})

        self._preview_table.load_data(rows)
        n = len(diff.get("nuevos", []))
        a = len(diff.get("actualizados", []))
        c = len(diff.get("cambios_version", []))
        e = len(diff.get("eliminados", []))
        self._preview_summary.setText(
            f"{len(programas)} programas | Nuevos: {n} | Sin cambios: {a} | Cambio version: {c} | Eliminados: {e}"
        )
        self._feedback.clear()
        self._stack.setCurrentWidget(self._page_preview)

    def _confirm_import(self) -> None:
        if not self._pending_diff:
            return
        self._confirm_btn.setEnabled(False)
        self._feedback.show_message("Registrando importacion...", "info")
        run_in_thread(
            self,
            _aplicar_diff,
            self._pending_equipo_id,
            self._pending_programas,
            self._pending_diff,
            self._pending_metodo,
            on_done=self._on_import_done,
            on_error=self._on_import_error,
        )

    def _on_import_error(self, msg: str) -> None:
        self._confirm_btn.setEnabled(True)
        self._feedback.show_message(f"Error importando: {msg}", "error")
        QMessageBox.critical(self, "Error", msg)

    def _on_import_done(self, result) -> None:
        importacion_id, insertados, actualizados = result
        self._result_label.setText(
            f"<b>Importacion completada</b><br><br>"
            f"ID de importacion: {importacion_id}<br>"
            f"Registros insertados: {insertados}<br>"
            f"Registros actualizados: {actualizados}"
        )
        self._pending_diff = None
        self._pending_programas = None
        self._pending_equipo_id = None
        self._pending_metodo = None
        self._feedback.show_message("Importacion completada.", "success")
        self.main_window.set_status("Importacion completada")
        self._stack.setCurrentWidget(self._page_result)

    def _go_to_load(self) -> None:
        self._paste_area.clear()
        self._confirm_btn.setEnabled(True)
        self._feedback.clear()
        self._stack.setCurrentWidget(self._page_load)

    def _go_to_inventory(self) -> None:
        if self.main_window:
            self.main_window.navigate_to("software")

    def _set_load_buttons_enabled(self, enabled: bool) -> None:
        self._analyze_btn.setEnabled(enabled)
        self._file_btn.setEnabled(enabled)
