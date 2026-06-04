from __future__ import annotations

from nicegui import ui

from database.connection import get_engine
from modules.autorizado import autorizar_softwares
from modules.software import actualizar_fabricante, fabricantes_vacios, software_comun_no_autorizado, versiones_sospechosas
from nicegui_app.components import empty_state, page_header
from nicegui_app.layout import create_layout
from nicegui_app.theme import apply_theme


@ui.page("/calidad")
def calidad_page() -> None:
    apply_theme()
    create_layout("/calidad")

    with ui.element("div").style("padding:28px 32px;background:#F4F7FA;min-height:calc(100vh - 52px);"):
        page_header("Calidad de datos", "Versiones sospechosas, fabricantes vacios y autorizacion")

        try:
            with get_engine().connect() as db:
                suspicious_versions = versiones_sospechosas(db)
                empty_manufacturers = fabricantes_vacios(db)
                common_not_authorized = software_comun_no_autorizado(db)
        except Exception as exc:
            ui.notify(f"Error de conexion: {exc}", type="negative")
            empty_state("Sin conexion", "No se pudo conectar con MySQL.", "cloud_off")
            return

        with ui.tabs().classes("w-full") as tabs:
            tab_v = ui.tab("Versiones sospechosas")
            tab_f = ui.tab("Fabricantes vacios")
            tab_c = ui.tab("Software comun no autorizado")

        with ui.tab_panels(tabs, value=tab_v).classes("w-full"):
            with ui.tab_panel(tab_v):
                if suspicious_versions:
                    ui.table(
                        columns=[
                            {"name": "nombre", "label": "Programa", "field": "nombre", "sortable": True, "align": "left"},
                            {"name": "version_referencia", "label": "Version", "field": "version_referencia", "align": "left"},
                            {"name": "fabricante", "label": "Fabricante", "field": "fabricante", "align": "left"},
                        ],
                        rows=suspicious_versions,
                        row_key="id",
                        pagination={"rowsPerPage": 25, "sortBy": "nombre"},
                    ).classes("w-full")
                else:
                    empty_state("Sin incidencias", "No se han detectado versiones sospechosas.", "check_circle")

            with ui.tab_panel(tab_f):
                if empty_manufacturers:
                    ui.table(
                        columns=[
                            {"name": "nombre", "label": "Programa", "field": "nombre", "sortable": True, "align": "left"},
                            {"name": "version_referencia", "label": "Version", "field": "version_referencia", "align": "left"},
                            {"name": "fabricante", "label": "Fabricante", "field": "fabricante", "align": "left"},
                        ],
                        rows=empty_manufacturers,
                        row_key="id",
                        pagination={"rowsPerPage": 25, "sortBy": "nombre"},
                    ).classes("w-full")

                    labels = {
                        f"{row['nombre']} - {row.get('version_referencia') or 'sin version'} (id {row['id']})": row
                        for row in empty_manufacturers
                    }
                    selected = ui.select(list(labels.keys()), label="Software a editar").props("outlined dense").style("width:360px;")
                    fabricante = ui.input("Fabricante").props("outlined dense").style("width:260px;")

                    def save_fabricante() -> None:
                        if not selected.value:
                            return
                        try:
                            with get_engine().begin() as db:
                                actualizar_fabricante(db, labels[selected.value]["id"], (fabricante.value or "").strip() or None)
                            ui.notify("Fabricante actualizado", type="positive")
                            ui.navigate.reload()
                        except Exception as exc:
                            ui.notify(f"Error al guardar: {exc}", type="negative")

                    ui.button("Guardar fabricante", on_click=save_fabricante, icon="save").props("outline")
                else:
                    empty_state("Sin incidencias", "No hay fabricantes vacios.", "check_circle")

            with ui.tab_panel(tab_c):
                if common_not_authorized:
                    ui.table(
                        columns=[
                            {"name": "nombre", "label": "Programa", "field": "nombre", "sortable": True, "align": "left"},
                            {"name": "n_departamentos", "label": "Departamentos", "field": "n_departamentos", "sortable": True, "align": "right"},
                        ],
                        rows=common_not_authorized,
                        row_key="software_id",
                    ).classes("w-full")

                    labels = {
                        f"{row['nombre']} ({row['n_departamentos']} departamentos)": row["software_id"]
                        for row in common_not_authorized
                    }
                    selected = ui.select(list(labels.keys()), label="Software a autorizar").props("outlined dense").style("width:380px;")

                    def authorize_selected() -> None:
                        if not selected.value:
                            return
                        try:
                            with get_engine().begin() as db:
                                inserted = autorizar_softwares(
                                    db,
                                    [labels[selected.value]],
                                    "Autorizado desde calidad de datos: software comun en mas de 3 departamentos",
                                )
                            ui.notify(f"Software autorizado anadido: {inserted}", type="positive")
                            ui.navigate.reload()
                        except Exception as exc:
                            ui.notify(f"Error al autorizar: {exc}", type="negative")

                    ui.button("Autorizar software seleccionado", on_click=authorize_selected, icon="verified_user").props("outline")
                else:
                    empty_state("Sin pendientes", "No hay software comun pendiente de autorizacion.", "check_circle")
