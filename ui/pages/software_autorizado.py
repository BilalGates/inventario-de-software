"""
Software autorizado: autorizado actual (general/específico), exclusivos pendientes
de autorizar y sugerencias de promoción a autorización general.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ui.components.confirm_dialog import confirm
from ui.components.sortable_table import SortableTable
from ui.components.ui_kit import FeedbackBar, PageHeader
from ui.components.worker import run_in_thread

if TYPE_CHECKING:
    from ui.main_window import MainWindow


def _fetch_autorizado():
    from database.connection import get_engine
    from modules.autorizado import (
        detectar_autorizados_para_promocion,
        detectar_software_exclusivo,
        listar_autorizado_agrupado,
    )
    with get_engine().connect() as db:
        grupos = listar_autorizado_agrupado(db)
        exclusivos = detectar_software_exclusivo(db)
        promociones = detectar_autorizados_para_promocion(db)
    return grupos, exclusivos, promociones


class SoftwareAutorizadoPage(QWidget):
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
            "Software autorizado",
            "Excepciones aprobadas, software exclusivo por autorizar y sugerencias de promoción.",
        )
        header.add_action(self._refresh_btn)
        layout.addWidget(header)

        self._feedback = FeedbackBar()
        layout.addWidget(self._feedback)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs, stretch=1)

        # --- Tab 1: autorizado actual ---------------------------------
        tab_auth = QWidget()
        l1 = QVBoxLayout(tab_auth)
        l1.setContentsMargins(0, 12, 0, 0)
        l1.setSpacing(10)
        self._auth_table = SortableTable(
            headers=["Nombre", "Fabricante", "Versiones", "Ámbito (equipo/usuario)", "Dispositivos", "Tipo"],
            keys=["nombre", "fabricante", "versiones", "ambito", "dispositivos", "tipo"],
            badge_keys=["tipo"],
        )
        self._auth_table.set_empty_content(
            title="Sin software autorizado",
            message="Aún no hay excepciones aprobadas. Autoriza software exclusivo desde la pestaña siguiente.",
            icon="🛡",
        )
        l1.addWidget(self._auth_table, stretch=1)
        revoke_row = QHBoxLayout()
        self._revoke_btn = QPushButton("Revocar autorización")
        self._revoke_btn.setObjectName("danger")
        self._revoke_btn.clicked.connect(self._revoke_selected)
        revoke_row.addWidget(self._revoke_btn)
        revoke_row.addStretch()
        l1.addLayout(revoke_row)
        self._tabs.addTab(tab_auth, "Autorizado")

        # --- Tab 2: exclusivos pendientes -----------------------------
        tab_excl = QWidget()
        l2 = QVBoxLayout(tab_excl)
        l2.setContentsMargins(0, 12, 0, 0)
        l2.setSpacing(10)
        self._excl_table = SortableTable(
            headers=["Software", "Versión", "Fabricante", "Equipo"],
            keys=["nombre", "version_referencia", "fabricante", "equipo"],
        )
        self._excl_table.set_empty_content(
            title="Nada que autorizar",
            message="No hay software instalado en un único equipo pendiente de autorizar.",
            icon="✓",
        )
        l2.addWidget(self._excl_table, stretch=1)
        excl_row = QHBoxLayout()
        self._auth_sel_btn = QPushButton("Autorizar seleccionado")
        self._auth_sel_btn.setObjectName("primary")
        self._auth_sel_btn.clicked.connect(self._authorize_selected)
        excl_row.addWidget(self._auth_sel_btn)
        self._auth_all_btn = QPushButton("Autorizar todos los exclusivos")
        self._auth_all_btn.clicked.connect(self._authorize_all)
        excl_row.addWidget(self._auth_all_btn)
        excl_row.addStretch()
        l2.addLayout(excl_row)
        self._tabs.addTab(tab_excl, "Exclusivos por autorizar")

        # --- Tab 3: sugerencias de promoción --------------------------
        tab_promo = QWidget()
        l3 = QVBoxLayout(tab_promo)
        l3.setContentsMargins(0, 12, 0, 0)
        l3.setSpacing(10)
        self._promo_table = SortableTable(
            headers=["Software", "Versión", "Departamento", "Equipos", "Dispositivos"],
            keys=["nombre", "version_referencia", "departamento", "equipos", "n_equipos"],
        )
        self._promo_table.set_empty_content(
            title="Sin sugerencias",
            message="No hay autorizaciones específicas que convenga promover a generales.",
            icon="↗",
        )
        l3.addWidget(self._promo_table, stretch=1)
        promo_row = QHBoxLayout()
        self._promo_btn = QPushButton("Promover a autorización general")
        self._promo_btn.setObjectName("primary")
        self._promo_btn.clicked.connect(self._promote_selected)
        promo_row.addWidget(self._promo_btn)
        promo_row.addStretch()
        l3.addLayout(promo_row)
        self._tabs.addTab(tab_promo, "Sugerencias de promoción")

    # ------------------------------------------------------------------
    def on_activate(self) -> None:
        self._load_data()

    def _load_data(self) -> None:
        self._feedback.show_message("Cargando software autorizado...", "info")
        self._thread = run_in_thread(self, _fetch_autorizado, on_done=self._on_loaded, on_error=self._on_error)

    def _on_loaded(self, result) -> None:
        grupos, exclusivos, promociones = result
        auth_rows = []
        for g in grupos:
            n = g.get("n_dispositivos", 0)
            auth_rows.append({
                "grupo": g.get("grupo"),
                "nombre": g.get("nombre") or "",
                "fabricante": g.get("fabricantes") or "",
                "versiones": g.get("versiones") or "",
                "ambito": g.get("equipos_usuarios") or "—",
                "dispositivos": str(n),
                "tipo": "General" if n >= 2 else "Específico",
            })
        self._auth_table.load_data(auth_rows)

        for r in exclusivos:
            r["version_referencia"] = str(r.get("version_referencia") or "")
        self._excl_table.load_data([dict(r) for r in exclusivos])

        for r in promociones:
            r["version_referencia"] = str(r.get("version_referencia") or "")
            r["n_equipos"] = str(r.get("n_equipos") or "")
        self._promo_table.load_data([dict(r) for r in promociones])

        self._feedback.clear()
        self.main_window.set_status("Software autorizado actualizado")

    def _on_error(self, msg: str) -> None:
        self._feedback.show_message(f"Error: {msg}", "error")

    # ------------------------------------------------------------------
    def _revoke_selected(self) -> None:
        row = self._auth_table.selected_row()
        if not row:
            self._feedback.show_message("Selecciona una autorización para revocar.", "warning")
            return
        if not confirm(
            self,
            "Revocar autorización",
            f"Se revocará la autorización de «{row.get('nombre')}».",
            details="El software seguirá en el inventario; solo deja de figurar como autorizado.",
            ok_text="Revocar",
            danger=True,
        ):
            return
        self._run_action(
            lambda db: _revoke_group(db, row["grupo"]),
            "Autorización revocada.",
        )

    def _authorize_selected(self) -> None:
        row = self._excl_table.selected_row()
        if not row:
            self._feedback.show_message("Selecciona un software exclusivo.", "warning")
            return
        if not confirm(
            self,
            "Autorizar software",
            f"Se autorizará «{row.get('nombre')}» como excepción específica.",
            ok_text="Autorizar",
        ):
            return
        self._run_action(
            lambda db: _authorize_ids(db, [row["id"]]),
            _authorization_message,
        )

    def _authorize_all(self) -> None:
        n = self._excl_table.row_count()
        if not n:
            self._feedback.show_message("No hay software exclusivo por autorizar.", "info")
            return
        if not confirm(
            self,
            "Autorizar exclusivos",
            f"Se autorizarán {n} programas instalados en un único equipo.",
            ok_text="Autorizar todos",
        ):
            return
        self._run_action(_authorize_all_exclusive, _authorization_message)

    def _promote_selected(self) -> None:
        row = self._promo_table.selected_row()
        if not row:
            self._feedback.show_message("Selecciona un software para promover.", "warning")
            return
        if not confirm(
            self,
            "Promover a autorización general",
            f"«{row.get('nombre')}» pasará a estar autorizado de forma general (sin equipo concreto).",
            ok_text="Promover",
        ):
            return
        self._run_action(
            lambda db: _promote_ids(db, [row["id"]]),
            "Autorización promovida a general.",
        )

    def _run_action(self, action, success_msg) -> None:
        try:
            from database.connection import get_engine
            with get_engine().begin() as db:
                result = action(db)
            message = success_msg(result) if callable(success_msg) else success_msg
            self._feedback.show_message(message, "success")
            self._load_data()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))


# --- acciones (se ejecutan dentro de una transacción) ------------------
def _revoke_group(db, grupo):
    from modules.autorizado import eliminar_autorizado_grupo
    return eliminar_autorizado_grupo(db, grupo)


def _authorize_ids(db, ids):
    from modules.autorizado import autorizar_softwares
    return autorizar_softwares(db, ids, "Autorizado manualmente desde Software autorizado")


def _authorization_message(n):
    if not n:
        return "El software seleccionado ya estaba autorizado."
    if n == 1:
        return "1 software autorizado."
    return f"{n} programas autorizados."


def _authorize_all_exclusive(db):
    from modules.autorizado import autorizar_exclusivos_automaticamente
    return autorizar_exclusivos_automaticamente(db)


def _promote_ids(db, ids):
    from modules.autorizado import promocionar_autorizaciones_generales
    return promocionar_autorizaciones_generales(db, ids, "Promovido a autorización general")
