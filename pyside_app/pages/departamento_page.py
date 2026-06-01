from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
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
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from database.connection import get_engine
from modules.autorizado import (
    autorizar_exclusivos_automaticamente,
    autorizar_softwares,
    detectar_autorizados_para_promocion,
    detectar_software_exclusivo,
    promocionar_autorizaciones_generales,
)
from modules.equipos import (
    actualizar_usuario_dispositivo,
    alertas_equipo,
    crear_equipo,
    estado_importacion,
    existe_equipo,
    exportar_equipos_excel,
    listar_equipos,
)
from modules.exportacion import generar_excel, generar_excel_importaciones
from modules.importacion import (
    aplicar_diff,
    calcular_diff,
    contar_reactivaciones_pendientes,
    listar_reactivaciones_pendientes,
    resolver_reactivacion,
    ultima_importacion_por_equipo,
    ultimas_importaciones_por_equipo,
)
from modules.software import (
    actualizar_software_revision,
    contar_software_sin_dispositivos,
    eliminar_software_inventario,
    listar_departamentos_con_estadisticas,
    listar_inventario,
    obtener_departamento_por_codigo,
    ocultar_software_sin_dispositivos,
)
from utils.parser import parse_file, parse_paste

from pyside_app.widgets.data_table import DataTable

if TYPE_CHECKING:
    from pyside_app.main_window import MainWindow


