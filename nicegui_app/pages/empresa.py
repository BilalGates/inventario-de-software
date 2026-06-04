from __future__ import annotations

from nicegui import ui

from database.connection import get_engine
from modules.equipos import listar_equipos
from modules.software import listar_departamentos, listar_inventario_empresa
from nicegui_app.components import empty_state, page_header
from nicegui_app.layout import create_layout
from nicegui_app.theme import apply_theme


@ui.page("/empresa")
def empresa_page() -> None:
    apply_theme()
    create_layout("/empresa")

    with ui.element("div").style("padding:28px 32px;background:#F4F7FA;min-height:calc(100vh - 52px);"):
        page_header("Software de la empresa", "Vision global de todo el software registrado")

        try:
            with get_engine().connect() as db:
                departamentos = listar_departamentos(db)
                equipos = []
                for dept in departamentos:
                    equipos.extend(listar_equipos(db, dept["id"], solo_activos=True))
                rows = listar_inventario_empresa(db)
        except Exception as exc:
            ui.notify(f"Error de conexion: {exc}", type="negative")
            empty_state("Sin conexion", "No se pudo conectar con MySQL.", "cloud_off")
            return

        dept_options = {"Todos": None} | {dept["nombre"]: dept["id"] for dept in departamentos}
        equipo_options = {"Todos": None} | {f"{eq['nombre']} ({eq['departamento_nombre']})": eq["id"] for eq in equipos}
        state = {"dept": None, "equipo": None, "solo_comun": False, "texto": "", "detallada": False}

        def to_table_rows(source: list[dict]) -> list[dict]:
            return [
                {
                    "nombre": row.get("nombre"),
                    "fabricantes": row.get("fabricantes") or "-",
                    "versiones": row.get("versiones") or "-",
                    "departamentos": row.get("departamentos") or "-",
                    "dispositivos": row.get("dispositivos") or "-",
                    "clasificaciones": row.get("clasificaciones") or "-",
                    "guia": "Pendiente" if row.get("en_guia_105") is None else ("Si" if bool(row.get("en_guia_105")) else "No"),
                    "observaciones": row.get("observaciones") or "-",
                    "ultima": str(row.get("fecha_ultima_actualizacion") or "-"),
                    "n_departamentos": row.get("n_departamentos") or 0,
                }
                for row in source
            ]

        columns_basic = [
            {"name": "nombre", "label": "Programa", "field": "nombre", "sortable": True, "align": "left"},
            {"name": "fabricantes", "label": "Fabricante", "field": "fabricantes", "align": "left"},
            {"name": "versiones", "label": "Version", "field": "versiones", "align": "left"},
            {"name": "dispositivos", "label": "Dispositivos", "field": "dispositivos", "align": "left"},
            {"name": "ultima", "label": "Ultima actualizacion", "field": "ultima", "sortable": True, "align": "left"},
        ]
        columns_detail = columns_basic + [
            {"name": "departamentos", "label": "Departamentos", "field": "departamentos", "align": "left"},
            {"name": "n_departamentos", "label": "N. departamentos", "field": "n_departamentos", "sortable": True, "align": "right"},
            {"name": "clasificaciones", "label": "Clasificacion", "field": "clasificaciones", "align": "left"},
            {"name": "guia", "label": "Guia 105", "field": "guia", "sortable": True, "align": "left"},
            {"name": "observaciones", "label": "Observaciones", "field": "observaciones", "align": "left"},
        ]

        with ui.row().classes("gap-4 items-center").style("margin-bottom:12px;"):
            ui.select(list(dept_options.keys()), value="Todos", label="Departamento", on_change=lambda e: update_filter("dept", dept_options[e.value])).props("outlined dense").style("width:190px;")
            ui.select(list(equipo_options.keys()), value="Todos", label="Dispositivo", on_change=lambda e: update_filter("equipo", equipo_options[e.value])).props("outlined dense").style("width:240px;")
            ui.checkbox("Solo software comun", on_change=lambda e: update_filter("solo_comun", bool(e.value)))
            ui.checkbox("Vista detallada", on_change=lambda e: update_filter("detallada", bool(e.value)))
            ui.input(placeholder="Buscar software...", on_change=lambda e: update_filter("texto", e.value or "")).props("outlined dense clearable").style("width:220px;")

        table = ui.table(
            columns=columns_basic,
            rows=to_table_rows(rows),
            row_key="nombre",
            pagination={"rowsPerPage": 25, "sortBy": "nombre"},
        ).classes("w-full").style("border-radius:0;border:none;box-shadow:none;")

        def update_filter(key: str, value) -> None:
            state[key] = value
            try:
                with get_engine().connect() as db:
                    filtered = listar_inventario_empresa(
                        db,
                        departamento_ids=[state["dept"]] if state["dept"] is not None else None,
                        equipo_ids=[state["equipo"]] if state["equipo"] is not None else None,
                        solo_comun=state["solo_comun"],
                        texto_libre=state["texto"] or None,
                    )
            except Exception as exc:
                ui.notify(f"Error al filtrar: {exc}", type="negative")
                return
            table.columns = columns_detail if state["detallada"] else columns_basic
            table.rows = to_table_rows(filtered)

        if not rows:
            empty_state("Sin software", "No hay software que coincida con los filtros.", "apps")
