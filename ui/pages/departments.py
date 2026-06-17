"""
Vista por departamento: inventario, dispositivos y exportación.
La importación y las reactivaciones tienen ahora su propia pantalla (navegación
por tareas), por lo que esta página se centra en consultar y exportar.
"""
from __future__ import annotations

from datetime import date, datetime
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
    QVBoxLayout,
    QWidget,
)

from ui.components.confirm_dialog import confirm
from ui.components.detail_panel import DetailPanel
from ui.components.sortable_table import SortableTable
from ui.components.ui_kit import FeedbackBar, FilterBar, PageHeader
from ui.components.worker import run_in_thread

if TYPE_CHECKING:
    from ui.main_window import MainWindow


def _estado_label(fecha) -> str:
    if not fecha:
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


def _fetch_dept_list():
    from database.connection import get_engine
    from modules.software import listar_departamentos_con_estadisticas
    with get_engine().connect() as db:
        return listar_departamentos_con_estadisticas(db)


def _fetch_inventario(dept_id: int, equipo_id=None, texto=None):
    from database.connection import get_engine
    from modules.equipos import listar_equipos
    from modules.software import listar_inventario
    with get_engine().connect() as db:
        equipos = listar_equipos(db, dept_id, solo_activos=True)
        inv = listar_inventario(db, dept_id, equipo_ids=[equipo_id] if equipo_id else None,
                                en_guia_105="todos", texto_libre=texto or None)
    result = []
    for row in inv:
        r = dict(row)
        r["version_referencia"] = str(r.get("version_referencia") or "")
        r["en_guia_105_str"] = "Pendiente" if r.get("en_guia_105") is None else ("Sí" if r.get("en_guia_105") else "No")
        result.append(r)
    return result, equipos


def _fetch_dispositivos(dept_id: int):
    from database.connection import get_engine
    from modules.equipos import listar_equipos
    with get_engine().connect() as db:
        rows = listar_equipos(db, dept_id, solo_activos=False)
    result = []
    for r in rows:
        item = dict(r)
        item["activo_str"] = "Activo" if item.get("activo") else "Inactivo"
        item["estado"] = _estado_label(item.get("ultima_importacion"))
        item["ultima_importacion_str"] = str(item.get("ultima_importacion") or "—")[:10]
        item["usuario"] = item.get("notas") or "—"
        result.append(item)
    return result


HDRS_INV = ["Código", "Nombre", "Fabricante", "Versión", "Dispositivos", "Clasificación", "Guía 105"]
KEYS_INV = ["codigo", "nombre", "fabricante", "version_referencia", "dispositivos", "clasificacion_informacion", "en_guia_105_str"]

HDRS_DEV = ["Dispositivo", "Usuario", "Estado equipo", "Última import.", "Importación", "Software"]
KEYS_DEV = ["nombre", "usuario", "activo_str", "ultima_importacion_str", "estado", "total_software_activo"]


