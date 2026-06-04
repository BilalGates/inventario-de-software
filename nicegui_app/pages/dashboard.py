from __future__ import annotations

from datetime import date

from nicegui import ui

from database.connection import get_engine
from modules.equipos import listar_estado_importaciones
from modules.exportacion import generar_excel_completo
from modules.software import dashboard_metricas, estado_departamentos
from nicegui_app.components import empty_state, kpi_card, page_header
from nicegui_app.layout import create_layout
from nicegui_app.theme import apply_theme


def _fmt_date(value) -> str:
    return str(value) if value else "-"


@ui.page("/")
def dashboard() -> None:
    apply_theme()
    create_layout("/")

    with ui.element("div").style("padding:28px 32px;background:#F4F7FA;min-height:calc(100vh - 52px);"):
        page_header("Dashboard", "Vision general del inventario de software")

        try:
            with get_engine().connect() as db:
                metricas = dashboard_metricas(db)
                departamentos = estado_departamentos(db)
                equipos_estado = listar_estado_importaciones(db)
        except Exception as exc:
            ui.notify(f"Error de conexion: {exc}", type="negative", position="top")
            empty_state("Sin conexion", "No se pudo conectar con MySQL.", "cloud_off")
            return

        with ui.row().classes("w-full gap-4").style("margin-bottom:20px;"):
            kpi_card("Equipos activos", metricas["equipos_activos"], "devices", "blue")
            kpi_card("Software activo", metricas["software_activo"], "apps", "purple")
            kpi_card("Importaciones mes", metricas["importaciones_mes"], "sync", "green")
            kpi_card("Pendiente autorizado", metricas["autorizado_pendiente_promocion"], "verified_user", "amber")

        dept_rows = [
            {
                "departamento": row["departamento"],
                "equipos": row["equipos_activos"],
                "software": row["software_visible"],
                "ultima": _fmt_date(row.get("ultima_importacion")),
            }
            for row in departamentos
        ]
        dept_cols = [
            {"name": "departamento", "label": "Departamento", "field": "departamento", "sortable": True, "align": "left"},
            {"name": "equipos", "label": "Equipos", "field": "equipos", "sortable": True, "align": "right"},
            {"name": "software", "label": "Software", "field": "software", "sortable": True, "align": "right"},
            {"name": "ultima", "label": "Ultima importacion", "field": "ultima", "sortable": True, "align": "left"},
        ]

        with ui.row().classes("w-full gap-4 items-start"):
            with ui.card().classes("flex-1").style("padding:0;overflow:hidden;"):
                ui.label("Estado por departamento").style("font-size:13px;font-weight:600;color:#1E293B;padding:14px 18px 10px;")
                ui.table(columns=dept_cols, rows=dept_rows, row_key="departamento").classes("w-full").style(
                    "border-radius:0;border:none;box-shadow:none;"
                )

            alertas = [
                {
                    "nombre": row["nombre"],
                    "departamento": row.get("departamento_nombre") or "-",
                    "ultima": _fmt_date(row.get("ultima_importacion")),
                    "dias": row.get("dias_desde_importacion"),
                }
                for row in equipos_estado
                if row["dias_desde_importacion"] is None
                or row["dias_desde_importacion"] > 30
                or not row.get("responsable")
            ]
            with ui.card().classes("flex-1").style("padding:0;overflow:hidden;"):
                ui.label("Alertas de importacion").style("font-size:13px;font-weight:600;color:#1E293B;padding:14px 18px 10px;")
                if alertas:
                    alert_cols = [
                        {"name": "nombre", "label": "Equipo", "field": "nombre", "sortable": True, "align": "left"},
                        {"name": "departamento", "label": "Departamento", "field": "departamento", "sortable": True, "align": "left"},
                        {"name": "ultima", "label": "Ultima imp.", "field": "ultima", "align": "left"},
                        {"name": "dias", "label": "Dias", "field": "dias", "sortable": True, "align": "right"},
                    ]
                    ui.table(columns=alert_cols, rows=alertas[:50], row_key="nombre").classes("w-full").style(
                        "border-radius:0;border:none;box-shadow:none;"
                    )
                else:
                    empty_state("Sin alertas", "Todas las importaciones estan al dia.", "check_circle")

        ui.separator().style("margin:20px 0;border-color:#E8EDF2;")

        def handle_export() -> None:
            try:
                with get_engine().connect() as db:
                    data = generar_excel_completo(db)
                ui.download(data, filename=f"Inventario_Asserta_{date.today().isoformat()}.xlsx")
            except Exception as exc:
                ui.notify(f"Error al exportar: {exc}", type="negative")

        ui.button("Exportar inventario completo", on_click=handle_export, icon="download").props("outline").style(
            "border-color:#E2E8F0;color:#2E1A47;font-size:13px;"
        )