class DepartamentoPage(QWidget):
    def __init__(self, main_window: MainWindow, departamento_codigo: str) -> None:
        super().__init__()
        self.main_window = main_window
        self.departamento_codigo = departamento_codigo
        self.dept: dict | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        self.title_label = QLabel()
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        layout.addWidget(self.title_label)

        self.subtitle_label = QLabel()
        self.subtitle_label.setStyleSheet("color: #666;")
        layout.addWidget(self.subtitle_label)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { background: white; border: 1px solid #ddd; border-top: none; }
            QTabBar::tab { padding: 8px 16px; }
            QTabBar::tab:selected { background: white; font-weight: bold; }
        """)
        layout.addWidget(self.tabs)

        self.inv_tab = QWidget()
        self.import_tab = QWidget()
        self.export_tab = QWidget()
        self.devices_tab = QWidget()
        self.reactivations_tab = QWidget()

        self.tabs.addTab(self.inv_tab, "Inventario")
        self.tabs.addTab(self.import_tab, "Importar")
        self.tabs.addTab(self.export_tab, "Exportar")
        self.tabs.addTab(self.devices_tab, "Dispositivos")
        self.tabs.addTab(self.reactivations_tab, "Reactivaciones")

        self._setup_inventario_tab()
        self._setup_import_tab()
        self._setup_export_tab()
        self._setup_devices_tab()
        self._setup_reactivations_tab()

    def on_activate(self) -> None:
        self._load_dept()

    # --- INVENTARIO TAB ---
    def _setup_inventario_tab(self) -> None:
        layout = QVBoxLayout(self.inv_tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        filter_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar programa...")
        filter_layout.addWidget(self.search_input, stretch=2)

        self.equipo_combo = QComboBox()
        self.equipo_combo.setMinimumWidth(200)
        filter_layout.addWidget(self.equipo_combo, stretch=1)

        self.vista_basica_btn = QPushButton("Basica")
        self.vista_detallada_btn = QPushButton("Detallada")
        for btn in (self.vista_basica_btn, self.vista_detallada_btn):
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton { padding: 4px 12px; border: 1px solid #ccc; border-radius: 4px; }
                QPushButton:checked { background: #0f3460; color: white; border-color: #0f3460; }
            """)
        self.vista_basica_btn.setChecked(True)
        self.vista_basica_btn.clicked.connect(lambda: self._set_vista("basica"))
        self.vista_detallada_btn.clicked.connect(lambda: self._set_vista("detallada"))

        filter_layout.addWidget(self.vista_basica_btn)
        filter_layout.addWidget(self.vista_detallada_btn)

        search_btn = QPushButton("Filtrar")
        search_btn.clicked.connect(self._load_inventario_tab)
        filter_layout.addWidget(search_btn)

        layout.addLayout(filter_layout)

        self.inv_table = DataTable()
        self.inv_table.setSelectionMode(self.inv_table.SelectionMode.MultiSelection)
        layout.addWidget(self.inv_table, stretch=1)

        btn_layout = QHBoxLayout()
        self.save_inv_btn = QPushButton("Guardar cambios")
        self.save_inv_btn.setStyleSheet("""
            QPushButton { background: #27ae60; color: white; padding: 8px 16px;
                          border: none; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background: #219a52; }
        """)
        self.save_inv_btn.clicked.connect(self._save_inventario)
        btn_layout.addWidget(self.save_inv_btn)

        self.cleanup_btn = QPushButton("Ocultar software sin dispositivos")
        self.cleanup_btn.setStyleSheet("""
            QPushButton { background: #e67e22; color: white; padding: 8px 16px;
                          border: none; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background: #d35400; }
        """)
        self.cleanup_btn.clicked.connect(self._cleanup_software)
        btn_layout.addWidget(self.cleanup_btn)

        layout.addLayout(btn_layout)

        self.inv_vista = "basica"

    def _set_vista(self, vista: str) -> None:
        self.inv_vista = vista
        self.vista_basica_btn.setChecked(vista == "basica")
        self.vista_detallada_btn.setChecked(vista == "detallada")
        self._load_inventario_tab()

    def _load_inventario_tab(self) -> None:
        if not self.dept:
            return
        try:
            with get_engine().connect() as db:
                equipos = listar_equipos(db, self.dept["id"], solo_activos=True)
                self.equipo_combo.clear()
                self.equipo_combo.addItem("Todos", None)
                for eq in equipos:
                    self.equipo_combo.addItem(eq["nombre"], eq["id"])

                texto = self.search_input.text().strip() or None
                equipo_id = self.equipo_combo.currentData()
                equipo_ids = [equipo_id] if equipo_id else None

                inventario = listar_inventario(
                    db,
                    self.dept["id"],
                    equipo_ids=equipo_ids,
                    en_guia_105="todos",
                    texto_libre=texto,
                )
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        if not inventario:
            self.inv_table.load_data([])
            return

        base_cols = ["id", "codigo", "nombre", "fabricante", "version_referencia", "dispositivos"]
        detail_cols = ["clasificacion_informacion", "en_guia_105", "observaciones"]
        display_cols = base_cols + (detail_cols if self.inv_vista == "detallada" else [])

        def fmt_en_guia(val):
            if val is None:
                return "Pendiente"
            return "Si" if val else "No"

        data = []
        for row in inventario:
            entry = {
                "id": row["id"],
                "codigo": row.get("codigo", ""),
                "nombre": row.get("nombre", ""),
                "fabricante": row.get("fabricante", ""),
                "version_referencia": row.get("version_referencia", ""),
                "dispositivos": row.get("dispositivos", ""),
                "clasificacion_informacion": row.get("clasificacion_informacion", ""),
                "en_guia_105": fmt_en_guia(row.get("en_guia_105")),
                "observaciones": row.get("observaciones", ""),
            }
            data.append(entry)

        header_names = {
            "id": "ID",
            "codigo": "Codigo",
            "nombre": "Programa",
            "fabricante": "Fabricante",
            "version_referencia": "Version",
            "dispositivos": "Dispositivos",
            "clasificacion_informacion": "Clasificacion",
            "en_guia_105": "Guia 105",
            "observaciones": "Observaciones",
        }
        headers = [header_names[c] for c in display_cols]
        self.inv_table.load_data(data, headers)
        self._inv_data = inventario

    def _save_inventario(self) -> None:
        if not hasattr(self, "_inv_data") or not self._inv_data:
            return
        rows_by_id = {row["id"]: row for row in self._inv_data}
        updated = 0
        archived = 0
        with get_engine().begin() as db:
            for row_idx in range(self.inv_table.rowCount()):
                item_id_item = self.inv_table.item(row_idx, 0)
                if not item_id_item:
                    continue
                try:
                    item_id = int(item_id_item.text())
                except ValueError:
                    continue
                original = rows_by_id.get(item_id)
                if not original:
                    continue
                archivable = False
                fabricante = self._get_table_text(row_idx, 3)
                version = self._get_table_text(row_idx, 4)
                values = {
                    "fabricante": fabricante or None,
                    "version_referencia": version or None,
                    "fecha_ultima_actualizacion": date.today(),
                }
                if self.inv_vista == "detallada":
                    clasificacion = self._get_table_text(row_idx, 6)
                    en_guia_raw = self._get_table_text(row_idx, 7)
                    observaciones = self._get_table_text(row_idx, 8)
                    values.update({
                        "clasificacion_informacion": clasificacion or "Media",
                        "en_guia_105": {"Si": True, "No": False}.get(en_guia_raw),
                        "observaciones_elena": observaciones or None,
                        "observaciones_toni": None,
                    })

                changed = any(
                    values.get(k) != original.get(k)
                    for k in values
                    if k != "fecha_ultima_actualizacion"
                )
                if changed:
                    actualizar_software_revision(db, item_id, values)
                    updated += 1

        QMessageBox.information(
            self, "Guardado", f"Registros actualizados: {updated}. Archivados: {archived}."
        )
        self._load_inventario_tab()

    @staticmethod
    def _get_table_text(table: DataTable, row: int, col: int) -> str:
        item = table.item(row, col)
        return item.text() if item else ""

    def _cleanup_software(self) -> None:
        if not self.dept:
            return
        reply = QMessageBox.question(
            self,
            "Confirmar limpieza",
            "Se ocultara el software activo sin dispositivos asignados.\nContinuar?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        with get_engine().begin() as db:
            hidden = ocultar_software_sin_dispositivos(db, self.dept["id"])
        QMessageBox.information(self, "Limpieza", f"Registros ocultados: {hidden}")
        self._load_inventario_tab()

    # --- IMPORT TAB ---
    def _setup_import_tab(self) -> None:
        layout = QVBoxLayout(self.import_tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        equipo_layout = QHBoxLayout()
        equipo_layout.addWidget(QLabel("Dispositivo:"))
        self.import_equipo_combo = QComboBox()
        self.import_equipo_combo.setMinimumWidth(300)
        equipo_layout.addWidget(self.import_equipo_combo)
        self.new_equipo_btn = QPushButton("+ Nuevo dispositivo")
        self.new_equipo_btn.clicked.connect(self._show_new_equipo_dialog)
        equipo_layout.addWidget(self.new_equipo_btn)
        layout.addLayout(equipo_layout)

        self.new_equipo_name = QLineEdit()
        self.new_equipo_name.setPlaceholderText("Nombre del nuevo dispositivo")
        self.new_equipo_name.hide()
        layout.addWidget(self.new_equipo_name)

        paste_label = QLabel("Pegar texto desde Panda Adaptive Defense:")
        layout.addWidget(paste_label)

        self.paste_text = QTextEdit()
        self.paste_text.setPlaceholderText(
            "Nombre\tEditor\tFecha de instalacion\tTamano\tVersion\n"
            "Adobe Acrobat\tAdobe\t18/05/2026\t1,2 GB\t26.001.21563"
        )
        self.paste_text.setFixedHeight(180)
        layout.addWidget(self.paste_text)

        btn_layout = QHBoxLayout()
        self.analyze_btn = QPushButton("Analizar texto")
        self.analyze_btn.setStyleSheet("""
            QPushButton { background: #0f3460; color: white; padding: 8px 16px;
                          border: none; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background: #1a5276; }
        """)
        self.analyze_btn.clicked.connect(self._analyze_import)
        btn_layout.addWidget(self.analyze_btn)

        self.file_btn = QPushButton("Subir fichero CSV/XLSX...")
        self.file_btn.clicked.connect(self._upload_file)
        btn_layout.addWidget(self.file_btn)

        layout.addLayout(btn_layout)

        self.import_result_label = QLabel()
        self.import_result_label.setWordWrap(True)
        layout.addWidget(self.import_result_label)

        self.diff_table = DataTable()
        layout.addWidget(self.diff_table, stretch=1)

        self.confirm_btn = QPushButton("Confirmar e importar")
        self.confirm_btn.setStyleSheet("""
            QPushButton { background: #27ae60; color: white; padding: 10px 24px;
                          border: none; border-radius: 4px; font-weight: bold; font-size: 11pt; }
            QPushButton:hover { background: #219a52; }
            QPushButton:disabled { background: #ccc; }
        """)
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.clicked.connect(self._confirm_import)
        layout.addWidget(self.confirm_btn)

        self._pending_diff = None
        self._pending_programas = None
        self._pending_equipo_id = None
        self._pending_metodo = None

    def _load_import_tab(self) -> None:
        if not self.dept:
            return
        try:
            with get_engine().connect() as db:
                equipos = listar_equipos(db, self.dept["id"], solo_activos=True)
            self.import_equipo_combo.clear()
            for eq in equipos:
                self.import_equipo_combo.addItem(f"{eq['nombre']} (id {eq['id']})", eq["id"])
            self.import_equipo_combo.addItem("+ Crear dispositivo nuevo", -1)
        except Exception:
            pass

    def _show_new_equipo_dialog(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Nuevo dispositivo")
        layout = QFormLayout(dialog)
        name_input = QLineEdit()
        user_input = QLineEdit()
        layout.addRow("Nombre:", name_input)
        layout.addRow("Usuario:", user_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec() == QDialog.Accepted:
            name = name_input.text().strip()
            if not name:
                QMessageBox.warning(self, "Error", "El nombre es obligatorio")
                return
            with get_engine().begin() as db:
                if existe_equipo(db, self.dept["id"], name):
                    QMessageBox.warning(self, "Error", "Ya existe un dispositivo con ese nombre")
                    return
                equipo_id = crear_equipo(db, self.dept["id"], name, user_input.text().strip() or None)
            QMessageBox.information(self, "Creado", f"Dispositivo {name} creado (id {equipo_id})")
            self._load_import_tab()

    def _analyze_import(self) -> None:
        text = self.paste_text.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Error", "Pega el listado primero")
            return

        equipo_id = self.import_equipo_combo.currentData()
        if equipo_id is None or equipo_id == -1:
            QMessageBox.warning(self, "Error", "Selecciona un dispositivo")
            return

        programas = parse_paste(text)
        if not programas:
            QMessageBox.warning(self, "Error", "No se detectaron programas")
            return

        with get_engine().connect() as db:
            diff = calcular_diff(equipo_id, programas, db)

        self._pending_diff = diff
        self._pending_programas = programas
        self._pending_equipo_id = equipo_id
        self._pending_metodo = "paste"

        self._show_diff(diff)

    def _upload_file(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar fichero", "", "CSV o XLSX (*.csv *.xlsx)"
        )
        if not path:
            return

        equipo_id = self.import_equipo_combo.currentData()
        if equipo_id is None or equipo_id == -1:
            QMessageBox.warning(self, "Error", "Selecciona un dispositivo")
            return

        with open(path, "rb") as f:
            file_bytes = f.read()
        filename = path.rsplit("\\", 1)[-1]

        programas = parse_file(file_bytes, filename)
        if not programas:
            QMessageBox.warning(self, "Error", "No se detectaron programas en el fichero")
            return

        with get_engine().connect() as db:
            diff = calcular_diff(equipo_id, programas, db)

        self._pending_diff = diff
        self._pending_programas = programas
        self._pending_equipo_id = equipo_id
        self._pending_metodo = "file"

        self._show_diff(diff)

    def _show_diff(self, diff: dict) -> None:
        total = (
            len(diff["nuevos"])
            + len(diff["actualizados"])
            + len(diff["cambios_version"])
            + len(diff["eliminados"])
        )
        self.import_result_label.setText(
            f"Nuevos: {len(diff['nuevos'])}  |  Actualizados: {len(diff['actualizados'])}  |  "
            f"Cambios version: {len(diff['cambios_version'])}  |  Eliminados: {len(diff['eliminados'])}"
        )

        diff_rows = []
        for item in diff["nuevos"]:
            diff_rows.append({
                "Tipo": "Nuevo",
                "Programa": item.get("nombre", ""),
                "Fabricante": item.get("fabricante", ""),
                "Version": str(item.get("version", "")),
            })
        for item in diff["cambios_version"]:
            diff_rows.append({
                "Tipo": "Cambio version",
                "Programa": item.get("nombre", ""),
                "Fabricante": item.get("fabricante", ""),
                "Version": f"{item.get('version_anterior', '')} -> {item.get('version_nueva', '')}",
            })
        for item in diff["eliminados"]:
            diff_rows.append({
                "Tipo": "Eliminado",
                "Programa": item.get("nombre", ""),
                "Fabricante": item.get("fabricante", ""),
                "Version": "",
            })

        if total == 0:
            self.diff_table.load_data([])
            self.import_result_label.setText("No hay cambios respecto a la ultima importacion.")
            self.confirm_btn.setEnabled(False)
        else:
            self.diff_table.load_data(diff_rows, ["Tipo", "Programa", "Fabricante", "Version"])
            self.confirm_btn.setEnabled(True)

    def _confirm_import(self) -> None:
        if not self._pending_diff or not self._pending_programas or not self._pending_equipo_id:
            return
        try:
            with get_engine().begin() as db:
                importacion_id = aplicar_diff(
                    self._pending_equipo_id,
                    self._pending_programas,
                    self._pending_diff,
                    db,
                    self._pending_metodo,
                )
                exclusivos = autorizar_exclusivos_automaticamente(db, self.dept["id"])
                pendientes = contar_reactivaciones_pendientes(db, self.dept["id"])
            QMessageBox.information(
                self,
                "Importacion completada",
                f"Importacion registrada con id {importacion_id}.\n"
                f"Software exclusivos autorizados: {exclusivos}\n"
                f"Reactivaciones pendientes: {pendientes}",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Error al importar:\n{exc}")
            return

        self._pending_diff = None
        self._pending_programas = None
        self._pending_equipo_id = None
        self._pending_metodo = None
        self.confirm_btn.setEnabled(False)
        self.import_result_label.setText("")
        self.diff_table.load_data([])
        self.paste_text.clear()

    # --- EXPORT TAB ---
    def _setup_export_tab(self) -> None:
        layout = QVBoxLayout(self.export_tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.detalle_check = QCheckBox("Incluir detalle por dispositivo")

        self.export_dept_btn = QPushButton("Generar Excel del departamento")
        self.export_dept_btn.setStyleSheet("""
            QPushButton { background: #27ae60; color: white; padding: 8px 16px;
                          border: none; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background: #219a52; }
        """)
        self.export_dept_btn.clicked.connect(self._export_departamento)
        layout.addWidget(self.detalle_check)
        layout.addWidget(self.export_dept_btn)

        self.export_hist_btn = QPushButton("Exportar historial de importaciones")
        self.export_hist_btn.clicked.connect(self._export_historial)
        layout.addWidget(self.export_hist_btn)

        layout.addStretch()

    def _export_departamento(self) -> None:
        if not self.dept:
            return
        try:
            with get_engine().connect() as db:
                data = generar_excel(db, [self.dept["id"]], detalle_por_equipo=self.detalle_check.isChecked())
            from PySide6.QtWidgets import QFileDialog
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Guardar Excel",
                f"inventario_{self.dept['codigo']}.xlsx",
                "Excel (*.xlsx)",
            )
            if filename:
                with open(filename, "wb") as f:
                    f.write(data)
                QMessageBox.information(self, "Exportado", f"Excel guardado en:\n{filename}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"No se pudo exportar:\n{exc}")

    def _export_historial(self) -> None:
        if not self.dept:
            return
        try:
            with get_engine().connect() as db:
                data = generar_excel_importaciones(db, self.dept["id"])
            from PySide6.QtWidgets import QFileDialog
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Guardar Excel",
                f"historial_importaciones_{self.dept['codigo']}.xlsx",
                "Excel (*.xlsx)",
            )
            if filename:
                with open(filename, "wb") as f:
                    f.write(data)
                QMessageBox.information(self, "Exportado", f"Historial guardado en:\n{filename}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"No se pudo exportar:\n{exc}")

    # --- DEVICES TAB ---
    def _setup_devices_tab(self) -> None:
        layout = QVBoxLayout(self.devices_tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.devices_table = DataTable()
        layout.addWidget(self.devices_table, stretch=1)

        btn_layout = QHBoxLayout()
        self.export_devices_btn = QPushButton("Exportar equipos a Excel")
        self.export_devices_btn.clicked.connect(self._export_devices)
        btn_layout.addWidget(self.export_devices_btn)
        layout.addLayout(btn_layout)

        self.device_detail_label = QLabel()
        self.device_detail_label.setWordWrap(True)
        self.device_detail_label.setStyleSheet("background: #f0f0f0; padding: 12px; border-radius: 4px;")
        layout.addWidget(self.device_detail_label)

        user_layout = QHBoxLayout()
        user_layout.addWidget(QLabel("Usuario del dispositivo:"))
        self.user_input = QLineEdit()
        user_layout.addWidget(self.user_input, stretch=1)
        self.save_user_btn = QPushButton("Guardar usuario")
        self.save_user_btn.clicked.connect(self._save_user)
        user_layout.addWidget(self.save_user_btn)
        layout.addLayout(user_layout)

    def _load_devices_tab(self) -> None:
        if not self.dept:
            return
        try:
            with get_engine().connect() as db:
                equipos = listar_equipos(db, self.dept["id"])
        except Exception as exc:
            return

        data = []
        for eq in equipos:
            data.append({
                "id": eq["id"],
                "Dispositivo": eq["nombre"],
                "Usuario": eq.get("notas") or "",
                "Activo": "Si" if eq["activo"] else "No",
                "Ultima importacion": str(eq.get("ultima_importacion") or ""),
                "Estado": estado_importacion(eq.get("ultima_importacion")),
                "Software activo": str(eq.get("total_software_activo") or 0),
            })

        self.devices_table.load_data(
            data,
            ["Dispositivo", "Usuario", "Activo", "Ultima importacion", "Estado", "Software activo"],
        )
        self._equipos_data = equipos
        self.devices_table.itemSelectionChanged.connect(self._on_device_selected)

    def _on_device_selected(self) -> None:
        row = self.devices_table.currentRow()
        if row < 0 or not hasattr(self, "_equipos_data"):
            return
        id_item = self.devices_table.item(row, 0)
        if not id_item:
            return
        try:
            equipo_id = int(id_item.text())
        except ValueError:
            return
        equipo = next((eq for eq in self._equipos_data if eq["id"] == equipo_id), None)
        if not equipo:
            return

        alerts = alertas_equipo(equipo)
        detail = (
            f"<b>{equipo['nombre']}</b><br><br>"
            f"<b>Hardware:</b><br>"
            f"Tipo: {equipo.get('tipo_dispositivo') or '-'}<br>"
            f"Marca/Modelo: {equipo.get('marca_modelo') or '-'}<br>"
            f"N Serie: {equipo.get('num_serie') or '-'}<br>"
            f"MAC: {equipo.get('mac_address') or '-'}<br>"
            f"SO: {equipo.get('sistema_operativo') or '-'}<br>"
            f"Procesador: {equipo.get('procesador') or '-'}<br>"
            f"RAM: {equipo.get('ram') or '-'}<br>"
            f"Almacenamiento: {equipo.get('almacenamiento') or '-'}<br><br>"
            f"<b>Actividad:</b><br>"
            f"Responsable: {equipo.get('responsable') or '-'}<br>"
            f"Ubicacion: {equipo.get('ubicacion') or '-'}<br>"
            f"Coste: {equipo.get('coste') or '-'}<br>"
            f"Fecha adquisicion: {equipo.get('fecha_adquisicion') or '-'}<br>"
            f"Ultima importacion: {equipo.get('ultima_importacion') or '-'}<br><br>"
        )
        if alerts:
            detail += "<b>Alertas:</b><br>" + "<br>".join(f"! {a}" for a in alerts)
        else:
            detail += "<b>Sin alertas activas.</b>"

        self.device_detail_label.setText(detail)
        self.user_input.setText(equipo.get("notas") or "")
        self._selected_equipo_id = equipo_id

    def _save_user(self) -> None:
        if not hasattr(self, "_selected_equipo_id") or not self._selected_equipo_id:
            QMessageBox.warning(self, "Error", "Selecciona un dispositivo primero")
            return
        with get_engine().begin() as db:
            actualizar_usuario_dispositivo(db, self._selected_equipo_id, self.user_input.text().strip() or None)
        QMessageBox.information(self, "Guardado", "Usuario actualizado.")

    def _export_devices(self) -> None:
        if not self.dept or not hasattr(self, "_equipos_data"):
            return
        try:
            data = exportar_equipos_excel(self._equipos_data, self.dept["nombre"])
            from PySide6.QtWidgets import QFileDialog
            safe_dept = "".join(c if c.isalnum() else "_" for c in self.dept["nombre"])
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Guardar Excel",
                f"Inventario_Equipos_{safe_dept}_{date.today().isoformat()}.xlsx",
                "Excel (*.xlsx)",
            )
            if filename:
                with open(filename, "wb") as f:
                    f.write(data)
                QMessageBox.information(self, "Exportado", f"Equipos exportados a:\n{filename}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"No se pudo exportar:\n{exc}")

    # --- REACTIVATIONS TAB ---
    def _setup_reactivations_tab(self) -> None:
        layout = QVBoxLayout(self.reactivations_tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.reactivations_table = DataTable()
        layout.addWidget(self.reactivations_table, stretch=1)

        btn_layout = QHBoxLayout()
        self.reactivate_btn = QPushButton("Reactivar")
        self.reactivate_btn.setStyleSheet("""
            QPushButton { background: #27ae60; color: white; padding: 8px 16px;
                          border: none; border-radius: 4px; font-weight: bold; }
        """)
        self.reactivate_btn.clicked.connect(lambda: self._resolve_reactivation("reactivar"))
        btn_layout.addWidget(self.reactivate_btn)

        self.ignore_btn = QPushButton("Ignorar")
        self.ignore_btn.setStyleSheet("""
            QPushButton { background: #e74c3c; color: white; padding: 8px 16px;
                          border: none; border-radius: 4px; font-weight: bold; }
        """)
        self.ignore_btn.clicked.connect(lambda: self._resolve_reactivation("ignorar"))
        btn_layout.addWidget(self.ignore_btn)

        layout.addLayout(btn_layout)

    def _load_reactivations_tab(self) -> None:
        if not self.dept:
            return
        try:
            with get_engine().connect() as db:
                rows = listar_reactivaciones_pendientes(db, self.dept["id"])
        except Exception as exc:
            return

        data = []
        for row in rows:
            data.append({
                "id": row["id"],
                "Software": row["software_nombre"],
                "Version": row.get("version_referencia") or "",
                "Fabricante": row.get("fabricante") or "",
                "Equipo": row["equipo"],
                "Fecha deteccion": str(row.get("fecha_deteccion") or ""),
            })

        self.reactivations_table.load_data(
            data,
            ["Software", "Version", "Fabricante", "Equipo", "Fecha deteccion"],
        )
        self._reactivaciones_data = rows

    def _resolve_reactivation(self, accion: str) -> None:
        row = self.reactivations_table.currentRow()
        if row < 0 or not hasattr(self, "_reactivaciones_data") or row >= len(self._reactivaciones_data):
            QMessageBox.warning(self, "Error", "Selecciona una reactivacion de la tabla")
            return
        reactivacion_id = self._reactivaciones_data[row]["id"]
        with get_engine().begin() as db:
            resolver_reactivacion(db, reactivacion_id, accion)
        action_label = "reactivado" if accion == "reactivar" else "ignorado"
        QMessageBox.information(self, "Hecho", f"Software {action_label} correctamente.")
        self._load_reactivations_tab()

    def on_activate(self) -> None:
        self._load_dept()

    def _load_dept(self) -> None:
        try:
            with get_engine().connect() as db:
                dept_list = listar_departamentos_con_estadisticas(db)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"No se pudo conectar:\n{exc}")
            return

        self.dept = next(
            (item for item in dept_list if item["codigo"] == self.departamento_codigo),
            None,
        )
        if not self.dept:
            QMessageBox.critical(self, "Error", f"Departamento {self.departamento_codigo} no encontrado")
            return

        self.title_label.setText(self.dept["nombre"])
        self.subtitle_label.setText(
            f"{self.dept['n_equipos']} dispositivos  ·  {self.dept['n_software']} software"
        )

        self._load_inventario_tab()
        self._load_import_tab()
        self._load_devices_tab()
        self._load_reactivations_tab()
