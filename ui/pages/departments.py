"""
Vista por departamento — inventario + importar + exportar + dispositivos + reactivaciones.
Esta es la página más rica de la aplicación.
"""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

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
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.components.sortable_table import SortableTable
from ui.components.ui_kit import FeedbackBar
from ui.components.worker import run_in_thread

if TYPE_CHECKING:
    from ui.main_window import MainWindow


def _fetch_dept_list():
    from database.connection import get_engine
    from modules.software import listar_departamentos_con_estadisticas
    with get_engine().connect() as db:
        return listar_departamentos_con_estadisticas(db)


def _fetch_inventario(dept_id: int, equipo_id=None, texto=None):
    from database.connection import get_engine
    from modules.software import listar_inventario
    from modules.equipos import listar_equipos
    with get_engine().connect() as db:
        equipos = listar_equipos(db, dept_id, solo_activos=True)
        inv = listar_inventario(db, dept_id,
                                equipo_ids=[equipo_id] if equipo_id else None,
                                en_guia_105="todos",
                                texto_libre=texto or None)
    result = []
    for row in inv:
        r = dict(row)
        r["version_referencia"] = str(r.get("version_referencia") or "")
        r["en_guia_105_str"] = "Pendiente" if r.get("en_guia_105") is None else ("Sí" if r.get("en_guia_105") else "No")
        result.append(r)
    return result, equipos


def _fetch_dispositivos(dept_id: int):
    from database.connection import get_engine
    from modules.equipos import listar_equipos, estado_importacion
    with get_engine().connect() as db:
        rows = listar_equipos(db, dept_id)
    result = []
    for r in rows:
        item = dict(r)
        item["estado_import"] = estado_importacion(item.get("ultima_importacion"))
        item["activo_str"] = "Sí" if item.get("activo") else "No"
        result.append(item)
    return result


def _fetch_reactivaciones(dept_id: int):
    from database.connection import get_engine
    from modules.importacion import listar_reactivaciones_pendientes
    with get_engine().connect() as db:
        return listar_reactivaciones_pendientes(db, dept_id)


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


def _aplicar_diff(equipo_id: int, programas, diff, metodo: str, dept_id: int):
    from database.connection import get_engine
    from modules.importacion import aplicar_diff, contar_reactivaciones_pendientes
    from modules.autorizado import autorizar_exclusivos_automaticamente
    with get_engine().begin() as db:
        importacion_id = aplicar_diff(equipo_id, programas, diff, db, metodo)
        exclusivos = autorizar_exclusivos_automaticamente(db, dept_id)
        pendientes = contar_reactivaciones_pendientes(db, dept_id)
    return importacion_id, exclusivos, pendientes


HDRS_INV = ["Código", "Nombre", "Fabricante", "Versión", "Dispositivos", "Clasificación", "Guía 105"]
KEYS_INV = ["codigo", "nombre", "fabricante", "version_referencia", "dispositivos", "clasificacion_informacion", "en_guia_105_str"]

HDRS_DIFF = ["Tipo", "Programa", "Fabricante", "Versión"]
KEYS_DIFF = ["tipo", "nombre", "fabricante", "version_str"]

HDRS_DEV = ["ID", "Dispositivo", "Usuario", "Activo", "Última import.", "Estado", "Software"]
KEYS_DEV = ["id", "nombre", "notas", "activo_str", "ultima_importacion", "estado_import", "total_software_activo"]

HDRS_REACT = ["ID", "Software", "Versión", "Fabricante", "Equipo", "Fecha detección"]
KEYS_REACT = ["id", "software_nombre", "version_referencia", "fabricante", "equipo", "fecha_deteccion"]


