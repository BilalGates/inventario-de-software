from __future__ import annotations

import re
from datetime import date
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from modules.simple_inventory import current_period
from ui.components.confirm_dialog import confirm
from ui.components.department_card import DepartmentCard
from ui.components.device_dialog import DeviceEditDialog
from ui.components.detail_panel import DetailPanel
from ui.components.sortable_table import SortableTable
from ui.components.ui_kit import FeedbackBar, PageHeader, SectionCard
from ui.components.worker import run_in_thread
from ui.pages.import_panda import ImportPandaPage
from ui.tokens import SPACING

if TYPE_CHECKING:
    from ui.main_window import MainWindow


DEVICE_HEADERS = ["Equipo", "Usuario", "Sistema operativo", "Tipo", "Estado", "Programas"]
DEVICE_KEYS = ["nombre", "usuario", "sistema_operativo", "tipo_label", "estado_importacion", "n_programas"]
SOFTWARE_HEADERS = ["Programa", "Editor/Fabricante", "Versiones", "N equipos", "Equipos"]
SOFTWARE_KEYS = ["nombre", "fabricantes", "versiones", "n_equipos", "equipos"]


def _natural_key(value: object) -> list[tuple[int, object]]:
    parts = re.split(r"(\d+)", str(value or "").casefold())
    key: list[tuple[int, object]] = []
    for part in parts:
        if not part:
            continue
        key.append((0, int(part)) if part.isdigit() else (1, part))
    return key


def _with_search_text(item: dict) -> dict:
    item["_search_text"] = " ".join(str(value or "") for value in item.values()).casefold()
    return item


def _format_device_rows(equipos: list[dict], estado_por_equipo: dict[int, dict]) -> list[dict]:
    device_rows = []
    for row in equipos:
        item = dict(row)
        monthly = estado_por_equipo.get(int(item["id"]), {})
        item["usuario"] = item.get("notas") or item.get("responsable") or ""
        item["estado_importacion"] = monthly.get("estado_importacion") or ("Activo" if item.get("activo") else "Inactivo")
        item["fecha_importacion_str"] = monthly.get("fecha_importacion_str") or ""
        item["n_programas"] = monthly.get("n_programas") or 0
        item["tipo_label"] = "Servidor" if item.get("es_servidor") else item.get("tipo_dispositivo") or "Equipo"
        device_rows.append(_with_search_text(item))
    device_rows.sort(key=lambda item: _natural_key(item.get("nombre")))
    return device_rows


def _format_software_rows(software: list[dict]) -> list[dict]:
    software_rows = []
    for row in software:
        software_rows.append(_with_search_text(dict(row)))
    software_rows.sort(key=lambda item: _natural_key(item.get("nombre")))
    return software_rows


def _fetch_inventory(periodo: str, departamento_id: int | None):
    from database.connection import get_engine
    from modules.equipos import listar_equipos
    from modules.simple_inventory import (
        dashboard_simple,
        equipos_estado_mensual,
        resumen_departamentos,
        software_por_departamento,
        validate_periodo,
    )
    from modules.software import listar_departamentos

    periodo = validate_periodo(periodo)
    with get_engine().connect() as db:
        departamentos = listar_departamentos(db)
        selected = departamento_id
        metricas = dashboard_simple(periodo, db=db)
        resumen = resumen_departamentos(periodo, db=db)
        todos_equipos = listar_equipos(db, solo_activos=False)
        estados_globales: dict[int, dict] = {}
        software_global = []
        for dept in departamentos:
            dept_id = int(dept["id"])
            for estado in equipos_estado_mensual(periodo, dept_id, db=db, solo_activos=False):
                estados_globales[int(estado["id"])] = estado
            for item in software_por_departamento(periodo, dept_id, db=db):
                software_item = dict(item)
                software_item["departamento_id"] = dept_id
                software_item["departamento"] = dept["nombre"]
                software_global.append(software_item)
        equipos = listar_equipos(db, departamento_id=selected, solo_activos=False) if selected else []
        software = [row for row in software_global if row["departamento_id"] == selected] if selected else []

    device_rows = _format_device_rows(equipos, estados_globales)
    software_rows = _format_software_rows(software)
    all_device_rows = _format_device_rows(todos_equipos, estados_globales)
    all_software_rows = _format_software_rows(software_global)

    inactive_by_dept: dict[int, int] = {}
    for row in todos_equipos:
        if not row.get("activo"):
            dept_id = int(row["departamento_id"])
            inactive_by_dept[dept_id] = inactive_by_dept.get(dept_id, 0) + 1

    return {
        "periodo": periodo,
        "metricas": metricas,
        "departamentos": departamentos,
        "selected": selected,
        "resumen": resumen,
        "inactive_by_dept": inactive_by_dept,
        "equipos": device_rows,
        "software": software_rows,
        "equipos_globales": all_device_rows,
        "software_global": all_software_rows,
    }


