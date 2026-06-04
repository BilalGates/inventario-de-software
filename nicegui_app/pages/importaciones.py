from __future__ import annotations

from nicegui import ui

from database.connection import get_engine
from modules.equipos import listar_estado_importaciones
from modules.software import listar_departamentos
from nicegui_app.components import empty_state, kpi_card, page_header
from nicegui_app.layout import create_layout
from nicegui_app.theme import apply_theme


@ui.page("/importaciones")
def importaciones_page() -> None:
    apply_theme()
    create_layout("/importaciones")

    with ui.element("div").style("padding:28px 32px;background:#F4F7FA;min-height:calc(100vh - 52px);"):
        page_header("Estado de importaciones", "Monitoreo de importaciones por equipo")

        try:
            with get_engine().connect() as db:
                departamentos = listar_departamentos(db)
                rows = listar_estado_importaciones(db)
        except Exception as exc:
            ui.notify(f"Error de conexion: {exc}", type="negative")
            empty_state("Sin conexion", "No se pudo conectar con MySQL.", "cloud_off")
            return

        all_rows = [
            {
                "id": row["id"],
                "equipo": row["nombre"],
                "departamento": row.get("departamento_nombre") or "-",
                "departamento_id": row.get("departamento_id"),
                "ultima": str(row.get("ultima_importacion") or "-"),
                "dias": row.get("dias_desde_importacion"),
                "estado": row.get("estado_importacion") or "-",
            }
            for row in rows
        ]
        dept_options = {"Todos": None} | {dept["nombre"]: dept["id"] for dept in departamentos}
        state = {"dept": None, "estado": "Todos"}

        def filtered_rows() -> list[dict]:
            result = [
                row for row in all_rows
                if state["dept"] is None or row["departamento_id"] == state["dept"]
            ]
            if state["estado"] == "Solo pendientes (>30 dias)":
                result = [row for row in result if row["dias"] is None or row["dias"] > 30]
            elif state["estado"] == "Nunca importados":
                result = [row for row in result if row["dias"] is None]
            return result

        def refresh() -> None:
            result = filtered_rows()
            table.rows = result
            total = len(result)
            al_dia = len([row for row in result if row["dias"] is not None and row["dias"] < 30])
            pendientes = len([row for row in result if row["dias"] is not None and row["dias"] >= 30])
            nunca = len([row for row in result if row["dias"] is None])
            metrics.clear()
            with metrics:
                kpi_card("Total equipos", total, "devices", "blue")
                kpi_card("Al dia", al_dia, "check_circle", "green")
                kpi_card("Pendientes", pendientes, "schedule", "amber")
                kpi_card("Nunca importados", nunca, "warning", "red")

        with ui.row().classes("gap-4 items-center").style("margin-bottom:12px;"):
            ui.select(list(dept_options.keys()), value="Todos", label="Departamento", on_change=lambda e: (state.update({"dept": dept_options[e.value]}), refresh())).props("outlined dense").style("width:190px;")
            ui.select(["Todos", "Solo pendientes (>30 dias)", "Nunca importados"], value="Todos", label="Estado", on_change=lambda e: (state.update({"estado": e.value}), refresh())).props("outlined dense").style("width:230px;")

        metrics = ui.row().classes("w-full gap-4").style("margin-bottom:20px;")
        columns = [
            {"name": "equipo", "label": "Equipo", "field": "equipo", "sortable": True, "align": "left"},
            {"name": "departamento", "label": "Departamento", "field": "departamento", "sortable": True, "align": "left"},
            {"name": "ultima", "label": "Ultima importacion", "field": "ultima", "align": "left"},
            {"name": "dias", "label": "Dias", "field": "dias", "sortable": True, "align": "right"},
            {"name": "estado", "label": "Estado", "field": "estado", "align": "left"},
        ]
        table = ui.table(columns=columns, rows=[], row_key="id", pagination={"rowsPerPage": 30}).classes("w-full")
        refresh()
