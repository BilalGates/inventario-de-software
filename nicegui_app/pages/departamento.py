from __future__ import annotations

from datetime import date

from nicegui import ui

from database.connection import get_engine
from modules.exportacion import generar_excel
from modules.software import listar_inventario, obtener_departamento_por_codigo
from nicegui_app.components import empty_state, page_header
from nicegui_app.layout import create_layout
from nicegui_app.theme import apply_theme


def _dash(value) -> str:
    return str(value) if value not in (None, "") else "-"


def _make_dept_page(codigo: str, path: str) -> None:
    @ui.page(path)
    def dept_page() -> None:
        apply_theme()
        create_layout(path)

        with ui.element("div").style("padding:28px 32px;background:#F4F7FA;min-height:calc(100vh - 52px);"):
            try:
                with get_engine().connect() as db:
                    dept = obtener_departamento_por_codigo(db, codigo)
                    if not dept:
                        ui.notify("Departamento no encontrado", type="warning")
                        return
                    inventario = listar_inventario(db, dept["id"])
            except Exception as exc:
                ui.notify(f"Error de conexion: {exc}", type="negative")
                empty_state("Sin conexion", "No se pudo conectar con MySQL.", "cloud_off")
                return

            page_header(dept["nombre"], f"{len(inventario)} programas activos")

            all_rows = [dict(row) for row in inventario]
            for row in all_rows:
                row["dispositivos"] = _dash(row.get("dispositivos"))
                row["fabricante"] = _dash(row.get("fabricante"))
                row["version_referencia"] = _dash(row.get("version_referencia"))

            columns = [
                {"name": "codigo", "label": "ID", "field": "codigo", "sortable": True, "align": "left"},
                {"name": "nombre", "label": "Programa", "field": "nombre", "sortable": True, "align": "left"},
                {"name": "fabricante", "label": "Fabricante", "field": "fabricante", "sortable": True, "align": "left"},
                {"name": "version", "label": "Version", "field": "version_referencia", "align": "left"},
                {"name": "disp", "label": "Dispositivos", "field": "dispositivos", "align": "left"},
                {"name": "guia", "label": "Guia 105", "field": "en_guia_105", "sortable": True, "align": "center"},
            ]

            with ui.card().style("width:100%;padding:0;overflow:hidden;"):
                with ui.row().classes("items-center gap-4").style("padding:14px 18px 8px;"):
                    ui.label(f"Inventario - {dept['nombre']}").style("font-size:13px;font-weight:600;color:#1E293B;flex:1;")
                    search_input = ui.input(placeholder="Buscar programa...").props("outlined dense clearable").style("width:220px;")

                table = ui.table(
                    columns=columns,
                    rows=all_rows,
                    row_key="id",
                    pagination={"rowsPerPage": 25, "sortBy": "nombre"},
                ).classes("w-full").style("border-radius:0;border:none;box-shadow:none;")

                table.add_slot("body-cell-guia", """
                    <q-td :props="props" style="text-align:center;">
                        <span v-if="props.row.en_guia_105 === true || props.row.en_guia_105 === 1"
                            style="display:inline-flex;align-items:center;padding:2px 9px;border-radius:99px;font-size:11px;font-weight:500;background:#DCFCE7;color:#166534;">Si</span>
                        <span v-else-if="props.row.en_guia_105 === false || props.row.en_guia_105 === 0"
                            style="display:inline-flex;align-items:center;padding:2px 9px;border-radius:99px;font-size:11px;font-weight:500;background:#FEE2E2;color:#991B1B;">No</span>
                        <span v-else style="color:#94A3B8;font-size:12px;">-</span>
                    </q-td>
                """)

            def filter_table(e) -> None:
                needle = (e.value or "").strip().lower()
                table.rows = [
                    row for row in all_rows
                    if needle in str(row.get("nombre", "")).lower()
                    or needle in str(row.get("fabricante", "")).lower()
                    or needle in str(row.get("dispositivos", "")).lower()
                ] if needle else all_rows

            search_input.on("update:model-value", filter_table)

            ui.separator().style("margin:16px 0;border-color:#E8EDF2;")

            def handle_export() -> None:
                try:
                    with get_engine().connect() as db:
                        data = generar_excel(db, [dept["id"]])
                    ui.download(data, filename=f"Inventario_{dept['nombre']}_{date.today().isoformat()}.xlsx")
                except Exception as exc:
                    ui.notify(f"Error al exportar: {exc}", type="negative")

            ui.button("Exportar Excel", on_click=handle_export, icon="download").props("outline").style(
                "border-color:#E2E8F0;color:#2E1A47;"
            )


_make_dept_page("gerencia", "/dept/gerencia")
_make_dept_page("it", "/dept/it")
_make_dept_page("silicon", "/dept/silicon")
_make_dept_page("data_science", "/dept/data_science")
_make_dept_page("administracion", "/dept/administracion")
_make_dept_page("servidores", "/dept/servidores")