def _export_excel(periodo: str) -> bytes:
    from modules.simple_inventory import exportar_inventario_excel

    return exportar_inventario_excel(periodo)


class SoftwareEditDialog(QDialog):
    def __init__(self, parent: QWidget, software: dict | None = None, title: str = "Software") -> None:
        super().__init__(parent)
        self._software = software or {}
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING["xl"], SPACING["lg"], SPACING["xl"], SPACING["lg"])
        layout.setSpacing(SPACING["md"])

        heading = QLabel(title)
        heading.setObjectName("labelSection")
        layout.addWidget(heading)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setHorizontalSpacing(SPACING["lg"])
        form.setVerticalSpacing(SPACING["sm"])

        self._nombre = QLineEdit(str(self._software.get("nombre") or ""))
        self._fabricante = QLineEdit(str(self._software.get("fabricantes") or self._software.get("fabricante") or ""))
        self._version = QLineEdit(str(self._software.get("versiones") or self._software.get("version") or ""))
        self._tamano = QLineEdit(str(self._software.get("tamano") or ""))

        form.addRow("Programa", self._nombre)
        form.addRow("Editor/Fabricante", self._fabricante)
        form.addRow("Version", self._version)
        form.addRow("Tamano", self._tamano)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        save_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        save_btn.setText("Guardar")
        save_btn.setObjectName("primary")
        cancel_btn.setText("Cancelar")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept_if_valid(self) -> None:
        if not self._nombre.text().strip():
            QMessageBox.warning(self, "Dato obligatorio", "El nombre del programa es obligatorio.")
            return
        self.accept()

    def values(self) -> dict:
        return {
            "nombre": self._nombre.text().strip(),
            "fabricante": self._fabricante.text().strip() or None,
            "version": self._version.text().strip() or None,
            "tamano": self._tamano.text().strip() or None,
        }


