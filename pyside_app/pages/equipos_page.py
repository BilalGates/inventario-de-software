from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
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
    QVBoxLayout,
    QWidget,
)

from database.connection import get_engine
from modules.equipos import (
    crear_equipo,
    dar_baja_equipo,
    existe_equipo,
    exportar_equipos_excel,
    listar_equipos,
    obtener_equipo,
)
from modules.importacion import ultima_importacion_por_equipo, ultimas_importaciones_por_equipo
from modules.software import listar_departamentos

from pyside_app.widgets.data_table import DataTable

if TYPE_CHECKING:
    from pyside_app.main_window import MainWindow


class EquiposPage(QWidget):
    def __init__(self, main_window: MainWindow) -> None:
        super().__init__()
        self.main_window = main_window
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("Equipos")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Departamento:"))
        self.dept_combo = QComboBox()
        self.dept_combo.addItem("Todos", None)
        filter_layout.addWidget(self.dept_combo)
        self.filter_btn = QPushButton("Filtrar")
        self.filter_btn.clicked.connect(self._load_data)
        filter_layout.addWidget(self.filter_btn)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        btn_layout = QHBoxLayout()
        self.add_equipo_btn = QPushButton("+ Anadir equipo")
        self.add_equipo_btn.setStyleSheet("""
            QPushButton { background: #27ae60; color: white; padding: 8px 16px;
                          border: none; border-radius: 4px; font-weight: bold; }
        """)
        self.add_equipo_btn.clicked.connect(self._add_equipo)
        btn_layout.addWidget(self.add_equipo_btn)

        self.baja_btn = QPushButton("Dar de baja equipo seleccionado")
        self.baja_btn.setStyleSheet("""
            QPushButton { background: #e74c3c; color: white; padding: 8px 16px;
                          border: none; border-radius: 4px; font-weight: bold; }
        """)
        self.baja_btn.clicked.connect(self._baja_equipo)
        btn_layout.addWidget(self.baja_btn)

        self.export_btn = QPushButton("Exportar a Excel")
        self.export_btn.clicked.connect(self._export)
        btn_layout.addWidget(self.export_btn)

        layout.addLayout(btn_layout)

        self.table = DataTable()
        layout.addWidget(self.table, stretch=1)

        self.detail_label = QLabel()
        self.detail_label.setWordWrap(True)
        self.detail_label.setStyleSheet("background: #f0f0f0; padding: 12px; border-radius: 4px;")
        layout.addWidget(self.detail_label)

        self.import_table = DataTable()
        layout.addWidget(self.import_table)

    def on_activate(self) -> None:
        try:
            with get_engine().connect() as db:
                depts = listar_departamentos(db)
            self.dept_combo.clear()
            self.dept_combo.addItem("Todos", None)
            for dept in depts:
                self.dept_combo.addItem(dept["nombre"], dept["id"])
        except Exception:
            pass
        self._load_data()

    def _load_data(self) -> None:
        try:
            with get_engine().connect() as db:
                departamento_id = self.dept_combo.currentData()
                equipos = listar_equipos(db, departamento_id=departamento_id, solo_activos=False)
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        data = []
        for eq in equipos:
            data.append({
                "id": eq["id"],
                "Equipo": eq["nombre"],
                "Departamento": eq["departamento_nombre"],
                "Usuario": eq.get("notas") or "",
                "Activo": "Si" if eq["activo"] else "No",
                "Ultima importacion": str(eq.get("ultima_importacion") or ""),
                "Software activo": str(eq.get("total_software_activo") or 0),
            })
        self.table.load_data(data, ["Equipo", "Departamento", "Usuario", "Activo", "Ultima importacion", "Software activo"])
        self._equipos_loaded = equipos
        self.table.itemSelectionChanged.connect(self._on_equipo_selected)

    def _on_equipo_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0 or not hasattr(self, "_equipos_loaded") or row >= len(self._equipos_loaded):
            return
        equipo = self._equipos_loaded[row]

        detail = (
            f"<b>{equipo['nombre']}</b><br><br>"
            f"Dept: {equipo['departamento_nombre']}<br>"
            f"Activo: {'Si' if equipo['activo'] else 'No'}<br>"
            f"Tipo: {equipo.get('tipo_dispositivo') or '-'}<br>"
            f"Marca: {equipo.get('marca_modelo') or '-'}<br>"
            f"N Serie: {equipo.get('num_serie') or '-'}<br>"
            f"MAC: {equipo.get('mac_address') or '-'}<br>"
            f"SO: {equipo.get('sistema_operativo') or '-'}<br>"
            f"Procesador: {equipo.get('procesador') or '-'}<br>"
            f"RAM: {equipo.get('ram') or '-'}<br>"
            f"Almacenamiento: {equipo.get('almacenamiento') or '-'}<br>"
            f"Responsable: {equipo.get('responsable') or '-'}<br>"
            f"Ubicacion: {equipo.get('ubicacion') or '-'}<br>"
            f"Coste: {equipo.get('coste') or '-'}<br>"
            f"Fecha adquisicion: {equipo.get('fecha_adquisicion') or '-'}<br>"
        )
        self.detail_label.setText(detail)

        try:
            with get_engine().connect() as db:
                recent = ultimas_importaciones_por_equipo(db, equipo["id"], limit=5)
            imp_data = []
            for imp in recent:
                imp_data.append({
                    "Fecha": str(imp["fecha_importacion"]),
                    "Metodo": imp["metodo"],
                    "Total": str(imp.get("n_total") or 0),
                    "Nuevos": str(imp.get("n_nuevos") or 0),
                    "Actualizados": str(imp.get("n_actualizados") or 0),
                    "Eliminados": str(imp.get("n_eliminados") or 0),
                    "Cambios version": str(imp.get("n_cambios_version") or 0),
                })
            self.import_table.load_data(
                imp_data,
                ["Fecha", "Metodo", "Total", "Nuevos", "Actualizados", "Eliminados", "Cambios version"],
            )
        except Exception:
            pass

    def _add_equipo(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Nuevo equipo")
        layout = QFormLayout(dialog)
        name_input = QLineEdit()
        notes_input = QLineEdit()
        layout.addRow("Nombre:", name_input)
        layout.addRow("Notas:", notes_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec() == QDialog.Accepted:
            name = name_input.text().strip()
            if not name:
                QMessageBox.warning(self, "Error", "El nombre es obligatorio")
                return
            dept_id = self.dept_combo.currentData()
            if dept_id is None:
                QMessageBox.warning(self, "Error", "Selecciona un departamento")
                return
            with get_engine().begin() as db:
                if existe_equipo(db, dept_id, name):
                    QMessageBox.warning(self, "Error", "Ya existe un equipo con ese nombre en el departamento")
                    return
                crear_equipo(db, dept_id, name, notes_input.text().strip() or None)
            QMessageBox.information(self, "Creado", f"Equipo {name} creado")
            self._load_data()

    def _baja_equipo(self) -> None:
        row = self.table.currentRow()
        if row < 0 or not hasattr(self, "_equipos_loaded"):
            QMessageBox.warning(self, "Error", "Selecciona un equipo de la tabla")
            return
        equipo = self._equipos_loaded[row]
        reply = QMessageBox.question(
            self,
            "Confirmar baja",
            f"Dar de baja el equipo {equipo['nombre']}?\nEsta accion no se puede deshacer.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        with get_engine().begin() as db:
            dar_baja_equipo(db, equipo["id"])
        QMessageBox.information(self, "Baja", f"Equipo {equipo['nombre']} dado de baja")
        self._load_data()

    def _export(self) -> None:
        if not hasattr(self, "_equipos_loaded") or not self._equipos_loaded:
            QMessageBox.warning(self, "Error", "No hay datos para exportar")
            return
        try:
            data = exportar_equipos_excel(self._equipos_loaded, "Equipos")
            from PySide6.QtWidgets import QFileDialog
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Guardar Excel",
                f"Inventario_Equipos_{date.today().isoformat()}.xlsx",
                "Excel (*.xlsx)",
            )
            if filename:
                with open(filename, "wb") as f:
                    f.write(data)
                QMessageBox.information(self, "Exportado", f"Excel guardado en:\n{filename}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
