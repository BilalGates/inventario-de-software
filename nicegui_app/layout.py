from __future__ import annotations

from nicegui import ui

from nicegui_app.theme import BRAND_ACCENT, BRAND_PRIMARY, BRAND_SECONDARY

_NAV = [
    {"section": "Inicio", "items": [
        {"label": "Dashboard", "icon": "dashboard", "path": "/"},
    ]},
    {"section": "Inventario", "items": [
        {"label": "Resumen empresa", "icon": "apps", "path": "/empresa"},
        {"label": "Direccion", "icon": "corporate_fare", "path": "/dept/gerencia"},
        {"label": "IT", "icon": "terminal", "path": "/dept/it"},
        {"label": "Silicon", "icon": "memory", "path": "/dept/silicon"},
        {"label": "Data Science", "icon": "analytics", "path": "/dept/data_science"},
        {"label": "Administracion", "icon": "admin_panel_settings", "path": "/dept/administracion"},
        {"label": "Servidores", "icon": "dns", "path": "/dept/servidores"},
    ]},
    {"section": "Gestion", "items": [
        {"label": "Importaciones", "icon": "sync", "path": "/importaciones"},
        {"label": "Equipos", "icon": "devices", "path": "/equipos"},
        {"label": "Autorizado", "icon": "verified_user", "path": "/autorizado"},
        {"label": "Calidad de datos", "icon": "verified", "path": "/calidad"},
    ]},
]

_PAGE_NAMES: dict[str, str] = {item["path"]: item["label"] for section in _NAV for item in section["items"]}


def create_layout(active_path: str = "/") -> None:
    with ui.left_drawer(value=True, bordered=False).style(
        f"background: linear-gradient(180deg, {BRAND_PRIMARY} 0%, {BRAND_SECONDARY} 100%);"
        "width: 260px; padding: 0; overflow-y: auto;"
    ):
        _logo()
        _nav(active_path)

    with ui.header(elevated=False).style("background:#fff; height:52px; padding:0 28px;").classes(
        "items-center justify-between row"
    ):
        _breadcrumb(active_path)
        _search()


def _logo() -> None:
    with ui.element("div").style("padding:24px 20px 18px; border-bottom:1px solid rgba(255,255,255,.08);"):
        with ui.row().classes("items-center gap-3 no-wrap"):
            with ui.element("div").style(
                f"width:30px;height:30px;border-radius:8px;background:{BRAND_ACCENT};"
                "display:flex;align-items:center;justify-content:center;"
                "font-weight:700;font-size:15px;color:#fff;flex-shrink:0;"
            ):
                ui.label("A")
            with ui.column().style("gap:0;"):
                ui.label("ASSERTA").style("font-size:13px;font-weight:600;color:#fff;letter-spacing:.06em;")
                ui.label("Inventario de software").style(
                    "font-size:10px;color:rgba(255,255,255,.35);letter-spacing:.04em;"
                )


def _nav(active_path: str) -> None:
    for section in _NAV:
        with ui.element("div").style("padding:14px 10px 4px;"):
            ui.label(section["section"]).style(
                "font-size:9.5px;font-weight:600;color:rgba(255,255,255,.3);"
                "letter-spacing:.1em;text-transform:uppercase;padding:0 10px;margin-bottom:4px;display:block;"
            )
            for item in section["items"]:
                _nav_item(item["label"], item["icon"], item["path"], item["path"] == active_path)


def _nav_item(label: str, icon: str, path: str, active: bool) -> None:
    style_base = "display:flex;align-items:center;gap:9px;padding:8px 12px;border-radius:8px;cursor:pointer;margin:1px 8px;"
    style_active = f"background:rgba(0,176,255,.18);color:#fff;border-left:2px solid {BRAND_ACCENT};padding-left:10px;"
    style_inactive = "color:rgba(255,255,255,.65);"

    with ui.link(target=path).style("text-decoration:none;display:block;"):
        with ui.element("div").style(style_base + (style_active if active else style_inactive)).classes(
            "" if active else "hover:bg-white/10"
        ):
            ui.icon(icon).style("font-size:17px;")
            ui.label(label).style("font-size:12.5px;")


def _breadcrumb(active_path: str) -> None:
    name = _PAGE_NAMES.get(active_path, active_path.split("/")[-1].capitalize())
    with ui.row().classes("items-center gap-2"):
        ui.label("Inicio").style("font-size:12px;color:#94A3B8;")
        ui.label(">").style("color:#CBD5E1;")
        ui.label(name).style("font-size:12px;font-weight:500;color:#1E293B;")


def _search() -> None:
    with ui.row().style(
        "align-items:center;gap:7px;background:#F4F7FA;border:1px solid #E2E8F0;"
        "border-radius:8px;padding:5px 11px;width:210px;"
    ):
        ui.icon("search").style("font-size:14px;color:#94A3B8;")
        ui.input(placeholder="Buscar software, equipo...").props("borderless dense").style("font-size:12px;width:100%;")
