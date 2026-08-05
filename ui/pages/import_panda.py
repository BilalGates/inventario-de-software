from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
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
    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__()
        self.main_window = main_window
        self._thread = None
        self._parse_result: PandaParseResult | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        layout.addWidget(PageHeader("Importar software", "Carga mensual de software por equipo desde Panda."))
        self._feedback = FeedbackBar()
        layout.addWidget(self._feedback)

        toolbar = FilterBar()
        toolbar.add_widget(QLabel("Periodo"))
        self._period_edit = FilterBar.search_box("YYYY-MM")
        self._period_edit.setText(current_period())
        self._period_edit.setMaximumWidth(120)
        toolbar.add_widget(self._period_edit)
        toolbar.add_widget(QLabel("Departamento"))
        self._dept_combo = QComboBox()
        self._dept_combo.setMinimumWidth(220)
        self._dept_combo.currentIndexChanged.connect(self._load_source_data)
        toolbar.add_widget(self._dept_combo)
        toolbar.add_widget(QLabel("Equipo"))
        self._equipo_combo = QComboBox()
        self._equipo_combo.setMinimumWidth(220)
        self._equipo_combo.currentIndexChanged.connect(self._update_confirm_state)
        toolbar.add_widget(self._equipo_combo)
        toolbar.add_stretch()
        layout.addWidget(toolbar)

        card = SectionCard("Pegado desde Panda")
        buttons = QHBoxLayout()
        self._validate_btn = QPushButton("Validar")
        self._validate_btn.setObjectName("primary")
        self._validate_btn.clicked.connect(self._validate)
        buttons.addWidget(self._validate_btn)
        self._confirm_btn = QPushButton("Guardar importacion")
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.clicked.connect(self._confirm)
        buttons.addWidget(self._confirm_btn)
        buttons.addStretch()
        card.add_layout(buttons)
        self._paste_area = QTextEdit()
        self._paste_area.setPlaceholderText(
            "Pega el listado de Panda. Sirve tabulado o vertical: nombre, editor, fecha, tamano, version."
        )
        self._paste_area.setMinimumHeight(180)
        self._paste_area.textChanged.connect(self._invalidate)
        card.add_widget(self._paste_area)
        layout.addWidget(card)

        body = QHBoxLayout()
        body.setSpacing(SPACING["md"])
        self._preview_table = SortableTable(headers=PREVIEW_HEADERS, keys=PREVIEW_KEYS)
        self._preview_table.set_empty_content(
            title="Sin previsualizacion",
            message="Pulsa Validar para ver los programas detectados.",
            icon="",
        )
        body.addWidget(self._preview_table, stretch=2)
        self._error_table = SortableTable(headers=ERROR_HEADERS, keys=ERROR_KEYS)
        self._error_table.set_empty_content(
            title="Sin errores",
            message="Los errores de formato apareceran aqui.",
            icon="",
        )
        body.addWidget(self._error_table, stretch=1)
        layout.addLayout(body, stretch=1)

    def on_activate(self) -> None:
        self._load_source_data()

    def _periodo(self) -> str:
        from modules.simple_inventory import validate_periodo

        return validate_periodo(self._period_edit.text())

    def _load_source_data(self) -> None:
        self._thread = run_in_thread(
            self,
            _fetch_source_data,
            self._dept_combo.currentData(),
            on_done=self._on_source_loaded,
            on_error=self._on_error,
        )

    def _on_source_loaded(self, result) -> None:
        depts, selected, equipos = result
        self._dept_combo.blockSignals(True)
        self._dept_combo.clear()
        for dept in depts:
            self._dept_combo.addItem(dept["nombre"], dept["id"])
        for i in range(self._dept_combo.count()):
            if self._dept_combo.itemData(i) == selected:
                self._dept_combo.setCurrentIndex(i)
                break
        self._dept_combo.blockSignals(False)

        current = self._equipo_combo.currentData()
        self._equipo_combo.blockSignals(True)
        self._equipo_combo.clear()
        for equipo in equipos:
            self._equipo_combo.addItem(equipo["nombre"], equipo["id"])
        for i in range(self._equipo_combo.count()):
            if self._equipo_combo.itemData(i) == current:
                self._equipo_combo.setCurrentIndex(i)
                break
        self._equipo_combo.blockSignals(False)
        self._update_confirm_state()

    def _invalidate(self) -> None:
        self._parse_result = None
        self._confirm_btn.setEnabled(False)

    def _validate(self) -> None:
        result = parse_panda_text(self._paste_area.toPlainText())
        self._parse_result = result
        self._preview_table.load_data(_format_rows(result.rows))
        self._error_table.load_data(_format_errors(result))
        if result.errors:
            self._feedback.show_message(f"{len(result.errors)} errores. Revisa el pegado.", "error")
        else:
            origen = "vertical" if result.mode == "vertical" else "tabulado"
            self._feedback.show_message(f"{len(result.rows)} programas detectados en formato {origen}.", "success")
        self._update_confirm_state()

    def _update_confirm_state(self) -> None:
        result = self._parse_result
        self._confirm_btn.setEnabled(bool(result and result.ok and self._equipo_combo.currentData()))

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
        self._confirm_btn.setEnabled(False)
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
        self._confirm_btn.setEnabled(False)
        self._parse_result = None

    def _on_error(self, msg: str) -> None:
        self._confirm_btn.setEnabled(False)
        QMessageBox.critical(self, "Error", msg)
        self._feedback.show_message(f"Error: {msg}", "error")
