"""
Inventario de hardware / equipos: salud del inventario por equipo.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QComboBox,
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


HEADERS = ["Equipo", "Departamento", "Usuario", "Última importación", "Software", "Estado"]
KEYS = ["nombre", "departamento_nombre", "notas", "ultima_importacion_str", "total_software_activo", "estado"]


def _estado_label(fecha) -> str:
    if fecha is None or fecha == "":
        return "Nunca importado"
    if isinstance(fecha, datetime):
        fecha = fecha.date()
    if not isinstance(fecha, date):
        try:
            fecha = datetime.fromisoformat(str(fecha)[:19]).date()
        except (ValueError, TypeError):
            return "Nunca importado"
    dias = (date.today() - fecha).days
    if dias < 30:
        return "Al día"
    if dias <= 60:
        return "Atención"
    return "Atrasado"


def _fetch_equipos(dept_id=None):
    from database.connection import get_engine
    from modules.equipos import listar_equipos
    from modules.software import listar_departamentos
    with get_engine().connect() as db:
        depts = listar_departamentos(db)
        rows = listar_equipos(db, departamento_id=dept_id, solo_activos=False)
    result = []
    for r in rows:
        item = dict(r)
        item["activo_str"] = "Activo" if item.get("activo") else "Inactivo"
        item["ultima_importacion_str"] = str(item.get("ultima_importacion") or "—")[:10]
        item["estado"] = _estado_label(item.get("ultima_importacion"))
        item["notas"] = item.get("notas") or "—"
        result.append(item)
    return depts, result


class HardwareInventoryPage(QWidget):
    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__()
        self.main_window = main_window
        self._all_data: list[dict] = []
        self._thread = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        self._import_btn = QPushButton("Importar CSV")
        self._import_btn.clicked.connect(self._import_csv)
        self._export_btn = QPushButton("Exportar Excel")
        self._export_btn.setObjectName("primary")
        self._export_btn.clicked.connect(self._export_excel)
        header = PageHeader("Equipos", "Estado de hardware e importación por dispositivo.")
        header.add_action(self._import_btn)
        header.add_action(self._export_btn)
        layout.addWidget(header)

        self._feedback = FeedbackBar()
        layout.addWidget(self._feedback)

        toolbar = FilterBar()
        self._search = FilterBar.search_box("Buscar equipo, usuario...")
        self._search.textChanged.connect(self._apply_filters)
        toolbar.add_widget(self._search, stretch=1)

        self._dept_combo = QComboBox()
        self._dept_combo.setMinimumWidth(180)
        self._dept_combo.addItem("Todos los departamentos", None)
        self._dept_combo.currentIndexChanged.connect(self._on_dept_changed)
        toolbar.add_widget(self._dept_combo)

        self._activo_combo = QComboBox()
        self._activo_combo.addItems(["Activos e inactivos", "Solo activos", "Solo inactivos"])
        self._activo_combo.currentIndexChanged.connect(self._apply_filters)
        toolbar.add_widget(self._activo_combo)

        self._clear_btn = QPushButton("Limpiar")
        self._clear_btn.setObjectName("subtle")
        self._clear_btn.clicked.connect(self._clear_filters)
        toolbar.add_widget(self._clear_btn)
        layout.addWidget(toolbar)

        body = QHBoxLayout()
        body.setSpacing(12)
        self._table = SortableTable(headers=HEADERS, keys=KEYS, badge_keys=["estado"])
        self._table.set_empty_content(
            title="Sin equipos",
            message="No hay equipos para estos filtros. Importa un CSV de equipos para empezar.",
            icon="🖥",
            action_text="Importar CSV",
            on_action=self._import_csv,
        )
        self._table.selection_changed.connect(self._on_selection)
        body.addWidget(self._table, stretch=1)

        self._detail = DetailPanel()
        self._detail.closed.connect(self._table.clear_selection)
        body.addWidget(self._detail)
        layout.addLayout(body, stretch=1)

        self._status_label = QLabel("")
        self._status_label.setObjectName("labelMuted")
        layout.addWidget(self._status_label)

    def on_activate(self) -> None:
        self._load_data()

    def _load_data(self) -> None:
        self._feedback.show_message("Cargando equipos...", "info")
        dept_id = self._dept_combo.currentData()
        self._thread = run_in_thread(self, _fetch_equipos, dept_id, on_done=self._on_data_loaded, on_error=self._on_error)

    def _on_data_loaded(self, result) -> None:
        depts, data = result
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
        idx = self._activo_combo.currentIndex()
        if idx == 1:
            filtered = [r for r in self._all_data if r.get("activo")]
        elif idx == 2:
            filtered = [r for r in self._all_data if not r.get("activo")]
        else:
            filtered = self._all_data
        self._table.load_data(filtered)
        self._table.filter(self._search.text())
        self._status_label.setText(f"{self._table.row_count()} / {len(self._all_data)} equipos")
        self._detail.clear()

    def _clear_filters(self) -> None:
        self._search.clear()
        self._activo_combo.setCurrentIndex(0)
        self._apply_filters()

    def _on_dept_changed(self) -> None:
        self._load_data()

    def _on_selection(self, row) -> None:
        if not row:
            self._detail.clear()
            return
        from modules.equipos import alertas_equipo
        alerts = alertas_equipo(row)
        badges = [(row.get("activo_str", "Activo"), None), (row.get("estado", ""), None)]
        rows = [
            ("Departamento", row.get("departamento_nombre")),
            ("Usuario", row.get("notas")),
            ("Sistema operativo", row.get("sistema_operativo")),
            ("Procesador", row.get("procesador")),
            ("RAM", row.get("ram")),
            ("Almacenamiento", row.get("almacenamiento")),
            ("Marca / Modelo", row.get("marca_modelo")),
            ("Nº de serie", row.get("num_serie")),
            ("Responsable", row.get("responsable")),
            ("Ubicación", row.get("ubicacion")),
            ("Software instalado", str(row.get("total_software_activo") or 0)),
            ("Última importación", row.get("ultima_importacion_str")),
        ]
        if alerts:
            rows.append(("Alertas", " · ".join(alerts)))
        self._detail.show_details(row.get("nombre", ""), rows, badges=badges)

    def _on_error(self, msg: str) -> None:
        self._feedback.show_message(f"Error cargando equipos: {msg}", "error")

    def _import_csv(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar CSV", "", "CSV (*.csv)")
        if not path:
            return
        self._import_btn.setEnabled(False)
        try:
            from scripts.importar_equipos_csv import import_csv
            result = import_csv(path)
            self._feedback.show_message(f"Importación completada: {result}", "success")
            self.main_window.set_status("Equipos importados")
            self._load_data()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"Error importando:\n{exc}")
        finally:
            self._import_btn.setEnabled(True)

    def _export_excel(self) -> None:
        if not self._all_data:
            self._feedback.show_message("No hay equipos para exportar.", "warning")
            return
        self._export_btn.setEnabled(False)
        try:
            from modules.equipos import exportar_equipos_excel
            data = exportar_equipos_excel(self._all_data, "Equipos Asserta")
            from PySide6.QtWidgets import QFileDialog
            filename, _ = QFileDialog.getSaveFileName(
                self, "Guardar Excel",
                f"Equipos_Asserta_{date.today().isoformat()}.xlsx",
                "Excel (*.xlsx)",
            )
            if filename:
                with open(filename, "wb") as f:
                    f.write(data)
                self._feedback.show_message(f"Excel guardado en {filename}.", "success")
                self.main_window.set_status("Excel exportado")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"No se pudo exportar:\n{exc}")
        finally:
            self._export_btn.setEnabled(True)
