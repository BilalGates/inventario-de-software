from __future__ import annotations

from nicegui import ui

from database.connection import get_engine
from modules.autorizado import (
    contar_pendientes_promocion,
    crear_autorizado,
    eliminar_autorizado,
    eliminar_autorizado_grupo,
    listar_autorizado_agrupado,
    listar_autorizado_detalle_grupo,
    promover_todos_los_pendientes,
)
from modules.equipos import listar_equipos
from modules.software import listar_departamentos
from nicegui_app.components import empty_state, page_header
from nicegui_app.layout import create_layout
from nicegui_app.theme import apply_theme


@ui.page("/autorizado")
def autorizado_page() -> None:
    apply_theme()
    create_layout("/autorizado")

    with ui.element("div").style("padding:28px 32px;background:#F4F7FA;min-height:calc(100vh - 52px);"):
        page_header("Software autorizado", "Programas autorizados por departamento")

        try:
            with get_engine().connect() as db:
                grouped_rows = listar_autorizado_agrupado(db)
                pendientes_promocion = contar_pendientes_promocion(db)
                departamentos = listar_departamentos(db)
                all_equipos = []
                for dept in departamentos:
                    all_equipos.extend(listar_equipos(db, dept["id"], solo_activos=True))
        except Exception as exc:
            ui.notify(f"Error de conexion: {exc}", type="negative")
            empty_state("Sin conexion", "No se pudo conectar con MySQL.", "cloud_off")
            return

        if pendientes_promocion > 0:
            with ui.card().classes("w-full").style("padding:14px 18px;margin-bottom:14px;background:#FEF3C7;border-color:#F59E0B;"):
                ui.label(
                    f"{pendientes_promocion} programa(s) deben pasar al inventario del departamento."
                ).style("font-size:13px;font-weight:600;color:#92400E;")

                def promote() -> None:
                    try:
                        with get_engine().begin() as db:
                            result = promover_todos_los_pendientes(db)
                        ui.notify(
                            f"Movidos al inventario: {result['total']} ({result['por_antiguedad']} por antiguedad, {result['por_multidevice']} por multiples dispositivos).",
                            type="positive",
                        )
                        ui.navigate.reload()
                    except Exception as exc:
                        ui.notify(f"Error al mover: {exc}", type="negative")

                ui.button("Mover al inventario de departamento", on_click=promote, icon="upgrade").props("unelevated").style(
                    "background:#2E1A47;color:#fff;margin-top:8px;"
                )

        rows = [
            {
                "grupo": row["grupo"],
                "nombre": row.get("nombre"),
                "fabricantes": row.get("fabricantes") or "-",
                "versiones": row.get("versiones") or "-",
                "departamentos": row.get("departamentos") or "-",
                "equipos": row.get("equipos_usuarios") or "-",
                "n_dispositivos": row.get("n_dispositivos") or 0,
                "observaciones": row.get("observaciones") or "-",
                "fecha": str(row.get("fecha_reciente") or "-"),
            }
            for row in grouped_rows
        ]
        columns = [
            {"name": "nombre", "label": "Programa", "field": "nombre", "sortable": True, "align": "left"},
            {"name": "fabricantes", "label": "Fabricante", "field": "fabricantes", "align": "left"},
            {"name": "versiones", "label": "Versiones", "field": "versiones", "align": "left"},
            {"name": "departamentos", "label": "Departamentos", "field": "departamentos", "align": "left"},
            {"name": "equipos", "label": "Equipos / Usuarios", "field": "equipos", "align": "left"},
            {"name": "n_dispositivos", "label": "Dispositivos", "field": "n_dispositivos", "sortable": True, "align": "right"},
            {"name": "fecha", "label": "Ultima autorizacion", "field": "fecha", "align": "left"},
        ]
        if rows:
            ui.table(columns=columns, rows=rows, row_key="grupo", pagination={"rowsPerPage": 25, "sortBy": "nombre"}).classes("w-full")
        else:
            empty_state("Sin software autorizado", "No hay software autorizado registrado.", "verified_user")

        with ui.expansion("Anadir software autorizado", icon="add_circle").style(
            "background:#fff;border:1px solid #E8EDF2;border-radius:14px;margin-top:16px;"
        ):
            dept_options = {"Sin departamento": None} | {dept["nombre"]: dept["id"] for dept in departamentos}
            equipo_options = {"Texto libre": None} | {f"{eq['nombre']} (id {eq['id']})": eq["id"] for eq in all_equipos}
            nombre = ui.input("Nombre").props("outlined dense").style("width:260px;")
            fabricante = ui.input("Fabricante").props("outlined dense").style("width:220px;")
            tipo = ui.input("Tipo").props("outlined dense").style("width:180px;")
            version = ui.input("Version").props("outlined dense").style("width:180px;")
            departamento = ui.select(list(dept_options.keys()), value="Sin departamento", label="Departamento").props("outlined dense").style("width:220px;")
            equipo = ui.select(list(equipo_options.keys()), value="Texto libre", label="Equipo").props("outlined dense").style("width:260px;")
            usuario_texto = ui.input("Equipo o usuario").props("outlined dense").style("width:260px;")
            observaciones = ui.textarea("Observaciones").props("outlined").style("width:360px;")

            def save_authorized() -> None:
                if not (nombre.value or "").strip():
                    ui.notify("El nombre es obligatorio", type="warning")
                    return
                try:
                    with get_engine().begin() as db:
                        crear_autorizado(db, {
                            "departamento_id": dept_options[departamento.value],
                            "nombre": nombre.value.strip(),
                            "fabricante": (fabricante.value or "").strip() or None,
                            "tipo": (tipo.value or "").strip() or None,
                            "version": (version.value or "").strip() or None,
                            "equipo_id": equipo_options[equipo.value],
                            "usuario_texto": (usuario_texto.value or "").strip() if equipo.value == "Texto libre" else None,
                            "observaciones": (observaciones.value or "").strip() or None,
                        })
                    ui.notify("Software autorizado anadido", type="positive")
                    ui.navigate.reload()
                except Exception as exc:
                    ui.notify(f"Error al guardar: {exc}", type="negative")

            ui.button("Guardar", on_click=save_authorized, icon="save").props("unelevated").style(
                "background:#2E1A47;color:#fff;margin-top:12px;"
            )

        if grouped_rows:
            with ui.expansion("Detalle y archivo", icon="edit").style("background:#fff;border:1px solid #E8EDF2;border-radius:14px;margin-top:16px;"):
                group_options = {f"{row['nombre']} ({row.get('n_dispositivos', 0)} dispositivos)": row["grupo"] for row in grouped_rows}
                detail_container = ui.column().classes("w-full")
                selected = ui.select(list(group_options.keys()), label="Programa autorizado").props("outlined dense").style("width:320px;")

                def load_detail() -> None:
                    detail_container.clear()
                    group = group_options.get(selected.value)
                    if not group:
                        return
                    try:
                        with get_engine().connect() as db:
                            detail = listar_autorizado_detalle_grupo(db, group)
                    except Exception as exc:
                        ui.notify(f"Error al cargar detalle: {exc}", type="negative")
                        return
                    detail_rows = [
                        {
                            "id": row["id"],
                            "programa": row.get("nombre_visible"),
                            "fabricante": row.get("fabricante_visible"),
                            "version": row.get("version_visible"),
                            "departamento": row.get("departamento_nombre") or "-",
                            "equipo": row.get("equipo_nombre") or row.get("usuario_texto") or "-",
                            "fecha": str(row.get("fecha_autorizacion") or row.get("fecha_alta") or "-"),
                        }
                        for row in detail
                    ]
                    with detail_container:
                        ui.table(
                            columns=[
                                {"name": "programa", "label": "Programa", "field": "programa", "align": "left"},
                                {"name": "fabricante", "label": "Fabricante", "field": "fabricante", "align": "left"},
                                {"name": "version", "label": "Version", "field": "version", "align": "left"},
                                {"name": "departamento", "label": "Departamento", "field": "departamento", "align": "left"},
                                {"name": "equipo", "label": "Equipo/Usuario", "field": "equipo", "align": "left"},
                                {"name": "fecha", "label": "Fecha", "field": "fecha", "align": "left"},
                            ],
                            rows=detail_rows,
                            row_key="id",
                        ).classes("w-full")

                        detail_labels = {f"{row['programa']} - {row.get('version') or 'sin version'} (id {row['id']})": row["id"] for row in detail_rows}
                        archive_one = ui.select(list(detail_labels.keys()), label="Registro individual a archivar").props("outlined dense").style("width:360px;")

                        def archive_selected() -> None:
                            if not archive_one.value:
                                return
                            with get_engine().begin() as db:
                                eliminar_autorizado(db, detail_labels[archive_one.value])
                            ui.notify("Registro archivado", type="positive")
                            ui.navigate.reload()

                        def archive_group() -> None:
                            with get_engine().begin() as db:
                                count = eliminar_autorizado_grupo(db, group)
                            ui.notify(f"Registros archivados: {count}", type="positive")
                            ui.navigate.reload()

                        with ui.row().classes("gap-3"):
                            ui.button("Archivar registro individual", on_click=archive_selected, icon="archive").props("outline")
                            ui.button("Archivar programa completo", on_click=archive_group, icon="delete").props("outline")

                selected.on("update:model-value", lambda _: load_detail())
