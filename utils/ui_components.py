from __future__ import annotations

import streamlit as st


_KPI_COLORS: dict[str, tuple[str, str]] = {
    "purple":  ("#EDE7F6", "#6D28D9"),
    "blue":    ("#E0F2FE", "#0284C7"),
    "amber":   ("#FEF9C3", "#B45309"),
    "red":     ("#FEE2E2", "#DC2626"),
    "green":   ("#DCFCE7", "#166534"),
    "teal":    ("#CCFBF1", "#0F766E"),
}


def kpi_card(
    label: str,
    value: str | int,
    icon: str = "ti-chart-bar",
    color: str = "purple",
    delta: str | None = None,
    delta_color: str = "#10B981",
) -> None:
    bg, fg = _KPI_COLORS.get(color, _KPI_COLORS["purple"])
    delta_html = (
        f'<div style="font-size:11px;color:{delta_color};margin-top:6px;">{delta}</div>'
        if delta
        else ""
    )
    st.markdown(
        f"""
        <div style="background:#fff;border-radius:16px;border:1px solid #E2E8F0;
                    box-shadow:0 4px 6px -1px rgba(0,0,0,0.05);
                    padding:18px 20px 16px;">
          <div style="width:36px;height:36px;border-radius:9px;background:{bg};
                      display:flex;align-items:center;justify-content:center;
                      margin-bottom:12px;">
            <i class="{icon}" style="font-size:18px;color:{fg};" aria-hidden="true"></i>
          </div>
          <div style="font-size:26px;font-weight:600;color:#1E293B;line-height:1;">{value}</div>
          <div style="font-size:12px;color:#94A3B8;margin-top:4px;font-weight:500;
                      text-transform:uppercase;letter-spacing:0.04em;">{label}</div>
          {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(title: str, subtitle: str = "", action_label: str = "", action_key: str = "") -> bool:
    col_title, col_action = st.columns([5, 1])
    with col_title:
        st.markdown(
            f"""
            <div style="margin-bottom:4px;">
              <span style="font-size:16px;font-weight:600;color:#1E293B;">{title}</span>
              {"<br><span style='font-size:12px;color:#94A3B8;'>" + subtitle + "</span>" if subtitle else ""}
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_action:
        if action_label:
            return st.button(action_label, key=action_key or f"action_{title}")
    return False


def empty_state(
    title: str = "Sin datos",
    message: str = "No hay registros que mostrar.",
    icon: str = "ti-database-off",
) -> None:
    st.markdown(
        f"""
        <div style="text-align:center;padding:48px 24px;background:#fff;
                    border-radius:16px;border:1px solid #E2E8F0;
                    box-shadow:0 4px 6px -1px rgba(0,0,0,0.05);">
          <div style="width:56px;height:56px;border-radius:14px;background:#F1F5F9;
                      display:flex;align-items:center;justify-content:center;
                      margin:0 auto 16px;font-size:26px;color:#CBD5E1;">
            <i class="{icon}" aria-hidden="true"></i>
          </div>
          <div style="font-size:15px;font-weight:600;color:#374151;margin-bottom:6px;">{title}</div>
          <div style="font-size:13px;color:#94A3B8;max-width:320px;margin:0 auto;">{message}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def status_badge(text: str, variant: str = "neutral") -> str:
    _styles: dict[str, tuple[str, str]] = {
        "success": ("#DCFCE7", "#166534"),
        "warning": ("#FEF9C3", "#854D0E"),
        "danger":  ("#FEE2E2", "#991B1B"),
        "info":    ("#E0F2FE", "#0369A1"),
        "neutral": ("#F1F5F9", "#475569"),
    }
    bg, fg = _styles.get(variant, _styles["neutral"])
    return (
        f'<span style="display:inline-flex;align-items:center;padding:3px 10px;'
        f'border-radius:99px;font-size:11px;font-weight:500;'
        f'background:{bg};color:{fg};">{text}</span>'
    )


def card_container() -> "st.delta_generator.DeltaGenerator":
    return st.container(border=True)


def page_header(title: str, subtitle: str = "") -> None:
    st.markdown(
        f"""
        <div style="margin-bottom:1.5rem;">
          <h1 style="margin:0 0 4px;">{title}</h1>
          {"<p style='font-size:13px;color:#94A3B8;margin:0;'>" + subtitle + "</p>" if subtitle else ""}
        </div>
        """,
        unsafe_allow_html=True,
    )