class DepartmentsPage(QWidget):
    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__()
        self.main_window = main_window
        self._dept: dict | None = None
        self._departamentos: list[dict] = []
        self._equipos: list[dict] = []
        self._selected_equipo_id = None
        self._thread = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(12)

        self._import_btn = QPushButton("Importar Panda")
        self._import_btn.clicked.connect(lambda: self.main_window.navigate_to("import"))
        header = PageHeader("Departamentos", "Inventario, dispositivos y exportación por área.")
        header.add_action(self._import_btn)
        layout.addWidget(header)

        sel_row = QHBoxLayout()
        sel_row.setSpacing(8)
        sel_row.addWidget(QLabel("Departamento:"))
        self._dept_combo = QComboBox()
        self._dept_combo.setMinimumWidth(220)
        self._dept_combo.currentIndexChanged.connect(self._on_dept_selected)
        sel_row.addWidget(self._dept_combo)
        self._dept_info = QLabel("")
        self._dept_info.setObjectName("labelMuted")
        sel_row.addWidget(self._dept_info)
        sel_row.addStretch()
        layout.addLayout(sel_row)

        self._feedback = FeedbackBar()
        layout.addWidget(self._feedback)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs, stretch=1)

        self._tabs.addTab(self._build_inv_tab(), "Inventario")
        self._tabs.addTab(self._build_devices_tab(), "Dispositivos")
        self._tabs.addTab(self._build_export_tab(), "Exportar")

    # ── Inventario ─────────────────────────────────────────────────
    def _build_inv_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(10)

        toolbar = FilterBar()
        self._inv_search = FilterBar.search_box("Buscar programa...")
        self._inv_search.textChanged.connect(lambda t: self._inv_table.filter(t))
        toolbar.add_widget(self._inv_search, stretch=1)
        self._equipo_filter = QComboBox()
        self._equipo_filter.setMinimumWidth(180)
        self._equipo_filter.addItem("Todos los dispositivos", None)
        self._equipo_filter.currentIndexChanged.connect(self._reload_inventario)
        toolbar.add_widget(self._equipo_filter)
        self._cleanup_btn = QPushButton("Ocultar huérfanos")
        self._cleanup_btn.setObjectName("subtle")
        self._cleanup_btn.clicked.connect(self._cleanup_orphans)
        toolbar.add_widget(self._cleanup_btn)
        layout.addWidget(toolbar)

        body = QHBoxLayout()
        body.setSpacing(12)
        self._inv_table = SortableTable(headers=HDRS_INV, keys=KEYS_INV, badge_keys=["en_guia_105_str"])
        self._inv_table.set_empty_content(
            title="Sin software", message="Este departamento no tiene software con dispositivos activos.", icon="🔎")
        self._inv_table.selection_changed.connect(self._on_inv_selection)
        body.addWidget(self._inv_table, stretch=1)
        self._inv_detail = DetailPanel()
        self._inv_detail.closed.connect(self._inv_table.clear_selection)
        body.addWidget(self._inv_detail)
        layout.addLayout(body, stretch=1)
        return tab

    def _on_inv_selection(self, row) -> None:
        if not row:
            self._inv_detail.clear()
            return
        self._inv_detail.show_details(
            row.get("nombre", ""),
            badges=[(row.get("en_guia_105_str", "Pendiente"), None)],
            rows=[
                ("Código", row.get("codigo")),
                ("Fabricante", row.get("fabricante")),
                ("Versión", row.get("version_referencia")),
                ("Dispositivos", row.get("dispositivos")),
                ("Clasificación", row.get("clasificacion_informacion")),
                ("Observaciones", row.get("observaciones")),
            ],
        )

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

    def _cleanup_orphans(self) -> None:
        if not self._dept:
            return
        if not confirm(self, "Ocultar software huérfano",
                       "Se ocultará el software activo sin dispositivos asignados.",
                       details="Es un soft-delete (activo = FALSE): no se borra el histórico.",
                       ok_text="Ocultar"):
            return
        try:
            from database.connection import get_engine
            from modules.software import ocultar_software_sin_dispositivos
            with get_engine().begin() as db:
                hidden = ocultar_software_sin_dispositivos(db, self._dept["id"])
            self._feedback.show_message(f"Registros ocultados: {hidden}", "success")
            self._reload_inventario()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))

    # ── Dispositivos ───────────────────────────────────────────────
    def _build_devices_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(10)

        top = QHBoxLayout()
        top.addStretch()
        self._new_equipo_btn = QPushButton("+ Nuevo dispositivo")
        self._new_equipo_btn.clicked.connect(self._show_new_equipo_dialog)
        top.addWidget(self._new_equipo_btn)
        layout.addLayout(top)

        body = QHBoxLayout()
        body.setSpacing(12)
        self._dev_table = SortableTable(headers=HDRS_DEV, keys=KEYS_DEV, badge_keys=["activo_str", "estado"])
        self._dev_table.set_empty_content(
            title="Sin dispositivos", message="Este departamento no tiene dispositivos. Crea uno nuevo.",
            icon="🖥", action_text="+ Nuevo dispositivo", on_action=self._show_new_equipo_dialog)
        self._dev_table.selection_changed.connect(self._on_dev_selected)
        body.addWidget(self._dev_table, stretch=1)
        self._dev_detail = DetailPanel()
        self._dev_detail.closed.connect(self._dev_table.clear_selection)
        body.addWidget(self._dev_detail)
        layout.addLayout(body, stretch=1)

        user_row = QHBoxLayout()
        user_row.addWidget(QLabel("Usuario del dispositivo:"))
        self._user_input = QLineEdit()
        user_row.addWidget(self._user_input, stretch=1)
        self._save_user_btn = QPushButton("Guardar usuario")
        self._save_user_btn.clicked.connect(self._save_user)
        user_row.addWidget(self._save_user_btn)
        layout.addLayout(user_row)
        return tab

    def _on_dev_selected(self, row) -> None:
        if not row:
            self._dev_detail.clear()
            self._selected_equipo_id = None
            return
        self._selected_equipo_id = row.get("id")
        from modules.equipos import alertas_equipo
        alerts = alertas_equipo(row)
        rows = [
            ("Sistema operativo", row.get("sistema_operativo")),
            ("Procesador", row.get("procesador")),
            ("RAM", row.get("ram")),
            ("Marca / Modelo", row.get("marca_modelo")),
            ("Nº de serie", row.get("num_serie")),
            ("Responsable", row.get("responsable")),
            ("Ubicación", row.get("ubicacion")),
            ("Software instalado", str(row.get("total_software_activo") or 0)),
        ]
        if alerts:
            rows.append(("Alertas", " · ".join(alerts)))
        self._dev_detail.show_details(
            row.get("nombre", ""),
            rows,
            badges=[(row.get("activo_str", "Activo"), None), (row.get("estado", ""), None)],
        )
        self._user_input.setText(row.get("notas") if row.get("notas") not in ("—", None) else "")

    def _save_user(self) -> None:
        if not self._selected_equipo_id:
            self._feedback.show_message("Selecciona un dispositivo primero.", "warning")
            return
        try:
            from database.connection import get_engine
            from modules.equipos import actualizar_usuario_dispositivo
            with get_engine().begin() as db:
                actualizar_usuario_dispositivo(db, self._selected_equipo_id, self._user_input.text().strip() or None)
            self._feedback.show_message("Usuario actualizado.", "success")
            self._load_devices()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))

    def _show_new_equipo_dialog(self) -> None:
        if not self._dept:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Nuevo dispositivo")
        dlg.setMinimumWidth(380)
        form = QFormLayout(dlg)
        name_input = QLineEdit()
        user_input = QLineEdit()
        form.addRow("Nombre:", name_input)
        form.addRow("Usuario:", user_input)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        name = name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Falta el nombre", "El nombre del dispositivo es obligatorio.")
            return
        try:
            from database.connection import get_engine
            from modules.equipos import crear_equipo, existe_equipo
            with get_engine().begin() as db:
                if existe_equipo(db, self._dept["id"], name):
                    QMessageBox.warning(self, "Duplicado", "Ya existe un dispositivo con ese nombre.")
                    return
                crear_equipo(db, self._dept["id"], name, user_input.text().strip() or None)
            self._feedback.show_message(f"Dispositivo «{name}» creado.", "success")
            self._load_devices()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))

    def _load_devices(self) -> None:
        if not self._dept:
            return
        run_in_thread(self, _fetch_dispositivos, self._dept["id"],
                      on_done=self._on_devices_loaded, on_error=self._show_error)

    def _on_devices_loaded(self, data: list[dict]) -> None:
        self._equipos = data
        self._dev_table.load_data(data)

    # ── Exportar ───────────────────────────────────────────────────
    def _build_export_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(10)
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
        return tab

    def _export_dept(self) -> None:
        if not self._dept:
            return
        try:
            from database.connection import get_engine
            from modules.exportacion import generar_excel
            with get_engine().connect() as db:
                data = generar_excel(db, [self._dept["id"]])
            self._save_file(data, f"inventario_{self._dept['codigo']}.xlsx", "Excel (*.xlsx)")
        except Exception as exc:  # noqa: BLE001
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
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))

    def _export_devices(self) -> None:
        if not self._equipos:
            self._feedback.show_message("No hay equipos cargados.", "warning")
            return
        try:
            from modules.equipos import exportar_equipos_excel
            dept_name = self._dept["nombre"] if self._dept else "Equipos"
            data = exportar_equipos_excel(self._equipos, dept_name)
            safe = "".join(c if c.isalnum() else "_" for c in dept_name)
            self._save_file(data, f"Equipos_{safe}_{date.today().isoformat()}.xlsx", "Excel (*.xlsx)")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))

    def _save_file(self, data: bytes, default_name: str, file_filter: str) -> None:
        from PySide6.QtWidgets import QFileDialog
        filename, _ = QFileDialog.getSaveFileName(self, "Guardar archivo", default_name, file_filter)
        if filename:
            with open(filename, "wb") as f:
                f.write(data)
            self._feedback.show_message(f"Archivo guardado en {filename}.", "success")

    # ── Activación ─────────────────────────────────────────────────
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
        self._select_current_dept()

    def _on_dept_selected(self) -> None:
        self._select_current_dept()

    def _select_current_dept(self) -> None:
        dept_id = self._dept_combo.currentData()
        if not dept_id:
            return
        self._dept = next((d for d in self._departamentos if d["id"] == dept_id), None)
        if self._dept:
            self._dept_info.setText(
                f"{self._dept.get('n_equipos', 0)} dispositivos · {self._dept.get('n_software', 0)} software"
            )
        self._reload_inventario()
        self._load_devices()

    def _show_error(self, msg: str) -> None:
        self._feedback.show_message(f"Error: {msg}", "error")
