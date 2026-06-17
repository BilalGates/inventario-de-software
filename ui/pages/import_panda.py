"""
Importación desde Panda Adaptive Defense — asistente de 4 pasos:
1) Origen  2) Validar  3) Revisar cambios  4) Aplicar (con resumen/confirmación).
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
from ui.components.ui_kit import FeedbackBar, PageHeader, SectionCard
from ui.components.worker import run_in_thread
from ui.tokens import SPACING

if TYPE_CHECKING:
    from ui.main_window import MainWindow


EXAMPLE = (
    "Adobe Acrobat Reader\tAdobe Systems\t18/05/2026\t1,2 GB\t26.001.21563\n"
    "AnyDesk\tAnyDesk Software GmbH\t10/03/2026\t2 MB\tad 9.0.10\n"
    "7-Zip 23.01 (x64 edition)\tIgor Pavlov\t12/02/2026\t5,2 MB\t23.01"
)

STEPS = ["Origen", "Validar", "Revisar", "Aplicar"]


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


def _aplicar_diff(equipo_id: int, programas, diff, metodo: str, dept_id):
    from database.connection import get_engine
    from modules.autorizado import autorizar_exclusivos_automaticamente
    from modules.importacion import aplicar_diff, contar_reactivaciones_pendientes
    with get_engine().begin() as db:
        importacion_id = aplicar_diff(equipo_id, programas, diff, db, metodo)
        exclusivos = autorizar_exclusivos_automaticamente(db, dept_id) if dept_id else 0
        pendientes = contar_reactivaciones_pendientes(db, dept_id)
    return importacion_id, exclusivos, pendientes


HDRS_DIFF = ["Estado", "Programa", "Fabricante", "Versión"]
KEYS_DIFF = ["estado", "nombre", "fabricante", "version_str"]


class _StepIndicator(QWidget):
    def __init__(self) -> None:
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(SPACING["sm"])
        self._labels: list[QLabel] = []
        for i, name in enumerate(STEPS, start=1):
            lbl = QLabel(f"{i}. {name}")
            lbl.setObjectName("labelMuted")
            self._labels.append(lbl)
            row.addWidget(lbl)
            if i < len(STEPS):
                sep = QLabel("→")
                sep.setObjectName("labelMuted")
                row.addWidget(sep)
        row.addStretch()

    def set_step(self, index: int) -> None:
        for i, lbl in enumerate(self._labels):
            if i == index:
                lbl.setObjectName("labelSection")
            elif i < index:
                lbl.setObjectName("labelSecondary")
            else:
                lbl.setObjectName("labelMuted")
            lbl.style().unpolish(lbl)
            lbl.style().polish(lbl)


class ImportPandaPage(QWidget):
    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__()
        self.main_window = main_window
        self._equipos: list[dict] = []
        self._programas = None
        self._diff = None
        self._equipo_id = None
        self._metodo = None
        self._thread = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        layout.addWidget(PageHeader("Importar Panda", "Asistente guiado para cruzar un listado de Panda con el inventario."))

        self._indicator = _StepIndicator()
        layout.addWidget(self._indicator)

        self._feedback = FeedbackBar()
        layout.addWidget(self._feedback)

        self._stack = QStackedWidget()
        layout.addWidget(self._stack, stretch=1)
        self._stack.addWidget(self._build_step_source())
        self._stack.addWidget(self._build_step_validate())
        self._stack.addWidget(self._build_step_review())
        self._stack.addWidget(self._build_step_apply())
        self._go_step(0)

    # ── Paso 1: Origen ─────────────────────────────────────────────
    def _build_step_source(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(SPACING["md"])

        form = QFormLayout()
        self._equipo_combo = QComboBox()
        self._equipo_combo.setMinimumWidth(340)
        form.addRow("Dispositivo destino:", self._equipo_combo)
        layout.addLayout(form)

        help_lbl = QLabel(
            "Pega el listado copiado de Panda (columnas separadas por tabulador):\n"
            "Nombre · Editor · Fecha de instalación · Tamaño · Versión"
        )
        help_lbl.setObjectName("labelMuted")
        layout.addWidget(help_lbl)

        self._paste_area = QTextEdit()
        self._paste_area.setPlaceholderText("Pega aquí el listado de Panda Adaptive Defense...")
        self._paste_area.setMinimumHeight(180)
        layout.addWidget(self._paste_area)

        btn_row = QHBoxLayout()
        self._analyze_btn = QPushButton("Validar datos")
        self._analyze_btn.setObjectName("primary")
        self._analyze_btn.clicked.connect(self._analyze_paste)
        btn_row.addWidget(self._analyze_btn)
        self._file_btn = QPushButton("Cargar CSV/XLSX...")
        self._file_btn.clicked.connect(self._upload_file)
        btn_row.addWidget(self._file_btn)
        self._example_btn = QPushButton("Ver ejemplo")
        self._example_btn.setObjectName("subtle")
        self._example_btn.clicked.connect(lambda: self._paste_area.setPlainText(EXAMPLE))
        btn_row.addWidget(self._example_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        layout.addStretch()
        return w

    # ── Paso 2: Validar ────────────────────────────────────────────
    def _build_step_validate(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(SPACING["md"])

        self._validate_card = SectionCard("Validación de los datos")
        self._validate_info = QLabel("")
        self._validate_info.setObjectName("labelSecondary")
        self._validate_info.setWordWrap(True)
        self._validate_card.add_widget(self._validate_info)
        layout.addWidget(self._validate_card)
        layout.addStretch()

        btn_row = QHBoxLayout()
        back = QPushButton("Atrás")
        back.clicked.connect(lambda: self._go_step(0))
        btn_row.addWidget(back)
        self._to_review_btn = QPushButton("Revisar cambios")
        self._to_review_btn.setObjectName("primary")
        self._to_review_btn.clicked.connect(lambda: self._go_step(2))
        btn_row.addWidget(self._to_review_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        return w

    # ── Paso 3: Revisar ────────────────────────────────────────────
    def _build_step_review(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(SPACING["md"])

        self._review_summary = QLabel("")
        self._review_summary.setObjectName("labelSecondary")
        layout.addWidget(self._review_summary)

        self._review_table = SortableTable(headers=HDRS_DIFF, keys=KEYS_DIFF, badge_keys=["estado"])
        layout.addWidget(self._review_table, stretch=1)

        btn_row = QHBoxLayout()
        back = QPushButton("Atrás")
        back.clicked.connect(lambda: self._go_step(1))
        btn_row.addWidget(back)
        self._to_apply_btn = QPushButton("Continuar")
        self._to_apply_btn.setObjectName("primary")
        self._to_apply_btn.clicked.connect(self._prepare_apply)
        btn_row.addWidget(self._to_apply_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        return w

    # ── Paso 4: Aplicar ────────────────────────────────────────────
    def _build_step_apply(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(SPACING["md"])

        self._apply_card = SectionCard("Resumen de la importación")
        self._apply_summary = QLabel("")
        self._apply_summary.setObjectName("labelSecondary")
        self._apply_summary.setWordWrap(True)
        self._apply_card.add_widget(self._apply_summary)
        layout.addWidget(self._apply_card)
        layout.addStretch()

        btn_row = QHBoxLayout()
        self._cancel_btn = QPushButton("Cancelar")
        self._cancel_btn.clicked.connect(self._reset)
        btn_row.addWidget(self._cancel_btn)
        self._apply_btn = QPushButton("Aplicar importación")
        self._apply_btn.setObjectName("primary")
        self._apply_btn.clicked.connect(self._confirm_import)
        btn_row.addWidget(self._apply_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        return w

    # ── Navegación de pasos ────────────────────────────────────────
    def _go_step(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        self._indicator.set_step(index)

    # ── Datos ──────────────────────────────────────────────────────
    def on_activate(self) -> None:
        self._thread = run_in_thread(self, _fetch_equipos_all, on_done=self._on_equipos_loaded)

    def _on_equipos_loaded(self, equipos: list[dict]) -> None:
        self._equipos = equipos
        current = self._equipo_combo.currentData()
        self._equipo_combo.blockSignals(True)
        self._equipo_combo.clear()
        for eq in equipos:
            self._equipo_combo.addItem(f"{eq['departamento_nombre']} · {eq['nombre']}", eq["id"])
        for i in range(self._equipo_combo.count()):
            if self._equipo_combo.itemData(i) == current:
                self._equipo_combo.setCurrentIndex(i)
                break
        self._equipo_combo.blockSignals(False)

    def _analyze_paste(self) -> None:
        text = self._paste_area.toPlainText().strip()
        if not text:
            self._feedback.show_message("Pega el listado primero o usa «Ver ejemplo».", "warning")
            return
        equipo_id = self._equipo_combo.currentData()
        if not equipo_id:
            self._feedback.show_message("Selecciona un dispositivo destino.", "warning")
            return
        self._feedback.show_message("Validando y analizando cambios...", "info")
        self._set_buttons_enabled(False)
        run_in_thread(self, _calcular_diff, equipo_id, text,
                      on_done=lambda r: self._on_diff_ready(r, "paste"), on_error=self._on_error)

    def _upload_file(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar fichero", "", "CSV o XLSX (*.csv *.xlsx)")
        if not path:
            return
        equipo_id = self._equipo_combo.currentData()
        if not equipo_id:
            self._feedback.show_message("Selecciona un dispositivo destino.", "warning")
            return
        with open(path, "rb") as f:
            file_bytes = f.read()
        import os
        self._feedback.show_message("Validando archivo...", "info")
        self._set_buttons_enabled(False)
        run_in_thread(self, _calcular_diff_file, equipo_id, file_bytes, os.path.basename(path),
                      on_done=lambda r: self._on_diff_ready(r, "file"), on_error=self._on_error)

    def _on_diff_ready(self, result, metodo: str) -> None:
        self._set_buttons_enabled(True)
        programas, diff = result
        if not programas:
            self._feedback.show_message("No se detectaron programas válidos en los datos.", "warning")
            return
        self._programas = programas
        self._diff = diff
        self._equipo_id = self._equipo_combo.currentData()
        self._metodo = metodo
        self._feedback.clear()

        equipo = next((e for e in self._equipos if e["id"] == self._equipo_id), {})
        self._validate_info.setText(
            f"✓ {len(programas)} programas detectados con el formato esperado.\n\n"
            f"Dispositivo: {equipo.get('nombre', '—')}\n"
            f"Departamento: {equipo.get('departamento_nombre', '—')}\n"
            f"Origen: {'texto pegado' if metodo == 'paste' else 'archivo'}\n\n"
            "Sin errores de formato. Continúa para revisar los cambios concretos."
        )
        self._populate_review()
        self._go_step(1)

    def _populate_review(self) -> None:
        diff = self._diff or {}
        rows = []
        for item in diff.get("nuevos", []):
            rows.append({"estado": "Nuevo", "nombre": item.get("nombre", ""),
                         "fabricante": item.get("fabricante", ""), "version_str": str(item.get("version", ""))})
        for item in diff.get("cambios_version", []):
            rows.append({"estado": "Cambio versión", "nombre": item.get("nombre", ""),
                         "fabricante": item.get("fabricante", ""),
                         "version_str": f"{item.get('version_anterior', '')} → {item.get('version_nueva', '')}"})
        for item in diff.get("eliminados", []):
            rows.append({"estado": "Eliminado", "nombre": item.get("nombre", ""),
                         "fabricante": item.get("fabricante", ""), "version_str": ""})
        for item in diff.get("actualizados", []):
            rows.append({"estado": "Sin cambios", "nombre": item.get("nombre", ""),
                         "fabricante": item.get("fabricante", ""), "version_str": str(item.get("version", ""))})
        self._review_table.load_data(rows)
        self._review_table.set_empty_content(title="Sin cambios", message="No hay diferencias respecto a la última importación.", icon="✓")
        n, c, e = len(diff.get("nuevos", [])), len(diff.get("cambios_version", [])), len(diff.get("eliminados", []))
        a = len(diff.get("actualizados", []))
        self._review_summary.setText(
            f"Nuevos: {n}  ·  Cambios de versión: {c}  ·  No presentes: {e}  ·  Sin cambios: {a}"
        )

    def _prepare_apply(self) -> None:
        diff = self._diff or {}
        n, c, e = len(diff.get("nuevos", [])), len(diff.get("cambios_version", [])), len(diff.get("eliminados", []))
        self._apply_summary.setText(
            "Esta importación modificará el inventario:\n\n"
            f"   • {n} programas nuevos\n"
            f"   • {c} versiones actualizadas\n"
            f"   • {e} programas marcados como no presentes\n\n"
            "Los programas no presentes se conservan (soft-delete), no se borran.\n"
            "Pulsa «Aplicar importación» para confirmar."
        )
        self._go_step(3)

    def _confirm_import(self) -> None:
        if not self._diff or not self._equipo_id:
            return
        equipo = next((eq for eq in self._equipos if eq["id"] == self._equipo_id), {})
        dept_id = equipo.get("departamento_id")
        self._apply_btn.setEnabled(False)
        self._cancel_btn.setEnabled(False)
        self._feedback.show_message("Aplicando importación...", "info")
        run_in_thread(self, _aplicar_diff, self._equipo_id, self._programas, self._diff, self._metodo, dept_id,
                      on_done=self._on_import_done, on_error=self._on_import_error)

    def _on_import_done(self, result) -> None:
        importacion_id, exclusivos, pendientes = result
        self._apply_btn.setEnabled(True)
        self._cancel_btn.setEnabled(True)
        self._apply_card.set_title("Importación completada")
        msg = (
            f"✓ Importación registrada (id {importacion_id}).\n\n"
            f"Software exclusivo autorizado automáticamente: {exclusivos}\n"
            f"Reactivaciones pendientes de revisar: {pendientes}"
        )
        self._apply_summary.setText(msg)
        self._feedback.show_message("Importación completada.", "success")
        self.main_window.set_status("Importación completada")
        # Botonera de cierre
        self._apply_btn.setText("Nueva importación")
        self._apply_btn.clicked.disconnect()
        self._apply_btn.clicked.connect(self._reset)
        self._cancel_btn.setText("Ir al inventario")
        self._cancel_btn.clicked.disconnect()
        self._cancel_btn.clicked.connect(lambda: self.main_window.navigate_to("software"))

    def _on_import_error(self, msg: str) -> None:
        self._apply_btn.setEnabled(True)
        self._cancel_btn.setEnabled(True)
        self._feedback.show_message(f"Error importando: {msg}", "error")
        QMessageBox.critical(self, "Error", msg)

    def _on_error(self, msg: str) -> None:
        self._set_buttons_enabled(True)
        self._feedback.show_message(f"Error analizando datos: {msg}", "error")

    def _reset(self) -> None:
        self._programas = None
        self._diff = None
        self._equipo_id = None
        self._metodo = None
        self._paste_area.clear()
        self._feedback.clear()
        # restaurar botonera del paso 4
        self._apply_card.set_title("Resumen de la importación")
        self._apply_btn.setText("Aplicar importación")
        self._apply_btn.setEnabled(True)
        try:
            self._apply_btn.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        self._apply_btn.clicked.connect(self._confirm_import)
        self._cancel_btn.setText("Cancelar")
        self._cancel_btn.setEnabled(True)
        try:
            self._cancel_btn.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        self._cancel_btn.clicked.connect(self._reset)
        self._go_step(0)

    def _set_buttons_enabled(self, enabled: bool) -> None:
        self._analyze_btn.setEnabled(enabled)
        self._file_btn.setEnabled(enabled)
