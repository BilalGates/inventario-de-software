"""
Reactivaciones pendientes (todas las áreas): software inactivo que ha vuelto a
detectarse en una importación y requiere decisión (reactivar / ignorar).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QHBoxLayout, QMessageBox, QPushButton, QVBoxLayout, QWidget

from ui.components.confirm_dialog import confirm
from ui.components.sortable_table import SortableTable
from ui.components.ui_kit import FeedbackBar, PageHeader
from ui.components.worker import run_in_thread

if TYPE_CHECKING:
    from ui.main_window import MainWindow


def _fetch_reactivaciones():
    from database.connection import get_engine
    from modules.importacion import listar_reactivaciones_pendientes
    with get_engine().connect() as db:
        rows = listar_reactivaciones_pendientes(db)
    result = []
    for r in rows:
        item = dict(r)
        item["version_referencia"] = str(item.get("version_referencia") or "")
        item["fecha_deteccion"] = str(item.get("fecha_deteccion") or "")
        result.append(item)
    return result


HEADERS = ["Software", "Versión", "Fabricante", "Departamento", "Equipo", "Detectado"]
KEYS = ["software_nombre", "version_referencia", "fabricante", "departamento", "equipo", "fecha_deteccion"]


class ReactivacionesPage(QWidget):
    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__()
        self.main_window = main_window
        self._thread = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        self._refresh_btn = QPushButton("Actualizar")
        self._refresh_btn.clicked.connect(self._load_data)
        header = PageHeader(
            "Reactivaciones pendientes",
            "Software que estaba inactivo y ha vuelto a detectarse. Decide si reactivarlo o ignorarlo.",
        )
        header.add_action(self._refresh_btn)
        layout.addWidget(header)

        self._feedback = FeedbackBar()
        layout.addWidget(self._feedback)

        self._table = SortableTable(headers=HEADERS, keys=KEYS)
        self._table.set_empty_content(
            title="Nada pendiente",
            message="No hay reactivaciones por revisar. Todo el software detectado está al día.",
            icon="✓",
        )
        layout.addWidget(self._table, stretch=1)

        btn_row = QHBoxLayout()
        self._reactivate_btn = QPushButton("Reactivar")
        self._reactivate_btn.setObjectName("primary")
        self._reactivate_btn.clicked.connect(lambda: self._resolve("reactivar"))
        btn_row.addWidget(self._reactivate_btn)
        self._ignore_btn = QPushButton("Ignorar")
        self._ignore_btn.setObjectName("danger")
        self._ignore_btn.clicked.connect(lambda: self._resolve("ignorar"))
        btn_row.addWidget(self._ignore_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def on_activate(self) -> None:
        self._load_data()

    def _load_data(self) -> None:
        self._feedback.show_message("Cargando reactivaciones...", "info")
        self._thread = run_in_thread(self, _fetch_reactivaciones, on_done=self._on_loaded, on_error=self._on_error)

    def _on_loaded(self, rows) -> None:
        self._table.load_data(rows)
        self._feedback.clear()
        self.main_window.set_status(f"{len(rows)} reactivaciones pendientes")

    def _on_error(self, msg: str) -> None:
        self._feedback.show_message(f"Error: {msg}", "error")

    def _resolve(self, accion: str) -> None:
        row = self._table.selected_row()
        if not row:
            self._feedback.show_message("Selecciona una reactivación.", "warning")
            return
        nombre = row.get("software_nombre", "")
        if accion == "ignorar" and not confirm(
            self,
            "Ignorar reactivación",
            f"Se ignorará la reactivación de «{nombre}».",
            details="El software permanecerá inactivo. Podrás volver a verlo si se detecta de nuevo.",
            ok_text="Ignorar",
            danger=True,
        ):
            return
        try:
            from database.connection import get_engine
            from modules.importacion import resolver_reactivacion
            with get_engine().begin() as db:
                resolver_reactivacion(db, row["id"], accion)
            label = "reactivado" if accion == "reactivar" else "ignorado"
            self._feedback.show_message(f"Software {label}.", "success")
            self._load_data()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
