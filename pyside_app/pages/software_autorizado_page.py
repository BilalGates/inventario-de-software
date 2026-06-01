from __future__ import annotations

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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from database.connection import get_engine
from modules.autorizado import (
    actualizar_autorizado,
    crear_autorizado,
    eliminar_autorizado,
    eliminar_autorizado_grupo,
    listar_autorizado,
    listar_autorizado_agrupado,
    listar_autorizado_detalle_grupo,
)
from modules.software import listar_departamentos

from pyside_app.widgets.data_table import DataTable

if TYPE_CHECKING:
    from pyside_app.main_window import MainWindow


class SoftwareAutorizadoPage(QWidget):
    def __init__(self, main_window: MainWindow) -> None:
        super().__init__()
        self.main_window = main_window
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("Software Autorizado")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.agrupado_tab = QWidget()
        self.detalle_tab = QWidget()
        self.tabs.addTab(self.agrupado_tab, "Agrupado")
        self.tabs.addTab(self.detalle_tab, "Detalle")

        self._setup_agrupado_tab()
        self._setup_detalle_tab()

    def _setup_agrupado_tab(self) -> None:
        layout = QVBoxLayout(self.agrupado_tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.agrupado_table = DataTable()
        layout.addWidget(self.agrupado_table, stretch=1)

        btn_layout = QHBoxLayout()
        self.show_detail_btn = QPushButton("Ver detalle del grupo")
        self.show_detail_btn.clicked.connect(self._show_grupo_detail)
        btn_layout.addWidget(self.show_detail_btn)

        self.delete_group_btn = QPushButton("Archivar grupo")
        self.delete_group_btn.setStyleSheet("""
            QPushButton { background: #e74c3c; color: white; padding: 8px 16px;
                          border: none; border-radius: 4px; }
        """)
        self.delete_group_btn.clicked.connect(self._delete_grupo)
        btn_layout.addWidget(self.delete_group_btn)

        self.refresh_agrupado_btn = QPushButton("Actualizar")
        self.refresh_agrupado_btn.clicked.connect(self._load_agrupado)
        btn_layout.addWidget(self.refresh_agrupado_btn)
        layout.addLayout(btn_layout)

    def _setup_detalle_tab(self) -> None:
        layout = QVBoxLayout(self.detalle_tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.detalle_table = DataTable()
        layout.addWidget(self.detalle_table, stretch=1)

        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("+ Anadir")
        self.add_btn.setStyleSheet("""
            QPushButton { background: #27ae60; color: white; padding: 8px 16px;
                          border: none; border-radius: 4px; font-weight: bold; }
        """)
        self.add_btn.clicked.connect(self._show_add_dialog)
        btn_layout.addWidget(self.add_btn)

        self.edit_btn = QPushButton("Editar seleccionado")
        self.edit_btn.clicked.connect(self._show_edit_dialog)
        btn_layout.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("Archivar seleccionado")
        self.delete_btn.setStyleSheet("""
            QPushButton { background: #e74c3c; color: white; padding: 8px 16px;
                          border: none; border-radius: 4px; }
        """)
        self.delete_btn.clicked.connect(self._delete_autorizado)
        btn_layout.addWidget(self.delete_btn)

        self.refresh_detalle_btn = QPushButton("Actualizar")
        self.refresh_detalle_btn.clicked.connect(self._load_detalle)
        btn_layout.addWidget(self.refresh_detalle_btn)

        layout.addLayout(btn_layout)

    def on_activate(self) -> None:
        self._load_agrupado()
        self._load_detalle()

    def _load_agrupado(self) -> None:
        try:
            with get_engine().connect() as db:
                rows = listar_autorizado_agrupado(db)
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return
        data = []
        for row in rows:
            data.append({
                "grupo": row["grupo"],
                "Nombre": row["nombre"],
                "Fabricantes": row.get("fabricantes") or "",
                "Versiones": row.get("versiones") or "",
                "Departamentos": row.get("departamentos") or "",
                "Equipos/Usuarios": row.get("equipos_usuarios") or "",
                "Registros": str(row.get("registros") or 0),
            })
        self.agrupado_table._data = rows
        self.agrupado_table.load_data(
            data,
            ["Nombre", "Fabricantes", "Versiones", "Departamentos", "Equipos/Usuarios", "Registros"],
        )

    def _load_detalle(self) -> None:
        try:
            with get_engine().connect() as db:
                rows = listar_autorizado(db)
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return
        data = []
        for row in rows:
            data.append({
                "id": row["id"],
                "Nombre": row.get("software_nombre") or row.get("nombre", ""),
                "Fabricante": row.get("fabricante") or "",
                "Tipo": row.get("tipo") or "",
                "Version": row.get("version") or "",
                "Equipo/Usuario": row.get("equipo_nombre") or row.get("usuario_texto") or "",
                "Departamento": row.get("departamento_nombre") or "",
                "Motivo": row.get("motivo") or "",
                "Fecha autorizacion": str(row.get("fecha_autorizacion") or ""),
            })
        self.detalle_table.load_data(
            data,
            ["Nombre", "Fabricante", "Tipo", "Version", "Equipo/Usuario", "Departamento", "Motivo", "Fecha autorizacion"],
        )
        self._detalle_data = rows

    def _show_grupo_detail(self) -> None:
        row = self.agrupado_table.currentRow()
        if row < 0 or not hasattr(self.agrupado_table, "_data"):
            QMessageBox.warning(self, "Error", "Selecciona un grupo")
            return
        grupo_data = self.agrupado_table._data[row]
        grupo = grupo_data["grupo"]
        try:
            with get_engine().connect() as db:
                detail = listar_autorizado_detalle_grupo(db, grupo)
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return
        data = []
        for item in detail:
            data.append({
                "Nombre": item.get("nombre_visible", ""),
                "Fabricante": item.get("fabricante_visible") or "",
                "Tipo": item.get("tipo") or "",
                "Version": item.get("version_visible") or "",
                "Equipo": item.get("equipo_nombre") or "",
                "Departamento": item.get("departamento_nombre") or "",
                "Observaciones": item.get("observaciones") or "",
            })
        detail_dialog = QDialog(self)
        detail_dialog.setWindowTitle(f"Detalle: {grupo_data['nombre']}")
        detail_dialog.resize(700, 400)
        detail_layout = QVBoxLayout(detail_dialog)
        detail_table = DataTable()
        detail_table.load_data(
            data,
            ["Nombre", "Fabricante", "Tipo", "Version", "Equipo", "Departamento", "Observaciones"],
        )
        detail_layout.addWidget(detail_table)
        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(detail_dialog.accept)
        detail_layout.addWidget(close_btn)
        detail_dialog.exec()

    def _show_add_dialog(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Nuevo software autorizado")
        dialog.resize(450, 400)
        layout = QFormLayout(dialog)

        nombre_input = QLineEdit()
        fabricante_input = QLineEdit()
        tipo_input = QLineEdit()
        version_input = QLineEdit()
        equipo_input = QLineEdit()
        usuario_input = QLineEdit()
        motivo_input = QLineEdit()
        dept_combo = QComboBox()

        try:
            with get_engine().connect() as db:
                depts = listar_departamentos(db)
            dept_combo.addItem("-- Ninguno --", None)
            for d in depts:
                dept_combo.addItem(d["nombre"], d["id"])
        except Exception:
            pass

        layout.addRow("Nombre:", nombre_input)
        layout.addRow("Fabricante:", fabricante_input)
        layout.addRow("Tipo:", tipo_input)
        layout.addRow("Version:", version_input)
        layout.addRow("Equipo (nombre):", equipo_input)
        layout.addRow("Usuario (texto):", usuario_input)
        layout.addRow("Departamento:", dept_combo)
        layout.addRow("Motivo:", motivo_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec() == QDialog.Accepted:
            name = nombre_input.text().strip()
            if not name:
                QMessageBox.warning(self, "Error", "El nombre es obligatorio")
                return
            values = {
                "nombre": name,
                "fabricante": fabricante_input.text().strip() or None,
                "tipo": tipo_input.text().strip() or None,
                "version": version_input.text().strip() or None,
                "equipo_id": None,
                "usuario_texto": usuario_input.text().strip() or None,
                "departamento_id": dept_combo.currentData(),
                "motivo": motivo_input.text().strip() or None,
            }
            with get_engine().begin() as db:
                crear_autorizado(db, values)
            QMessageBox.information(self, "Creado", "Software autorizado anadido correctamente")
            self._load_detalle()
            self._load_agrupado()

    def _show_edit_dialog(self) -> None:
        row = self.detalle_table.currentRow()
        if row < 0 or not hasattr(self, "_detalle_data") or row >= len(self._detalle_data):
            QMessageBox.warning(self, "Error", "Selecciona un registro de la tabla")
            return
        item = self._detalle_data[row]

        dialog = QDialog(self)
        dialog.setWindowTitle("Editar software autorizado")
        layout = QFormLayout(dialog)

        nombre_input = QLineEdit(item.get("software_nombre") or item.get("nombre", ""))
        fabricante_input = QLineEdit(item.get("fabricante") or "")
        tipo_input = QLineEdit(item.get("tipo") or "")
        version_input = QLineEdit(item.get("version") or "")
        obs_input = QLineEdit(item.get("observaciones") or "")

        layout.addRow("Nombre:", nombre_input)
        layout.addRow("Fabricante:", fabricante_input)
        layout.addRow("Tipo:", tipo_input)
        layout.addRow("Version:", version_input)
        layout.addRow("Observaciones:", obs_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec() == QDialog.Accepted:
            values = {
                "nombre": nombre_input.text().strip(),
                "fabricante": fabricante_input.text().strip() or None,
                "tipo": tipo_input.text().strip() or None,
                "version": version_input.text().strip() or None,
                "observaciones": obs_input.text().strip() or None,
            }
            with get_engine().begin() as db:
                actualizar_autorizado(db, item["id"], values)
            QMessageBox.information(self, "Actualizado", "Registro actualizado")
            self._load_detalle()
            self._load_agrupado()

    def _delete_autorizado(self) -> None:
        row = self.detalle_table.currentRow()
        if row < 0 or not hasattr(self, "_detalle_data") or row >= len(self._detalle_data):
            QMessageBox.warning(self, "Error", "Selecciona un registro de la tabla")
            return
        item = self._detalle_data[row]
        nombre = item.get("software_nombre") or item.get("nombre", "")
        reply = QMessageBox.question(
            self,
            "Confirmar",
            f"Archivar {nombre}?\nSe marcara como inactivo.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        with get_engine().begin() as db:
            eliminar_autorizado(db, item["id"])
        QMessageBox.information(self, "Archivado", f"{nombre} archivado")
        self._load_detalle()
        self._load_agrupado()

    def _delete_grupo(self) -> None:
        row = self.agrupado_table.currentRow()
        if row < 0 or not hasattr(self.agrupado_table, "_data"):
            QMessageBox.warning(self, "Error", "Selecciona un grupo")
            return
        grupo_data = self.agrupado_table._data[row]
        reply = QMessageBox.question(
            self,
            "Confirmar",
            f"Archivar todo el grupo '{grupo_data['nombre']}' ({grupo_data['registros']} registros)?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        with get_engine().begin() as db:
            count = eliminar_autorizado_grupo(db, grupo_data["grupo"])
        QMessageBox.information(self, "Archivado", f"{count} registros archivados")
        self._load_agrupado()
        self._load_detalle()
