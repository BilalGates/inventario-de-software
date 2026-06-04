from __future__ import annotations

from datetime import date

from nicegui import ui

from database.connection import get_engine
from modules.equipos import crear_equipo, existe_equipo, exportar_equipos_excel, listar_equipos, listar_estado_importaciones
from modules.software import listar_departamentos
from nicegui_app.components import empty_state, page_header
from nicegui_app.layout import create_layout
from nicegui_app.theme import apply_theme


@ui.page("/equipos")
def equipos_page() -> None:
    apply_theme()
    create_layout("/equipos")

    with ui.element("div").style("padding:28px 32px;background:#F4F7FA;min-height:calc(100vh - 52px);"):
        page_header("Equipos", "Todos los dispositivos de la empresa")

        try:
            with get_engine().connect() as db:
                departamentos = listar_departamentos(db)
                equipos = listar_estado_importaciones(db)
        except Exception as exc:
            ui.notify(f"Error de conexion: {exc}", type="negative")
            empty_state("Sin conexion", "No se pudo conectar con MySQL.", "cloud_off")
            return

        all_rows = [
            {
                **eq,
                "departamento": eq.get("departamento_nombre") or "-",
                "usuario": eq.get("notas") or "-",
                "ultima_imp": str(eq.get("ultima_importacion") or "-"),
                "estado_txt": eq.get("estado_importacion") or "-",
            }
            for eq in equipos
        ]

        columns = [
            {"name": "departamento", "label": "Departamento", "field": "departamento", "sortable": True, "align": "left"},
            {"name": "nombre", "label": "Dispositivo", "field": "nombre", "sortable": True, "align": "left"},
            {"name": "usuario", "label": "Usuario", "field": "usuario", "align": "left"},
            {"name": "ultima_imp", "label": "Ultima imp.", "field": "ultima_imp", "align": "left"},
            {"name": "estado", "label": "Estado", "field": "estado_txt", "align": "center"},
        ]

        dept_options = {"Todos": None} | {dept["nombre"]: dept["id"] for dept in departamentos}
        selected_dept = {"value": None}
        search_val = {"value": ""}

        def apply_filters() -> None:
            dept_id = selected_dept["value"]
            needle = search_val["value"].lower()
            table.rows = [
                row for row in all_rows
                if (dept_id is None or row.get("departamento_id") == dept_id)
                and (
                    not needle
                    or needle in str(row.get("nombre", "")).lower()
                    or needle in str(row.get("usuario", "")).lower()
                    or needle in str(row.get("departamento", "")).lower()
                )
            ]

        with ui.row().classes("gap-4 items-center").style("margin-bottom:12px;"):
            ui.select(list(dept_options.keys()), value="Todos", label="Departamento", on_change=lambda e: (selected_dept.update({"value": dept_options[e.value]}), apply_filters())).props("outlined dense").style("width:180px;")
            ui.input(placeholder="Buscar dispositivo o usuario", on_change=lambda e: (search_val.update({"value": e.value or ""}), apply_filters())).props("outlined dense clearable").style("width:240px;")

        with ui.card().style("width:100%;padding:0;overflow:hidden;"):
            table = ui.table(columns=columns, rows=all_rows, row_key="id", pagination={"rowsPerPage": 30, "sortBy": "departamento"}).classes("w-full").style("border-radius:0;border:none;box-shadow:none;")
            table.add_slot("body-cell-estado", """
                <q-td :props="props" style="text-align:center;">
                    <span :style="{
                        display:'inline-flex', alignItems:'center', padding:'2px 9px', borderRadius:'99px',
                        fontSize:'11px', fontWeight:'500',
                        background: props.row.estado_txt.includes('Nunca') ? '#FEE2E2' : (parseInt(props.row.estado_txt.match(/\\d+/)?.[0] || '999') < 30 ? '#DCFCE7' : '#FEF3C7'),
                        color: props.row.estado_txt.includes('Nunca') ? '#991B1B' : (parseInt(props.row.estado_txt.match(/\\d+/)?.[0] || '999') < 30 ? '#166534' : '#92400E'),
                    }">{{ props.row.estado_txt.replace(/^\\S+\\s*/, '') }}</span>
                </q-td>
            """)

        ui.separator().style("margin:16px 0;border-color:#E8EDF2;")
        with ui.expansion("Anadir dispositivo", icon="add_circle").style("background:#fff;border:1px solid #E8EDF2;border-radius:14px;"):
            dept_opts_add = {dept["nombre"]: dept["id"] for dept in departamentos}
            add_dept = ui.select(list(dept_opts_add.keys()), label="Departamento").props("outlined dense").style("width:220px;")
            add_nombre = ui.input("Nombre del dispositivo").props("outlined dense").style("width:260px;")
            add_usuario = ui.input("Usuario").props("outlined dense").style("width:220px;")

            def handle_add() -> None:
                if not add_nombre.value or not add_dept.value:
                    ui.notify("Nombre y departamento son obligatorios", type="warning")
                    return
                dept_id = dept_opts_add[add_dept.value]
                try:
                    with get_engine().begin() as db:
                        if existe_equipo(db, dept_id, add_nombre.value):
                            ui.notify("Ya existe un dispositivo con ese nombre en ese departamento", type="warning")
                            return
                        crear_equipo(db, dept_id, add_nombre.value, add_usuario.value or None)
                    ui.notify("Dispositivo anadido", type="positive")
                    ui.navigate.reload()
                except Exception as exc:
                    ui.notify(f"Error al guardar: {exc}", type="negative")

            ui.button("Guardar", on_click=handle_add, icon="save").props("unelevated color=primary").style(
                "background:#2E1A47;color:#fff;margin-top:12px;"
            )

        def handle_export() -> None:
            try:
                with get_engine().connect() as db:
                    data = exportar_equipos_excel(listar_equipos(db, es_servidor=False), "Equipos")
                ui.download(data, filename=f"Inventario_Equipos_{date.today().isoformat()}.xlsx")
            except Exception as exc:
                ui.notify(f"Error al exportar: {exc}", type="negative")

        ui.button("Exportar Excel", on_click=handle_export, icon="download").props("outline").style(
            "border-color:#E2E8F0;color:#2E1A47;margin-top:8px;"
        )
