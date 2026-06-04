"""
Importación desde Panda Adaptive Defense — wizard de 3 pasos.
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


HDRS_DIFF = ["Estado", "Programa", "Fabricante", "Versión"]
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
        layout.setSpacing(0)

        title = QLabel("Importar Panda Adaptive Defense")
        title.setObjectName("labelTitle")
        layout.addWidget(title)

        self._stack = QStackedWidget()
        layout.addWidget(self._stack, stretch=1)

        self._page_load = self._build_page_load()
        self._page_preview = self._build_page_preview()
        self._page_result = self._build_page_result()

        self._stack.addWidget(self._page_load)
        self._stack.addWidget(self._page_preview)
        self._stack.addWidget(self._page_result)

    # ── Paso 1 — Cargar datos ────────────────────────────────────────

    def _build_page_load(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(12)

        form = QFormLayout()
        self._equipo_combo = QComboBox()
        self._equipo_combo.setMinimumWidth(300)
        form.addRow("Dispositivo destino:", self._equipo_combo)
        layout.addLayout(form)

        layout.addWidget(QLabel("Pegar output de Panda Adaptive Defense:"))
        self._paste_area = QTextEdit()
        self._paste_area.setPlaceholderText(
            "Nombre\tEditor\tFecha de instalación\tTamaño\tVersión\n"
            "Adobe Acrobat\tAdobe\t18/05/2026\t1,2 GB\t26.001.21563"
        )
        self._paste_area.setFixedHeight(180)
        layout.addWidget(self._paste_area)

        btn_row = QHBoxLayout()
        self._analyze_btn = QPushButton("Analizar texto")
        self._analyze_btn.setObjectName("primary")
        self._analyze_btn.clicked.connect(self._analyze_paste)
        btn_row.addWidget(self._analyze_btn)
        self._file_btn = QPushButton("Cargar archivo CSV/XLSX...")
        self._file_btn.clicked.connect(self._upload_file)
        btn_row.addWidget(self._file_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._load_error = QLabel("")
        self._load_error.setObjectName("labelMuted")
        layout.addWidget(self._load_error)
        layout.addStretch()
        return w

    # ── Paso 2 — Previsualización ───────────────────────────────────

    def _build_page_preview(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(12)

        self._preview_summary = QLabel("")
        self._preview_summary.setObjectName("labelSection")
        layout.addWidget(self._preview_summary)

        self._preview_table = SortableTable(headers=HDRS_DIFF, keys=KEYS_DIFF)
        layout.addWidget(self._preview_table, stretch=1)

        btn_row = QHBoxLayout()
        self._confirm_btn = QPushButton("Confirmar importación")
        self._confirm_btn.setObjectName("primary")
        self._confirm_btn.clicked.connect(self._confirm_import)
        btn_row.addWidget(self._confirm_btn)
        self._cancel_btn = QPushButton("Cancelar")
        self._cancel_btn.clicked.connect(self._go_to_load)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        return w

    # ── Paso 3 — Resultado ──────────────────────────────────────────

    def _build_page_result(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(16)

        self._result_label = QLabel("")
        self._result_label.setWordWrap(True)
        layout.addWidget(self._result_label)

        btn_row = QHBoxLayout()
        self._view_inv_btn = QPushButton("Ver en inventario")
        self._view_inv_btn.setObjectName("primary")
        self._view_inv_btn.clicked.connect(self._go_to_inventory)
        btn_row.addWidget(self._view_inv_btn)
        self._new_import_btn = QPushButton("Nueva importación")
        self._new_import_btn.clicked.connect(self._go_to_load)
        btn_row.addWidget(self._new_import_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        layout.addStretch()
        return w

    # ── Lógica ──────────────────────────────────────────────────────

    def on_activate(self) -> None:
        self._thread = run_in_thread(self, _fetch_equipos_all, on_done=self._on_equipos_loaded)

    def _on_equipos_loaded(self, equipos: list[dict]) -> None:
        self._equipos = equipos
        self._equipo_combo.clear()
        for eq in equipos:
            self._equipo_combo.addItem(f"{eq['departamento_nombre']} — {eq['nombre']} (id {eq['id']})", eq["id"])

    def _analyze_paste(self) -> None:
        text = self._paste_area.toPlainText().strip()
        if not text:
            self._load_error.setText("Pega el listado primero.")
            return
        equipo_id = self._equipo_combo.currentData()
        if not equipo_id:
            self._load_error.setText("Selecciona un dispositivo.")
            return
        self._load_error.setText("")
        self._analyze_btn.setEnabled(False)
        run_in_thread(self, _calcular_diff, equipo_id, text,
                      on_done=lambda r: self._on_diff_ready(r, "paste"),
                      on_error=lambda m: self._on_analyze_error(m))

    def _upload_file(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar fichero", "", "CSV o XLSX (*.csv *.xlsx)")
        if not path:
            return
        equipo_id = self._equipo_combo.currentData()
        if not equipo_id:
            self._load_error.setText("Selecciona un dispositivo.")
            return
        with open(path, "rb") as f:
            file_bytes = f.read()
        import os
        filename = os.path.basename(path)
        run_in_thread(self, _calcular_diff_file, equipo_id, file_bytes, filename,
                      on_done=lambda r: self._on_diff_ready(r, "file"),
                      on_error=lambda m: self._on_analyze_error(m))

    def _on_analyze_error(self, msg: str) -> None:
        self._analyze_btn.setEnabled(True)
        self._load_error.setText(f"Error: {msg}")

    def _on_diff_ready(self, result, metodo: str) -> None:
        self._analyze_btn.setEnabled(True)
        programas, diff = result
        if programas is None:
            self._load_error.setText("No se detectaron programas en los datos.")
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
            rows.append({"estado": "Cambio versión", "nombre": item.get("nombre", ""), "fabricante": item.get("fabricante", ""), "version_str": f"{item.get('version_anterior','')} → {item.get('version_nueva','')}"})
        for item in diff.get("eliminados", []):
            rows.append({"estado": "Eliminado", "nombre": item.get("nombre", ""), "fabricante": item.get("fabricante", ""), "version_str": ""})

        self._preview_table.load_data(rows)
        n = len(diff.get("nuevos", []))
        a = len(diff.get("actualizados", []))
        c = len(diff.get("cambios_version", []))
        e = len(diff.get("eliminados", []))
        self._preview_summary.setText(
            f"{len(programas)} programas  |  Nuevos: {n}  Sin cambios: {a}  Cambio versión: {c}  Eliminados: {e}"
        )
        self._stack.setCurrentWidget(self._page_preview)

    def _confirm_import(self) -> None:
        if not self._pending_diff:
            return
        self._confirm_btn.setEnabled(False)
        run_in_thread(
            self,
            _aplicar_diff,
            self._pending_equipo_id,
            self._pending_programas,
            self._pending_diff,
            self._pending_metodo,
            on_done=self._on_import_done,
            on_error=lambda m: (
                self._confirm_btn.setEnabled(True),
                QMessageBox.critical(self, "Error", m),
            ),
        )

    def _on_import_done(self, result) -> None:
        importacion_id, insertados, actualizados = result
        self._result_label.setText(
            f"<b>Importación completada</b><br><br>"
            f"ID de importación: {importacion_id}<br>"
            f"Registros insertados: {insertados}<br>"
            f"Registros actualizados: {actualizados}"
        )
        self._pending_diff = None
        self._pending_programas = None
        self._pending_equipo_id = None
        self._pending_metodo = None
        self._stack.setCurrentWidget(self._page_result)

    def _go_to_load(self) -> None:
        self._paste_area.clear()
        self._load_error.setText("")
        self._confirm_btn.setEnabled(True)
        self._stack.setCurrentWidget(self._page_load)

    def _go_to_inventory(self) -> None:
        if self.main_window:
            self.main_window.navigate_to("software")