class SoftwareDevicesDialog(QDialog):
    def __init__(self, parent: QWidget, software_name: str, devices: list[dict], selected_ids: set[int]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Dispositivos instalados")
        self.setModal(True)
        self.setMinimumWidth(520)
        self._checks: list[tuple[int, QCheckBox]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING["xl"], SPACING["lg"], SPACING["xl"], SPACING["lg"])
        layout.setSpacing(SPACING["md"])

        heading = QLabel(software_name)
        heading.setObjectName("labelSection")
        layout.addWidget(heading)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        list_layout = QVBoxLayout(content)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(SPACING["xs"])
        for device in devices:
            label = device.get("nombre") or f"Equipo {device.get('id')}"
            user = device.get("usuario")
            if user:
                label = f"{label} Â· {user}"
            check = QCheckBox(label)
            check.setChecked(int(device["id"]) in selected_ids)
            self._checks.append((int(device["id"]), check))
            list_layout.addWidget(check)
        list_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, stretch=1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        save_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        save_btn.setText("Guardar")
        save_btn.setObjectName("primary")
        cancel_btn.setText("Cancelar")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_ids(self) -> list[int]:
        return [device_id for device_id, check in self._checks if check.isChecked()]


class InventoryPage(QWidget):
    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__()
        self.main_window = main_window
        self._periodo = current_period()
        self._departamentos: list[dict] = []
        self._summary_rows: list[dict] = []
        self._metricas: dict = {}
        self._inactive_by_dept: dict[int, int] = {}
        self._device_rows: list[dict] = []
        self._software_rows: list[dict] = []
        self._all_device_rows: list[dict] = []
        self._all_software_rows: list[dict] = []
        self._filtered_devices: list[dict] = []
        self._filtered_software: list[dict] = []
        self._cards: dict[int, DepartmentCard] = {}
        self._selected_department_id: int | None = None
        self._global_query = ""
        self._syncing_import_tab = False
        self._thread = None
        self._pending_export_path: str | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        self._import_devices_btn = QPushButton("Importar equipos")
        self._import_devices_btn.clicked.connect(self._import_devices)
        self._export_btn = QPushButton("Exportar Excel")
        self._export_btn.setObjectName("primary")
        self._export_btn.clicked.connect(self._export_all)
        self._refresh_btn = QPushButton("Actualizar")
        self._refresh_btn.clicked.connect(self._load_data)

        header = PageHeader("Inventario", "Equipos y software mensual en una sola vista.")
        for button in (self._import_devices_btn, self._export_btn, self._refresh_btn):
            header.add_action(button)
        layout.addWidget(header)

        self._feedback = FeedbackBar()
        layout.addWidget(self._feedback)

        self._cards_host = QWidget()
        self._cards_grid = QGridLayout(self._cards_host)
        self._cards_grid.setContentsMargins(0, 0, 0, 0)
        self._cards_grid.setSpacing(SPACING["md"])
        layout.addWidget(self._cards_host)

        self._status = QLabel("")
        self._status.setObjectName("labelMuted")
        layout.addWidget(self._status)

        inventory_card = SectionCard()
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_devices_tab(), "Dispositivos")
        self._tabs.addTab(self._build_software_tab(), "Software")
        self._tabs.addTab(self._build_import_tab(), "Importar software")
        self._tabs.currentChanged.connect(self._on_tab_changed)
        inventory_card.add_widget(self._tabs, stretch=1)
        layout.addWidget(inventory_card, stretch=1)

    def _build_devices_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("InventoryTab")
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._device_table = SortableTable(headers=DEVICE_HEADERS, keys=DEVICE_KEYS, badge_keys=["estado_importacion"])
        self._device_table.view().setObjectName("InventoryTable")
        self._device_table.set_empty_content(
            title="Sin dispositivos",
            message="No hay equipos para este departamento o filtro.",
            icon="",
        )
        self._device_table.set_context_menu_handler(self._device_context_menu)
        self._device_table.selection_changed.connect(self._show_device_details)
        self._device_detail = DetailPanel(width=330)
        self._device_detail.closed.connect(self._device_table.clear_selection)
        layout.addWidget(self._device_table, stretch=1)
        layout.addWidget(self._device_detail)
        return tab

    def _build_software_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("InventoryTab")
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._software_table = SortableTable(headers=SOFTWARE_HEADERS, keys=SOFTWARE_KEYS)
        self._software_table.view().setObjectName("InventoryTable")
        self._software_table.set_empty_content(
            title="Sin software",
            message="Importa software de algun equipo o ajusta el periodo.",
            icon="",
        )
        self._software_table.set_context_menu_handler(self._software_context_menu)
        self._software_table.selection_changed.connect(self._show_software_details)
        self._software_detail = DetailPanel(width=350)
        self._software_detail.closed.connect(self._software_table.clear_selection)
        layout.addWidget(self._software_table, stretch=1)
        layout.addWidget(self._software_detail)
        return tab

    def _build_import_tab(self) -> QWidget:
        self._import_page = ImportPandaPage(self.main_window, embedded=True)
        self._import_page.setObjectName("InventoryTab")
        self._import_page.import_saved.connect(self._on_import_saved)
        return self._import_page

    def on_activate(self) -> None:
        self._load_data()

    def apply_navigation(self, payload: dict) -> None:
        open_import = payload.get("tab") == "import" or payload.get("equipo_id") is not None
        if payload.get("periodo"):
            self._periodo = str(payload["periodo"])
        if payload.get("departamento_id") is not None:
            self._selected_department_id = int(payload["departamento_id"])
        if open_import:
            self._syncing_import_tab = True
            self._import_page.apply_navigation({**payload, "periodo": self._periodo})
            self._tabs.setCurrentWidget(self._import_page)
            self._syncing_import_tab = False
        self._load_data()

    def set_period(self, periodo: str) -> None:
        if periodo == self._periodo:
            return
        self._periodo = periodo
        self._import_page.set_period(periodo)
        self._load_data()

    def set_global_search(self, text_value: str) -> None:
        self._global_query = (text_value or "").strip().casefold()
        if self._global_query and self._tabs.currentWidget() is self._import_page:
            self._tabs.setCurrentIndex(0)
        self._apply_filter()
        if self._global_query:
            if self._tabs.currentIndex() == 0 and not self._filtered_devices and self._filtered_software:
                self._tabs.setCurrentIndex(1)
            elif self._tabs.currentIndex() == 1 and not self._filtered_software and self._filtered_devices:
                self._tabs.setCurrentIndex(0)

    def _load_data(self) -> None:
        self._feedback.show_message("Cargando inventario...", "info")
        self._thread = run_in_thread(
            self,
            _fetch_inventory,
            self._periodo,
            self._selected_department_id,
            on_done=self._on_loaded,
            on_error=self._on_error,
        )

    def _on_loaded(self, payload: dict) -> None:
        self._periodo = payload["periodo"]
        self._metricas = payload["metricas"]
        self._departamentos = payload["departamentos"]
        self._selected_department_id = payload["selected"]
        self._summary_rows = payload["resumen"]
        self._inactive_by_dept = payload["inactive_by_dept"]
        self._device_rows = payload["equipos"]
        self._software_rows = payload["software"]
        self._all_device_rows = payload["equipos_globales"]
        self._all_software_rows = payload["software_global"]
        self._render_department_cards()
        self._apply_filter()
        self._feedback.clear()

    def _render_department_cards(self) -> None:
        self._clear_layout(self._cards_grid)
        self._cards = {}
        summary = {row["id"]: row for row in self._summary_rows}
        for index, dept in enumerate(self._departamentos):
            dept_id = int(dept["id"])
            item = summary.get(dept_id, {})
            card = DepartmentCard(dept_id)
            card.update_content(
                dept["nombre"],
                int(item.get("equipos") or 0),
                self._inactive_by_dept.get(dept_id, 0),
                int(item.get("importados") or 0),
                int(item.get("software") or 0),
            )
            card.clicked.connect(self._select_department)
            card.set_selected(dept_id == self._selected_department_id)
            self._cards[dept_id] = card
            self._cards_grid.addWidget(card, index // 3, index % 3)
        self._apply_department_card_filter()

    def _select_department(self, departamento_id: int) -> None:
        if departamento_id == self._selected_department_id:
            self._selected_department_id = None
        else:
            self._selected_department_id = departamento_id
        for dept_id, card in self._cards.items():
            card.set_selected(dept_id == self._selected_department_id)
        if self._tabs.currentWidget() is self._import_page:
            self._sync_import_tab_context()
        self._load_data()

    def _on_tab_changed(self, _index: int) -> None:
        if self._syncing_import_tab:
            return
        if self._tabs.currentWidget() is self._import_page:
            self._sync_import_tab_context()

    def _sync_import_tab_context(self) -> None:
        payload = {"periodo": self._periodo}
        if self._selected_department_id is not None:
            payload["departamento_id"] = self._selected_department_id
        self._import_page.apply_navigation(payload)

    def _apply_filter(self) -> None:
        query = self._global_query
        global_search = bool(query)
        device_source = self._all_device_rows if global_search else self._device_rows
        software_source = self._all_software_rows if global_search else self._software_rows
        self._filtered_devices = [
            row for row in device_source if not query or query in row.get("_search_text", "")
        ]
        self._filtered_software = [
            row for row in software_source if not query or query in row.get("_search_text", "")
        ]
        self._apply_department_card_filter()
        if query:
            self._device_table.set_empty_message("No hay dispositivos en la busqueda global.")
            self._software_table.set_empty_message("No hay software en la busqueda global.")
        elif self._selected_department_id is None:
            self._device_table.set_empty_message("Selecciona un departamento para ver sus dispositivos.")
            self._software_table.set_empty_message("Selecciona un departamento para ver su software mensual.")
        else:
            self._device_table.set_empty_message("No hay equipos para este departamento o filtro.")
            self._software_table.set_empty_message("No hay software para este departamento o filtro.")
        self._device_detail.clear()
        self._software_detail.clear()
        self._device_table.load_data(self._filtered_devices)
        self._software_table.load_data(self._filtered_software)
        if query:
            self._status.setText(
                f"Busqueda global - {len(self._filtered_devices)} dispositivos - "
                f"{len(self._filtered_software)} programas - {self._periodo}"
            )
        elif self._selected_department_id is None:
            self._status.setText(f"Sin departamento seleccionado - {self._periodo}")
        else:
            self._status.setText(
                f"{self._selected_department_name()} - {len(self._filtered_devices)} dispositivos - "
                f"{len(self._filtered_software)} programas - {self._periodo}"
            )
        self.main_window.set_status(self._status.text())

    def _apply_department_card_filter(self) -> None:
        query = self._global_query
        summary = {int(row["id"]): row for row in self._summary_rows}
        for dept in self._departamentos:
            dept_id = int(dept["id"])
            card = self._cards.get(dept_id)
            if not card:
                continue
            item = summary.get(dept_id, {})
            search_text = " ".join(
                [
                    str(dept.get("nombre") or ""),
                    str(item.get("equipos") or ""),
                    str(item.get("importados") or ""),
                    str(item.get("software") or ""),
                ]
            ).casefold()
            card.setVisible(not query or query in search_text)

    def _show_device_details(self, row: dict | None) -> None:
        if not row:
            self._device_detail.clear()
            return
        self._device_detail.show_details(
            str(row.get("nombre") or "Dispositivo"),
            [
                ("Departamento", row.get("departamento_nombre") or self._selected_department_name()),
                ("Usuario", row.get("usuario") or row.get("responsable")),
                ("Estado mensual", row.get("estado_importacion")),
                ("Tipo", row.get("tipo_label")),
                ("Sistema operativo", row.get("sistema_operativo")),
                ("Programas este mes", str(row.get("n_programas") or 0)),
                ("Ultima importacion", row.get("fecha_importacion_str")),
                ("Marca / modelo", row.get("marca_modelo")),
                ("Procesador", row.get("procesador")),
                ("RAM", row.get("ram")),
                ("Almacenamiento", row.get("almacenamiento")),
                ("Serie", row.get("num_serie")),
                ("MAC", row.get("mac_address")),
                ("Ubicacion", row.get("ubicacion")),
            ],
            badges=[
                (str(row.get("estado_importacion") or ""), None),
                (str(row.get("tipo_label") or ""), "neutral"),
            ],
        )

    def _show_software_details(self, row: dict | None) -> None:
        if not row:
            self._software_detail.clear()
            return
        n_equipos = int(row.get("n_equipos") or 0)
        self._software_detail.show_details(
            str(row.get("nombre") or "Software"),
            [
                ("Departamento", self._selected_department_name()),
                ("Editor/Fabricante", row.get("fabricantes")),
                ("Versiones", row.get("versiones")),
                ("Equipos", row.get("equipos")),
                ("Numero de equipos", str(n_equipos)),
            ],
            badges=[(f"{n_equipos} equipo{'s' if n_equipos != 1 else ''}", "info")],
        )

    def _device_context_menu(self, row: dict, global_pos) -> bool:
        menu = QMenu(self)
        edit_action = menu.addAction("Editar dispositivo")
        new_action = menu.addAction("Nuevo dispositivo")
        import_action = menu.addAction("Importar software en este equipo")
        add_software_action = menu.addAction("Anadir software a este equipo")
        menu.addSeparator()
        active = bool(row.get("activo"))
        state_action = menu.addAction("Dar de baja" if active else "Reactivar")
        delete_action = None
        if not active:
            delete_action = menu.addAction("Eliminar definitivo")
        action = menu.exec(global_pos)
        if action == edit_action:
            self._edit_device(row)
        elif action == new_action:
            self._add_device()
        elif action == import_action:
            self.main_window.navigate_to(
                "import",
                {
                    "tab": "import",
                    "departamento_id": row.get("departamento_id"),
                    "equipo_id": row.get("id"),
                    "periodo": self._periodo,
                },
            )
        elif action == add_software_action:
            self._add_software({int(row["id"])}, departamento_id=int(row["departamento_id"]))
        elif action == state_action:
            self._toggle_device_state(row)
        elif delete_action is not None and action == delete_action:
            self._delete_device(row)
        return True

    def _software_context_menu(self, row: dict, global_pos) -> bool:
        menu = QMenu(self)
        edit_action = menu.addAction("Editar software")
        devices_action = menu.addAction("Cambiar dispositivos instalados")
        add_action = menu.addAction("Anadir software")
        menu.addSeparator()
        delete_action = menu.addAction("Eliminar del periodo")
        action = menu.exec(global_pos)
        if action == edit_action:
            self._edit_software(row)
        elif action == devices_action:
            self._change_software_devices(row)
        elif action == add_action:
            self._add_software(departamento_id=self._department_id_for_row(row))
        elif action == delete_action:
            self._delete_software(row)
        return True

    def _add_device(self) -> None:
        if not self._departamentos:
            self._feedback.show_message("No hay departamentos para asignar equipos.", "warning")
            return
        dialog = DeviceEditDialog(self, self._departamentos)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            from database.connection import get_engine
            from modules.equipos import crear_equipo_detallado

            with get_engine().begin() as db:
                crear_equipo_detallado(db, dialog.values())
            self._feedback.show_message("Dispositivo creado.", "success")
            self._load_data()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"No se pudo crear el dispositivo:\n{exc}")

    def _edit_device(self, row: dict) -> None:
        dialog = DeviceEditDialog(self, self._departamentos, row)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            from database.connection import get_engine
            from modules.equipos import actualizar_equipo

            with get_engine().begin() as db:
                actualizar_equipo(db, int(row["id"]), dialog.values())
            self._feedback.show_message("Dispositivo actualizado.", "success")
            self._load_data()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"No se pudo actualizar el dispositivo:\n{exc}")

    def _toggle_device_state(self, row: dict) -> None:
        active = bool(row.get("activo"))
        title = "Dar de baja dispositivo" if active else "Reactivar dispositivo"
        message = (
            f"{row.get('nombre')} pasara a inactivo. No se borran importaciones ni historico."
            if active
            else f"{row.get('nombre')} volvera al listado de equipos activos."
        )
        ok_text = "Dar de baja" if active else "Reactivar"
        if not confirm(self, title, message, ok_text=ok_text, danger=active):
            return
        try:
            from database.connection import get_engine
            from modules.equipos import dar_baja_equipo, reactivar_equipo

            with get_engine().begin() as db:
                if active:
                    dar_baja_equipo(db, int(row["id"]))
                else:
                    reactivar_equipo(db, int(row["id"]))
            self._feedback.show_message("Estado del dispositivo actualizado.", "success")
            self._load_data()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"No se pudo cambiar el estado:\n{exc}")

    def _delete_device(self, row: dict) -> None:
        if row.get("activo"):
            self._feedback.show_message("Primero da de baja el dispositivo; despues podras eliminarlo.", "warning")
            return
        if not confirm(
            self,
            "Eliminar dispositivo",
            f"{row.get('nombre')} se eliminara definitivamente del inventario.",
            details="Se borraran tambien sus relaciones de software e importaciones asociadas.",
            ok_text="Eliminar",
            danger=True,
        ):
            return
        try:
            from database.connection import get_engine
            from modules.equipos import eliminar_equipo_definitivo

            with get_engine().begin() as db:
                eliminar_equipo_definitivo(db, int(row["id"]))
            self._feedback.show_message("Dispositivo eliminado.", "success")
            self._load_data()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"No se pudo eliminar el dispositivo:\n{exc}")

    def _edit_software(self, row: dict) -> None:
        departamento_id = self._department_id_for_row(row)
        if departamento_id is None:
            return
        dialog = SoftwareEditDialog(self, row, "Editar software")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            from database.connection import get_engine
            from modules.simple_inventory import actualizar_software_mensual

            with get_engine().begin() as db:
                actualizar_software_mensual(
                    self._periodo,
                    departamento_id,
                    row["nombre_norm"],
                    dialog.values(),
                    db=db,
                )
            self._feedback.show_message("Software actualizado.", "success")
            self._load_data()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"No se pudo actualizar el software:\n{exc}")

    def _add_software(self, selected_ids: set[int] | None = None, departamento_id: int | None = None) -> None:
        departamento_id = departamento_id or self._department_id_for_row()
        if departamento_id is None:
            return
        dialog = SoftwareEditDialog(self, None, "Anadir software")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        devices_dialog = SoftwareDevicesDialog(
            self,
            dialog.values()["nombre"],
            self._active_devices(departamento_id),
            selected_ids or set(),
        )
        if devices_dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if not devices_dialog.selected_ids():
            self._feedback.show_message("Selecciona al menos un dispositivo.", "warning")
            return
        try:
            from database.connection import get_engine
            from modules.simple_inventory import set_software_dispositivos_mensual

            with get_engine().begin() as db:
                set_software_dispositivos_mensual(
                    self._periodo,
                    departamento_id,
                    None,
                    dialog.values(),
                    devices_dialog.selected_ids(),
                    db=db,
                )
            self._feedback.show_message("Software anadido al periodo.", "success")
            self._load_data()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"No se pudo anadir el software:\n{exc}")

    def _change_software_devices(self, row: dict) -> None:
        departamento_id = self._department_id_for_row(row)
        if departamento_id is None:
            return
        try:
            from database.connection import get_engine
            from modules.simple_inventory import software_dispositivos_mensual

            with get_engine().connect() as db:
                devices = software_dispositivos_mensual(
                    self._periodo,
                    departamento_id,
                    row["nombre_norm"],
                    db=db,
                )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"No se pudieron cargar los dispositivos:\n{exc}")
            return

        selected = {int(device["id"]) for device in devices if device.get("instalado")}
        dialog = SoftwareDevicesDialog(self, row.get("nombre", ""), devices, selected)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            from database.connection import get_engine
            from modules.simple_inventory import set_software_dispositivos_mensual

            with get_engine().begin() as db:
                set_software_dispositivos_mensual(
                    self._periodo,
                    departamento_id,
                    row["nombre_norm"],
                    {
                        "nombre": row.get("nombre"),
                        "fabricante": row.get("fabricantes"),
                        "version": row.get("versiones"),
                    },
                    dialog.selected_ids(),
                    db=db,
                )
            self._feedback.show_message("Dispositivos del software actualizados.", "success")
            self._load_data()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"No se pudieron actualizar los dispositivos:\n{exc}")

    def _delete_software(self, row: dict) -> None:
        departamento_id = self._department_id_for_row(row)
        if departamento_id is None:
            return
        if not confirm(
            self,
            "Eliminar software",
            f"{row.get('nombre')} se eliminara del periodo {self._periodo} en este departamento.",
            ok_text="Eliminar",
            danger=True,
        ):
            return
        try:
            from database.connection import get_engine
            from modules.simple_inventory import eliminar_software_mensual

            with get_engine().begin() as db:
                eliminar_software_mensual(
                    self._periodo,
                    departamento_id,
                    row["nombre_norm"],
                    db=db,
                )
            self._feedback.show_message("Software eliminado del periodo.", "success")
            self._load_data()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"No se pudo eliminar el software:\n{exc}")

    def _on_import_saved(self, _importacion_id: int) -> None:
        self._feedback.show_message("Importacion guardada. Inventario actualizado.", "success")
        self._load_data()

    def _department_id_for_row(self, row: dict | None = None) -> int | None:
        departamento_id = row.get("departamento_id") if row else self._selected_department_id
        if departamento_id is None:
            self._feedback.show_message("Selecciona un departamento primero.", "warning")
            return None
        return int(departamento_id)

    def _active_devices(self, departamento_id: int | None = None) -> list[dict]:
        source = self._all_device_rows if departamento_id is not None else self._device_rows
        return [
            row
            for row in source
            if row.get("activo") and (departamento_id is None or int(row["departamento_id"]) == departamento_id)
        ]

    def _import_devices(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Importar equipos", "", "Excel/CSV (*.xlsx *.csv)")
        if not path:
            return
        try:
            from database.connection import get_engine
            from modules.equipos import importar_equipos_desde_lista
            from modules.software import listar_departamentos
            from utils.parser import parse_equipos_file

            with open(path, "rb") as f:
                equipos_data = parse_equipos_file(f.read(), path)
            with get_engine().begin() as db:
                result = importar_equipos_desde_lista(db, equipos_data, listar_departamentos(db))
            self._feedback.show_message(f"Equipos importados: {result}", "success")
            self._load_data()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"No se pudo importar:\n{exc}")

    def _export_all(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar inventario",
            f"Inventario_Asserta_{self._periodo}_{date.today().isoformat()}.xlsx",
            "Excel (*.xlsx)",
        )
        if not filename:
            return
        self._pending_export_path = filename
        self._export_btn.setEnabled(False)
        self._feedback.show_message("Generando Excel...", "info")
        self._thread = run_in_thread(self, _export_excel, self._periodo, on_done=self._on_export_ready, on_error=self._on_error)

    def _on_export_ready(self, data: bytes) -> None:
        self._export_btn.setEnabled(True)
        path = self._pending_export_path
        self._pending_export_path = None
        if not path:
            return
        try:
            with open(path, "wb") as f:
                f.write(data)
            self._feedback.show_message(f"Excel guardado en {path}.", "success")
        except OSError as exc:
            QMessageBox.critical(self, "Error", f"No se pudo guardar:\n{exc}")

    def _selected_department_name(self) -> str:
        for dept in self._departamentos:
            if dept["id"] == self._selected_department_id:
                return dept["nombre"]
        return "Sin departamento"

    def _on_error(self, msg: str) -> None:
        self._export_btn.setEnabled(True)
        self._feedback.show_message(f"Error: {msg}", "error")

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                InventoryPage._clear_layout(child_layout)
