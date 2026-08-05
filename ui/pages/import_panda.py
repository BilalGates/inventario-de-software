from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modules.simple_inventory import current_period
from ui.components.sortable_table import SortableTable
from ui.components.ui_kit import FeedbackBar, FilterBar, PageHeader, SectionCard
from ui.components.worker import run_in_thread
from ui.tokens import SPACING
from utils.panda_parser import PandaParseResult, parse_panda_text

if TYPE_CHECKING:
    from ui.main_window import MainWindow


PREVIEW_HEADERS = ["Linea", "Programa", "Editor", "Fecha", "Tamano", "Version"]
PREVIEW_KEYS = ["row_number", "nombre", "fabricante", "fecha_str", "tamano", "version"]
ERROR_HEADERS = ["Linea", "Mensaje", "Texto"]
ERROR_KEYS = ["line_number", "message", "raw"]

VALIDATE_LABEL = "Validar"
CREATE_LABEL = "Crear importacion"


class ImportErrorsDialog(QDialog):
    """Ventana emergente con los errores de formato del pegado."""

    def __init__(self, parent: QWidget, errors: list[dict]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Errores de formato")
        self.setModal(True)
        self.resize(720, 380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"])
        layout.setSpacing(SPACING["md"])

        plural = "es" if len(errors) != 1 else ""
        layout.addWidget(QLabel(f"Se {'han' if len(errors) != 1 else 'ha'} detectado {len(errors)} error{plural}. Corrige el pegado y vuelve a validar."))

        table = SortableTable(headers=ERROR_HEADERS, keys=ERROR_KEYS)
        table.load_data(errors)
        layout.addWidget(table, stretch=1)

        footer = QHBoxLayout()
        footer.addStretch()
        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)
        layout.addLayout(footer)


def _format_rows(rows: list[dict]) -> list[dict]:
    formatted = []
    for row in rows:
        item = dict(row)
        fecha = item.get("fecha_instalacion")
        item["fecha_str"] = fecha.isoformat() if fecha else ""
        item["fabricante"] = item.get("fabricante") or ""
        item["tamano"] = item.get("tamano") or ""
        item["version"] = item.get("version") or ""
        formatted.append(item)
    return formatted


def _format_errors(result: PandaParseResult) -> list[dict]:
    return [{"line_number": e.line_number or "", "message": e.message, "raw": e.raw} for e in result.errors]


def _fetch_source_data(departamento_id: int | None):
    from database.connection import get_engine
    from modules.equipos import listar_equipos
    from modules.software import listar_departamentos

    with get_engine().connect() as db:
        depts = listar_departamentos(db)
        selected = departamento_id or (depts[0]["id"] if depts else None)
        equipos = listar_equipos(db, departamento_id=selected, solo_activos=True) if selected else []
    return depts, selected, equipos


def _save_import(equipo_id: int, periodo: str, rows: list[dict], raw_text: str) -> int:
    from modules.simple_inventory import confirm_software_import

    return confirm_software_import(equipo_id, periodo, rows, raw_text)


class ImportPandaPage(QWidget):
    import_saved = Signal(int)

    def __init__(self, main_window: "MainWindow", embedded: bool = False) -> None:
        super().__init__()
        self.main_window = main_window
        self._embedded = embedded
        self._thread = None
        self._parse_result: PandaParseResult | None = None
        self._department_id: int | None = None
        self._pending_department_id: int | None = None
        self._pending_equipo_id: int | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        margin = 0 if self._embedded else 24
        layout.setContentsMargins(margin, 20 if not self._embedded else 0, margin, margin)
        layout.setSpacing(12)

        if not self._embedded:
            layout.addWidget(PageHeader("Importar software", "Carga mensual de software por equipo desde Panda."))
        self._feedback = FeedbackBar()
        layout.addWidget(self._feedback)

        self._period_edit = FilterBar.search_box("YYYY-MM")
        self._period_edit.setText(current_period())
        self._period_edit.setMaximumWidth(120)
        if not self._embedded:
            toolbar = FilterBar()
            toolbar.add_widget(QLabel("Periodo"))
            toolbar.add_widget(self._period_edit)
            toolbar.add_stretch()
            layout.addWidget(toolbar)

        # ── Columna izquierda: pegado + equipo destino ─────────────────
        paste_card = SectionCard("Pegado desde Panda")

        equipo_row = QHBoxLayout()
        equipo_row.setSpacing(SPACING["sm"])
        equipo_row.addWidget(QLabel("Equipo"))
        self._equipo_combo = QComboBox()
        self._equipo_combo.setMinimumWidth(220)
        self._equipo_combo.currentIndexChanged.connect(self._update_confirm_state)
        equipo_row.addWidget(self._equipo_combo, stretch=1)
        paste_card.add_layout(equipo_row)

        self._paste_area = QTextEdit()
        self._paste_area.setPlaceholderText(
            "Pega el listado de Panda. Sirve tabulado o vertical: nombre, editor, fecha, tamano, version."
        )
        self._paste_area.setMinimumHeight(120)
        self._paste_area.textChanged.connect(self._invalidate)
        paste_card.add_widget(self._paste_area, stretch=1)

        # ── Columna derecha: programas detectados + accion ─────────────
        preview_card = SectionCard("Programas detectados")
        self._preview_table = SortableTable(headers=PREVIEW_HEADERS, keys=PREVIEW_KEYS)
        self._preview_table.set_empty_content(
            title="Sin previsualizacion",
            message="Pulsa Validar para ver los programas detectados.",
            icon="",
        )
        preview_card.add_widget(self._preview_table, stretch=1)

        # Un solo boton que cambia de rol: Validar -> Crear importacion.
        action_row = QHBoxLayout()
        action_row.addStretch()
        self._action_btn = QPushButton(VALIDATE_LABEL)
        self._action_btn.setObjectName("primary")
        self._action_btn.clicked.connect(self._on_action)
        action_row.addWidget(self._action_btn)
        preview_card.add_layout(action_row)

        columns = QSplitter(Qt.Orientation.Horizontal)
        columns.setChildrenCollapsible(False)
        columns.setHandleWidth(SPACING["sm"])
        columns.addWidget(paste_card)
        columns.addWidget(preview_card)
        columns.setStretchFactor(0, 1)
        columns.setStretchFactor(1, 1)
        layout.addWidget(columns, stretch=1)

        self._update_confirm_state()

    def on_activate(self) -> None:
        self._load_source_data()

    def set_period(self, periodo: str) -> None:
        if self._period_edit.text() != periodo:
            self._period_edit.setText(periodo)

    def apply_navigation(self, payload: dict) -> None:
        if payload.get("periodo"):
            self.set_period(str(payload["periodo"]))
        self._pending_department_id = payload.get("departamento_id")
        self._pending_equipo_id = payload.get("equipo_id")
        self._load_source_data()

    def _periodo(self) -> str:
        from modules.simple_inventory import validate_periodo

        return validate_periodo(self._period_edit.text())

    def _load_source_data(self) -> None:
        # El departamento viene del contexto de navegacion (tarjeta seleccionada),
        # no de un selector propio.
        departamento_id = self._pending_department_id or self._department_id
        self._thread = run_in_thread(
            self,
            _fetch_source_data,
            departamento_id,
            on_done=self._on_source_loaded,
            on_error=self._on_error,
        )

    def _on_source_loaded(self, result) -> None:
        depts, selected, equipos = result
        self._department_id = selected

        current = self._pending_equipo_id or self._equipo_combo.currentData()
        self._equipo_combo.blockSignals(True)
        self._equipo_combo.clear()
        for equipo in equipos:
            self._equipo_combo.addItem(equipo["nombre"], equipo["id"])
        for i in range(self._equipo_combo.count()):
            if self._equipo_combo.itemData(i) == current:
                self._equipo_combo.setCurrentIndex(i)
                break
        self._equipo_combo.blockSignals(False)
        self._pending_department_id = None
        self._pending_equipo_id = None
        self._update_confirm_state()

    def _invalidate(self) -> None:
        """Cualquier edicion del pegado devuelve el boton al estado Validar."""
        self._parse_result = None
        self._preview_table.load_data([])
        self._update_confirm_state()

    def _on_action(self) -> None:
        if self._parse_result is not None and self._parse_result.ok:
            self._confirm()
        else:
            self._validate()

    def _validate(self) -> None:
        result = parse_panda_text(self._paste_area.toPlainText())
        self._parse_result = result
        self._preview_table.load_data(_format_rows(result.rows))
        if result.errors:
            # Los errores se muestran en ventana emergente, no ocupan sitio en la pagina.
            self._feedback.show_message(f"{len(result.errors)} errores. Revisa el pegado.", "error")
            self._update_confirm_state()
            ImportErrorsDialog(self, _format_errors(result)).exec()
            return
        origen = "vertical" if result.mode == "vertical" else "tabulado"
        self._feedback.show_message(f"{len(result.rows)} programas detectados en formato {origen}.", "success")
        self._update_confirm_state()

    def _update_confirm_state(self) -> None:
        result = self._parse_result
        validated = bool(result and result.ok)
        self._action_btn.setText(CREATE_LABEL if validated else VALIDATE_LABEL)
        if validated:
            self._action_btn.setEnabled(bool(self._equipo_combo.currentData()))
        else:
            self._action_btn.setEnabled(bool(self._paste_area.toPlainText().strip()))

    def _confirm(self) -> None:
        result = self._parse_result
        equipo_id = self._equipo_combo.currentData()
        if not result or not result.ok or not equipo_id:
            self._feedback.show_message("Valida el pegado y selecciona un equipo.", "warning")
            return
        try:
            periodo = self._periodo()
        except ValueError as exc:
            self._feedback.show_message(str(exc), "warning")
            return
        self._action_btn.setEnabled(False)
        self._feedback.show_message("Guardando importacion...", "info")
        self._thread = run_in_thread(
            self,
            _save_import,
            int(equipo_id),
            periodo,
            result.rows,
            self._paste_area.toPlainText(),
            on_done=self._on_saved,
            on_error=self._on_error,
        )

    def _on_saved(self, importacion_id: int) -> None:
        self._feedback.show_message(f"Importacion guardada (id {importacion_id}).", "success")
        self.main_window.set_status("Software importado")
        self._parse_result = None
        # Vaciar el pegado deja la columna lista para el siguiente equipo.
        self._paste_area.blockSignals(True)
        self._paste_area.clear()
        self._paste_area.blockSignals(False)
        self._preview_table.load_data([])
        self._update_confirm_state()
        self.import_saved.emit(importacion_id)

    def _on_error(self, msg: str) -> None:
        self._update_confirm_state()
        QMessageBox.critical(self, "Error", msg)
        self._feedback.show_message(f"Error: {msg}", "error")
