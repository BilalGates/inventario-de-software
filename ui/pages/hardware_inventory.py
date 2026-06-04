"""
Inventario de hardware / equipos.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.components.sortable_table import SortableTable
from ui.components.worker import run_in_thread

if TYPE_CHECKING:
    from ui.main_window import MainWindow


HEADERS = ["ID", "Nombre", "Departamento", "Usuario", "SO", "Marca/Modelo", "N/S", "RAM", "Almacenamiento", "Activo", "Ú. Importación", "Software"]
KEYS    = ["id", "nombre", "departamento_nombre", "notas", "sistema_operativo", "marca_modelo", "num_serie", "ram", "almacenamiento", "activo_str", "ultima_importacion_str", "total_software_activo"]


def _fetch_equipos(dept_id=None):
    from database.connection import get_engine
    from modules.equipos import listar_equipos
    from modules.equipos import estado_importacion
    with get_engine().connect() as db:
        rows = listar_equipos(db, departamento_id=dept_id, solo_activos=False)
    result = []
    for r in rows:
        item = dict(r)
        item["activo_str"] = "Sí" if item.get("activo") else "No"
        item["ultima_importacion_str"] = str(item.get("ultima_importacion") or "")
        result.append(item)
    return result


def _fetch_departamentos():
    from database.connection import get_engine
    from modules.software import listar_departamentos
    with get_engine().connect() as db:
        return listar_departamentos(db)


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

        title = QLabel("Inventario de Hardware / Equipos")
        title.setObjectName("labelTitle")
        layout.addWidget(title)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Buscar equipo...")
        self._search.setMinimumWidth(240)
        self._search.textChanged.connect(self._apply_filters)
        toolbar.addWidget(self._search)

        self._dept_combo = QComboBox()
        self._dept_combo.setMinimumWidth(180)
        self._dept_combo.addItem("Todos los departamentos", None)
        self._dept_combo.currentIndexChanged.connect(self._on_dept_changed)
        toolbar.addWidget(self._dept_combo)

        self._activo_combo = QComboBox()
        self._activo_combo.addItems(["Activos e inactivos", "Solo activos", "Solo inactivos"])
        self._activo_combo.currentIndexChanged.connect(self._apply_filters)
        toolbar.addWidget(self._activo_combo)

        toolbar.addStretch()

        self._import_btn = QPushButton("Importar desde CSV")
        self._import_btn.clicked.connect(self._import_csv)
        toolbar.addWidget(self._import_btn)

        self._export_btn = QPushButton("Exportar a Excel")
        self._export_btn.setObjectName("primary")
        self._export_btn.clicked.connect(self._export_excel)
        toolbar.addWidget(self._export_btn)

        layout.addLayout(toolbar)

        # Tabla
        self._table = SortableTable(headers=HEADERS, keys=KEYS)
        layout.addWidget(self._table, stretch=1)

        self._status_label = QLabel("")
        self._status_label.setObjectName("labelMuted")
        layout.addWidget(self._status_label)

    def on_activate(self) -> None:
        run_in_thread(self, _fetch_departamentos, on_done=self._on_depts_loaded)
        self._load_data()

    def _on_depts_loaded(self, depts: list[dict]) -> None:
        self._dept_combo.blockSignals(True)
        self._dept_combo.clear()
        self._dept_combo.addItem("Todos los departamentos", None)
        for d in depts:
            self._dept_combo.addItem(d["nombre"], d["id"])
        self._dept_combo.blockSignals(False)

    def _load_data(self) -> None:
        dept_id = self._dept_combo.currentData()
        self._thread = run_in_thread(self, _fetch_equipos, dept_id,
                                     on_done=self._on_data_loaded, on_error=self._on_error)

    def _on_data_loaded(self, data: list[dict]) -> None:
        self._all_data = data
        self._apply_filters()

    def _apply_filters(self) -> None:
        activo_filter = self._activo_combo.currentIndex()
        if activo_filter == 1:
            filtered = [r for r in self._all_data if r.get("activo")]
        elif activo_filter == 2:
            filtered = [r for r in self._all_data if not r.get("activo")]
        else:
            filtered = self._all_data

        self._table.load_data(filtered)
        self._table.filter(self._search.text())
        self._status_label.setText(f"{self._table.row_count()} / {len(self._all_data)} equipos")

    def _on_dept_changed(self) -> None:
        self._load_data()

    def _on_error(self, msg: str) -> None:
        QMessageBox.critical(self, "Error", f"Error cargando equipos:\n{msg}")

    def _import_csv(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar CSV", "", "CSV (*.csv)")
        if not path:
            return
        try:
            from scripts.importar_equipos_csv import import_csv
            result = import_csv(path)
            QMessageBox.information(self, "Importado", f"Resultado: {result}")
            self._load_data()
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Error importando:\n{exc}")

    def _export_excel(self) -> None:
        if not self._all_data:
            return
        try:
            from modules.equipos import exportar_equipos_excel
            data = exportar_equipos_excel(self._all_data, "Equipos Asserta")
            from PySide6.QtWidgets import QFileDialog
            from datetime import date
            filename, _ = QFileDialog.getSaveFileName(
                self, "Guardar Excel",
                f"Equipos_Asserta_{date.today().isoformat()}.xlsx",
                "Excel (*.xlsx)",
            )
            if filename:
                with open(filename, "wb") as f:
                    f.write(data)
                QMessageBox.information(self, "Exportado", f"Excel guardado en:\n{filename}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"No se pudo exportar:\n{exc}")
