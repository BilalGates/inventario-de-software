from __future__ import annotations

from nicegui import ui

_KPI_COLORS: dict[str, tuple[str, str]] = {
    "purple": ("#EDE7F6", "#6D28D9"),
    "blue": ("#E0F2FE", "#0284C7"),
    "amber": ("#FEF9C3", "#B45309"),
    "red": ("#FEE2E2", "#DC2626"),
    "green": ("#DCFCE7", "#166534"),
    "teal": ("#CCFBF1", "#0F766E"),
}

_STATUS_STYLES: dict[str, tuple[str, str]] = {
    "success": ("#DCFCE7", "#166534"),
    "warning": ("#FEF3C7", "#92400E"),
    "danger": ("#FEE2E2", "#991B1B"),
    "info": ("#E0F2FE", "#0369A1"),
    "neutral": ("#F1F5F9", "#475569"),
}


def kpi_card(
    label: str,
    value: str | int,
    icon: str,
    color: str = "purple",
    delta: str | None = None,
    delta_ok: bool = True,
) -> None:
    bg, fg = _KPI_COLORS.get(color, _KPI_COLORS["purple"])
    with ui.card().classes("flex-1").style("padding: 18px 20px;"):
        with ui.row().classes("items-center justify-between w-full").style("margin-bottom:12px;"):
            with ui.element("div").style(
                f"width:36px;height:36px;border-radius:9px;background:{bg};"
                "display:flex;align-items:center;justify-content:center;"
            ):
                ui.icon(icon).style(f"font-size:18px;color:{fg};")
            if delta:
                d_color = "#10B981" if delta_ok else "#EF4444"
                ui.label(delta).style(f"font-size:11px;font-weight:500;color:{d_color};")
        ui.label(str(value)).style("font-size:26px;font-weight:600;color:#1E293B;line-height:1;")
        ui.label(label).style(
            "font-size:11px;color:#94A3B8;margin-top:3px;font-weight:500;"
            "text-transform:uppercase;letter-spacing:.04em;"
        )


def status_badge(text: str, variant: str = "neutral") -> None:
    bg, fg = _STATUS_STYLES.get(variant, _STATUS_STYLES["neutral"])
    ui.label(text).style(
        f"display:inline-flex;align-items:center;padding:3px 10px;"
        f"border-radius:99px;font-size:11px;font-weight:500;background:{bg};color:{fg};"
    )


def page_header(title: str, subtitle: str = "") -> None:
    ui.label(title).style("font-size:20px;font-weight:600;color:#1E293B;")
    if subtitle:
        ui.label(subtitle).style("font-size:12px;color:#94A3B8;margin-top:2px;")
    ui.separator().style("margin: 16px 0;border-color:#E8EDF2;")


def empty_state(title: str = "Sin datos", message: str = "No hay registros que mostrar.", icon: str = "inbox") -> None:
    with ui.column().classes("items-center w-full").style("padding: 48px 0;"):
        with ui.element("div").style(
            "width:56px;height:56px;border-radius:14px;background:#F1F5F9;"
            "display:flex;align-items:center;justify-content:center;margin-bottom:16px;"
        ):
            ui.icon(icon).style("font-size:26px;color:#CBD5E1;")
        ui.label(title).style("font-size:15px;font-weight:600;color:#374151;margin-bottom:4px;")
        ui.label(message).style("font-size:13px;color:#94A3B8;text-align:center;max-width:320px;")


def section_card(title: str = "", action_label: str = "", on_action=None):
    card = ui.card().classes("w-full").style("padding:0;")
    with card:
        if title or action_label:
            with ui.row().classes("items-center justify-between w-full").style("padding:14px 18px 10px;"):
                ui.label(title).style("font-size:13px;font-weight:600;color:#1E293B;")
                if action_label and on_action:
                    ui.button(action_label, on_click=on_action).props("flat dense").style("font-size:12px;color:#00B0FF;")
    return card