class DepartmentsPage(QWidget):
    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__()
        self.main_window = main_window
        self._dept: dict | None = None
        self._departamentos: list[dict] = []
        self._equipos: list[dict] = []
        self._reactivaciones: list[dict] = []
        self._pending_diff = None
        self._pending_programas = None
        self._pending_equipo_id = None
        self._pending_metodo = None
        self._thread = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Cabecera con selector de departamento
        hdr_widget = QWidget()
        hdr_widget.setFixedHeight(60)
        hdr_layout = QHBoxLayout(hdr_widget)
        hdr_layout.setContentsMargins(24, 0, 24, 0)

        self._dept_combo = QComboBox()
        self._dept_combo.setMinimumWidth(240)
        self._dept_combo.currentIndexChanged.connect(self._on_dept_selected)
        hdr_layout.addWidget(QLabel("Departamento:"))
        hdr_layout.addWidget(self._dept_combo)

        self._dept_info = QLabel("")
        self._dept_info.setObjectName("labelSecondary")
        hdr_layout.addWidget(self._dept_info)
        hdr_layout.addStretch()

        layout.addWidget(hdr_widget)

        self._feedback = FeedbackBar()
        layout.addWidget(self._feedback)

        # Tabs
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs, stretch=1)

        self._inv_tab = QWidget()
        self._import_tab = QWidget()
        self._export_tab = QWidget()
        self._devices_tab = QWidget()
        self._react_tab = QWidget()

        self._tabs.addTab(self._inv_tab, "Inventario")
        self._tabs.addTab(self._import_tab, "Importar")
        self._tabs.addTab(self._export_tab, "Exportar")
        self._tabs.addTab(self._devices_tab, "Dispositivos")
        self._tabs.addTab(self._react_tab, "Reactivaciones")

        self._setup_inv_tab()
        self._setup_import_tab()
        self._setup_export_tab()
        self._setup_devices_tab()
        self._setup_react_tab()

    # ── Inventario ─────────────────────────────────────────────────

    def _setup_inv_tab(self) -> None:
        layout = QVBoxLayout(self._inv_tab)
        layout.setContentsMargins(16, 12, 16, 12)

        toolbar = QHBoxLayout()
        self._inv_search = QLineEdit()
        self._inv_search.setPlaceholderText("Buscar programa...")
        self._inv_search.textChanged.connect(lambda t: self._inv_table.filter(t))
        toolbar.addWidget(self._inv_search)
        self._equipo_filter = QComboBox()
        self._equipo_filter.setMinimumWidth(180)
        self._equipo_filter.addItem("Todos los dispositivos", None)
        self._equipo_filter.currentIndexChanged.connect(self._reload_inventario)
        toolbar.addWidget(self._equipo_filter)
        toolbar.addStretch()
        self._cleanup_btn = QPushButton("Ocultar huérfanos")
        self._cleanup_btn.clicked.connect(self._cleanup_orphans)
        toolbar.addWidget(self._cleanup_btn)
        layout.addLayout(toolbar)

        self._inv_table = SortableTable(headers=HDRS_INV, keys=KEYS_INV)
        self._inv_table.row_activated.connect(self._on_inv_row_activated)
        layout.addWidget(self._inv_table, stretch=1)

    def _reload_inventario(self) -> None:
        if not self._dept:
            return
        equipo_id = self._equipo_filter.currentData()
        texto = self._inv_search.text().strip() or None
        run_in_thread(self, _fetch_inventario, self._dept["id"], equipo_id, texto,
                      on_done=self._on_inv_loaded, on_error=self._show_error)

    def _on_inv_loaded(self, result) -> None:
        inv, equipos = result
        self._equipos = equipos
        self._inv_table.load_data(inv)

        self._equipo_filter.blockSignals(True)
        cur = self._equipo_filter.currentData()
        self._equipo_filter.clear()
        self._equipo_filter.addItem("Todos los dispositivos", None)
        for eq in equipos:
            self._equipo_filter.addItem(eq["nombre"], eq["id"])
            if eq["id"] == cur:
                self._equipo_filter.setCurrentIndex(self._equipo_filter.count() - 1)
        self._equipo_filter.blockSignals(False)

        self._import_equipo_combo.blockSignals(True)
        cur2 = self._import_equipo_combo.currentData()
        self._import_equipo_combo.clear()
        for eq in equipos:
            self._import_equipo_combo.addItem(f"{eq['nombre']} (id {eq['id']})", eq["id"])
        for i in range(self._import_equipo_combo.count()):
            if self._import_equipo_combo.itemData(i) == cur2:
                self._import_equipo_combo.setCurrentIndex(i)
                break
        self._import_equipo_combo.blockSignals(False)

    def _on_inv_row_activated(self, row: dict) -> None:
        QMessageBox.information(
            self, row.get("nombre", ""),
            f"Código: {row.get('codigo', '')}\n"
            f"Fabricante: {row.get('fabricante', '')}\n"
            f"Versión: {row.get('version_referencia', '')}\n"
            f"Dispositivos: {row.get('dispositivos', '')}\n"
            f"Guía 105: {row.get('en_guia_105_str', '')}"
        )

    def _cleanup_orphans(self) -> None:
        if not self._dept:
            return
        reply = QMessageBox.question(
            self, "Ocultar huérfanos",
            "Se ocultará el software activo sin dispositivos asignados.\n¿Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            from database.connection import get_engine
            from modules.software import ocultar_software_sin_dispositivos
            with get_engine().begin() as db:
                hidden = ocultar_software_sin_dispositivos(db, self._dept["id"])
            self._feedback.show_message(f"Registros ocultados: {hidden}", "success")
            self._reload_inventario()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    # ── Importar ────────────────────────────────────────────────────

    def _setup_import_tab(self) -> None:
        layout = QVBoxLayout(self._import_tab)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        eq_row = QHBoxLayout()
        eq_row.addWidget(QLabel("Dispositivo:"))
        self._import_equipo_combo = QComboBox()
        self._import_equipo_combo.setMinimumWidth(300)
        eq_row.addWidget(self._import_equipo_combo)
        self._new_equipo_btn = QPushButton("+ Nuevo dispositivo")
        self._new_equipo_btn.clicked.connect(self._show_new_equipo_dialog)
        eq_row.addWidget(self._new_equipo_btn)
        eq_row.addStretch()
        layout.addLayout(eq_row)

        layout.addWidget(QLabel("Pegar texto desde Panda Adaptive Defense:"))
        self._paste_area = QTextEdit()
        self._paste_area.setPlaceholderText("Nombre\tEditor\tFecha de instalación\tTamaño\tVersión")
        self._paste_area.setFixedHeight(160)
        layout.addWidget(self._paste_area)

        btn_row = QHBoxLayout()
        self._analyze_btn = QPushButton("Analizar texto")
        self._analyze_btn.setObjectName("primary")
        self._analyze_btn.clicked.connect(self._analyze_paste)
        btn_row.addWidget(self._analyze_btn)
        self._file_btn = QPushButton("Subir fichero CSV/XLSX...")
        self._file_btn.clicked.connect(self._upload_file)
        btn_row.addWidget(self._file_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._import_result_lbl = QLabel("")
        self._import_result_lbl.setObjectName("labelSecondary")
        layout.addWidget(self._import_result_lbl)

        self._diff_table = SortableTable(headers=HDRS_DIFF, keys=KEYS_DIFF)
        self._diff_table.setFixedHeight(200)
        layout.addWidget(self._diff_table)

        self._confirm_btn = QPushButton("Confirmar e importar")
        self._confirm_btn.setObjectName("primary")
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.clicked.connect(self._confirm_import)
        layout.addWidget(self._confirm_btn)
        layout.addStretch()

    def _show_new_equipo_dialog(self) -> None:
        if not self._dept:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Nuevo dispositivo")
        form = QFormLayout(dlg)
        name_input = QLineEdit()
        user_input = QLineEdit()
        form.addRow("Nombre:", name_input)
        form.addRow("Usuario:", user_input)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            name = name_input.text().strip()
            if not name:
                QMessageBox.warning(self, "Error", "El nombre es obligatorio.")
                return
            try:
                from database.connection import get_engine
                from modules.equipos import crear_equipo, existe_equipo
                with get_engine().begin() as db:
                    if existe_equipo(db, self._dept["id"], name):
                        QMessageBox.warning(self, "Error", "Ya existe un dispositivo con ese nombre.")
                        return
                    equipo_id = crear_equipo(db, self._dept["id"], name, user_input.text().strip() or None)
                self._feedback.show_message(f"Dispositivo '{name}' creado (id {equipo_id}).", "success")
                self._reload_inventario()
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))

    def _analyze_paste(self) -> None:
        text = self._paste_area.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Error", "Pega el listado primero.")
            return
        equipo_id = self._import_equipo_combo.currentData()
        if not equipo_id:
            QMessageBox.warning(self, "Error", "Selecciona un dispositivo.")
            return
        run_in_thread(self, _calcular_diff, equipo_id, text,
                      on_done=lambda r: self._on_diff_ready(r, "paste"),
                      on_error=self._show_error)

    def _upload_file(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar fichero", "", "CSV o XLSX (*.csv *.xlsx)")
        if not path:
            return
        equipo_id = self._import_equipo_combo.currentData()
        if not equipo_id:
            QMessageBox.warning(self, "Error", "Selecciona un dispositivo.")
            return
        with open(path, "rb") as f:
            file_bytes = f.read()
        import os
        filename = os.path.basename(path)
        run_in_thread(self, _calcular_diff_file, equipo_id, file_bytes, filename,
                      on_done=lambda r: self._on_diff_ready(r, "file"),
                      on_error=self._show_error)

    def _on_diff_ready(self, result, metodo: str) -> None:
        programas, diff = result
        if programas is None:
            QMessageBox.warning(self, "Error", "No se detectaron programas.")
            self._confirm_btn.setEnabled(False)
            return
        self._pending_diff = diff
        self._pending_programas = programas
        self._pending_equipo_id = self._import_equipo_combo.currentData()
        self._pending_metodo = metodo

        rows = []
        for item in diff.get("nuevos", []):
            rows.append({"tipo": "Nuevo", "nombre": item.get("nombre", ""), "fabricante": item.get("fabricante", ""), "version_str": str(item.get("version", ""))})
        for item in diff.get("cambios_version", []):
            rows.append({"tipo": "Cambio versión", "nombre": item.get("nombre", ""), "fabricante": item.get("fabricante", ""), "version_str": f"{item.get('version_anterior', '')} → {item.get('version_nueva', '')}"})
        for item in diff.get("eliminados", []):
            rows.append({"tipo": "Eliminado", "nombre": item.get("nombre", ""), "fabricante": item.get("fabricante", ""), "version_str": ""})

        self._diff_table.load_data(rows)
        total = len(diff.get("nuevos", [])) + len(diff.get("cambios_version", [])) + len(diff.get("eliminados", []))
        self._import_result_lbl.setText(
            f"Nuevos: {len(diff.get('nuevos', []))}  |  Actualizados: {len(diff.get('actualizados', []))}  |  "
            f"Cambios versión: {len(diff.get('cambios_version', []))}  |  Eliminados: {len(diff.get('eliminados', []))}"
        )
        self._confirm_btn.setEnabled(total > 0)

    def _confirm_import(self) -> None:
        if not self._pending_diff or not self._pending_equipo_id:
            return
        dept_id = self._dept["id"] if self._dept else None
        run_in_thread(
            self,
            _aplicar_diff,
            self._pending_equipo_id,
            self._pending_programas,
            self._pending_diff,
            self._pending_metodo,
            dept_id,
            on_done=self._on_import_done,
            on_error=self._show_error,
        )

    def _on_import_done(self, result) -> None:
        importacion_id, exclusivos, pendientes = result
        self._pending_diff = None
        self._pending_programas = None
        self._pending_equipo_id = None
        self._pending_metodo = None
        self._confirm_btn.setEnabled(False)
        self._diff_table.load_data([])
        self._import_result_lbl.setText("")
        self._paste_area.clear()
        self._feedback.show_message(
            f"Importacion registrada (id {importacion_id}). Software exclusivo: {exclusivos}. Reactivaciones pendientes: {pendientes}.",
            "success",
        )
        self._reload_inventario()

    # ── Exportar ────────────────────────────────────────────────────

    def _setup_export_tab(self) -> None:
        layout = QVBoxLayout(self._export_tab)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        self._export_dept_btn = QPushButton("Generar Excel del departamento")
        self._export_dept_btn.setObjectName("primary")
        self._export_dept_btn.clicked.connect(self._export_dept)
        layout.addWidget(self._export_dept_btn)

        self._export_hist_btn = QPushButton("Exportar historial de importaciones")
        self._export_hist_btn.clicked.connect(self._export_hist)
        layout.addWidget(self._export_hist_btn)

        self._export_dev_btn = QPushButton("Exportar equipos a Excel")
        self._export_dev_btn.clicked.connect(self._export_devices)
        layout.addWidget(self._export_dev_btn)

        layout.addStretch()

    def _export_dept(self) -> None:
        if not self._dept:
            return
        try:
            from database.connection import get_engine
            from modules.exportacion import generar_excel
            with get_engine().connect() as db:
                data = generar_excel(db, [self._dept["id"]])
            self._save_file(data, f"inventario_{self._dept['codigo']}.xlsx", "Excel (*.xlsx)")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _export_hist(self) -> None:
        if not self._dept:
            return
        try:
            from database.connection import get_engine
            from modules.exportacion import generar_excel_importaciones
            with get_engine().connect() as db:
                data = generar_excel_importaciones(db, self._dept["id"])
            self._save_file(data, f"historial_{self._dept['codigo']}.xlsx", "Excel (*.xlsx)")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _export_devices(self) -> None:
        try:
            from modules.equipos import exportar_equipos_excel
            if not self._equipos:
                self._feedback.show_message("No hay equipos cargados.", "warning")
                return
            dept_name = self._dept["nombre"] if self._dept else "Equipos"
            data = exportar_equipos_excel(self._equipos, dept_name)
            safe = "".join(c if c.isalnum() else "_" for c in dept_name)
            self._save_file(data, f"Equipos_{safe}_{date.today().isoformat()}.xlsx", "Excel (*.xlsx)")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _save_file(self, data: bytes, default_name: str, file_filter: str) -> None:
        from PySide6.QtWidgets import QFileDialog
        filename, _ = QFileDialog.getSaveFileName(self, "Guardar archivo", default_name, file_filter)
        if filename:
            with open(filename, "wb") as f:
                f.write(data)
            self._feedback.show_message(f"Archivo guardado en {filename}.", "success")

    # ── Dispositivos ────────────────────────────────────────────────

    def _setup_devices_tab(self) -> None:
        layout = QVBoxLayout(self._devices_tab)
        layout.setContentsMargins(16, 12, 16, 12)

        self._dev_table = SortableTable(headers=HDRS_DEV, keys=KEYS_DEV)
        self._dev_table.selection_changed.connect(self._on_dev_selected)
        layout.addWidget(self._dev_table, stretch=1)

        self._dev_detail = QLabel("")
        self._dev_detail.setWordWrap(True)
        self._dev_detail.setObjectName("labelSecondary")
        layout.addWidget(self._dev_detail)

        user_row = QHBoxLayout()
        user_row.addWidget(QLabel("Usuario:"))
        self._user_input = QLineEdit()
        user_row.addWidget(self._user_input, stretch=1)
        self._save_user_btn = QPushButton("Guardar usuario")
        self._save_user_btn.clicked.connect(self._save_user)
        user_row.addWidget(self._save_user_btn)
        layout.addLayout(user_row)

        self._selected_equipo_id = None

    def _on_dev_selected(self, row) -> None:
        if not row:
            self._dev_detail.setText("")
            return
        self._selected_equipo_id = row.get("id")
        from modules.equipos import alertas_equipo
        alerts = alertas_equipo(row)
        detail = (
            f"<b>{row.get('nombre', '')}</b><br><br>"
            f"SO: {row.get('sistema_operativo') or '—'} | "
            f"RAM: {row.get('ram') or '—'} | "
            f"CPU: {row.get('procesador') or '—'}<br>"
            f"Marca: {row.get('marca_modelo') or '—'} | N/S: {row.get('num_serie') or '—'}<br>"
            f"Responsable: {row.get('responsable') or '—'} | Ubicación: {row.get('ubicacion') or '—'}<br>"
        )
        if alerts:
            detail += "<br><b>Alertas:</b> " + " | ".join(alerts)
        self._dev_detail.setText(detail)
        self._user_input.setText(row.get("notas") or "")

    def _save_user(self) -> None:
        if not self._selected_equipo_id:
            QMessageBox.warning(self, "Error", "Selecciona un dispositivo primero.")
            return
        try:
            from database.connection import get_engine
            from modules.equipos import actualizar_usuario_dispositivo
            with get_engine().begin() as db:
                actualizar_usuario_dispositivo(db, self._selected_equipo_id, self._user_input.text().strip() or None)
            self._feedback.show_message("Usuario actualizado.", "success")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    # ── Reactivaciones ──────────────────────────────────────────────

    def _setup_react_tab(self) -> None:
        layout = QVBoxLayout(self._react_tab)
        layout.setContentsMargins(16, 12, 16, 12)

        self._react_table = SortableTable(headers=HDRS_REACT, keys=KEYS_REACT)
        layout.addWidget(self._react_table, stretch=1)

        btn_row = QHBoxLayout()
        self._reactivate_btn = QPushButton("Reactivar")
        self._reactivate_btn.setObjectName("primary")
        self._reactivate_btn.clicked.connect(lambda: self._resolve_react("reactivar"))
        btn_row.addWidget(self._reactivate_btn)
        self._ignore_btn = QPushButton("Ignorar")
        self._ignore_btn.setObjectName("danger")
        self._ignore_btn.clicked.connect(lambda: self._resolve_react("ignorar"))
        btn_row.addWidget(self._ignore_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _resolve_react(self, accion: str) -> None:
        row = self._react_table.selected_row()
        if not row:
            QMessageBox.warning(self, "Error", "Selecciona una reactivación.")
            return
        try:
            from database.connection import get_engine
            from modules.importacion import resolver_reactivacion
            with get_engine().begin() as db:
                resolver_reactivacion(db, row["id"], accion)
            label = "reactivado" if accion == "reactivar" else "ignorado"
            self._feedback.show_message(f"Software {label}.", "success")
            self._load_react()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _load_react(self) -> None:
        if not self._dept:
            return
        run_in_thread(self, _fetch_reactivaciones, self._dept["id"],
                      on_done=lambda rows: self._react_table.load_data([dict(r) for r in rows]),
                      on_error=self._show_error)

    # ── Activación de la página ─────────────────────────────────────

    def on_activate(self) -> None:
        run_in_thread(self, _fetch_dept_list, on_done=self._on_depts_loaded, on_error=self._show_error)

    def _on_depts_loaded(self, depts: list[dict]) -> None:
        self._departamentos = depts
        cur = self._dept_combo.currentData()
        self._dept_combo.blockSignals(True)
        self._dept_combo.clear()
        for d in depts:
            self._dept_combo.addItem(d["nombre"], d["id"])
        for i in range(self._dept_combo.count()):
            if self._dept_combo.itemData(i) == cur:
                self._dept_combo.setCurrentIndex(i)
                break
        self._dept_combo.blockSignals(False)

        dept_id = self._dept_combo.currentData()
        if dept_id:
            self._dept = next((d for d in depts if d["id"] == dept_id), None)
            self._update_dept_info()
            self._reload_inventario()
            self._load_devices()
            self._load_react()

    def _on_dept_selected(self) -> None:
        dept_id = self._dept_combo.currentData()
        if not dept_id:
            return
        self._dept = next((d for d in self._departamentos if d["id"] == dept_id), None)
        self._update_dept_info()
        self._reload_inventario()
        self._load_devices()
        self._load_react()

    def _update_dept_info(self) -> None:
        if self._dept:
            self._dept_info.setText(
                f"{self._dept.get('n_equipos', 0)} dispositivos · {self._dept.get('n_software', 0)} software"
            )

    def _load_devices(self) -> None:
        if not self._dept:
            return
        run_in_thread(self, _fetch_dispositivos, self._dept["id"],
                      on_done=self._on_devices_loaded, on_error=self._show_error)

    def _on_devices_loaded(self, data: list[dict]) -> None:
        self._equipos = data
        self._dev_table.load_data(data)

    def _show_error(self, msg: str) -> None:
        QMessageBox.critical(self, "Error", msg)
