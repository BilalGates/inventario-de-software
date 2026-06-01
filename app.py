from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from database.connection import get_engine
from modules.equipos import estado_importacion, listar_estado_importaciones
from modules.exportacion import generar_excel_completo
from modules.software import dashboard_metricas, estado_departamentos
from utils.theme import apply_theme, sidebar_logo
from utils.ui_components import empty_state, kpi_card, page_header, status_badge


st.set_page_config(
    page_title="Inventario Software — Asserta",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="https://asserta.net/wp-content/themes/asserta/img/favicon.png",
)

apply_theme()
sidebar_logo()

# ── Promoción automática al iniciar sesión ──────────────────────
if not st.session_state.get("_promocion_ejecutada"):
    try:
        with get_engine().begin() as _db:
            from modules.autorizado import promover_todos_los_pendientes
            _result = promover_todos_los_pendientes(_db)
            if _result["total"]:
                st.toast(
                    f"{_result['total']} programa(s) movidos al inventario del departamento.",
                    icon="ℹ️",
                )
    except Exception:
        pass
    finally:
        st.session_state["_promocion_ejecutada"] = True

st.session_state.setdefault("departamento_id", None)
st.session_state.setdefault("departamento_nombre", None)


def dashboard() -> None:
    page_header("Dashboard", "Visión general del inventario de software")

    try:
        with get_engine().connect() as db:
            metricas = dashboard_metricas(db)
            departamentos = estado_departamentos(db)
            equipos_estado = listar_estado_importaciones(db)
    except Exception as exc:
        st.error("No se pudo conectar con MySQL.")
        st.exception(exc)
        st.stop()

    # ── KPI Cards ────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4, gap="medium")
    with c1:
        kpi_card(
            "Equipos activos",
            metricas["equipos_activos"],
            icon="ti ti-device-laptop",
            color="purple",
        )
    with c2:
        kpi_card(
            "Software activo",
            metricas["software_activo"],
            icon="ti ti-apps",
            color="blue",
        )
    with c3:
        kpi_card(
            "Importaciones este mes",
            metricas["importaciones_mes"],
            icon="ti ti-refresh",
            color="amber",
        )
    with c4:
        kpi_card(
            "Sin dispositivo",
            metricas["software_sin_dispositivo"],
            icon="ti ti-alert-circle",
            color="red" if metricas["software_sin_dispositivo"] else "green",
            delta="Revisar" if metricas["software_sin_dispositivo"] else "Todo ok",
            delta_color="#EF4444" if metricas["software_sin_dispositivo"] else "#10B981",
        )

    st.markdown("<div style='margin-top:24px;'></div>", unsafe_allow_html=True)

    # ── Estado por departamento + Importaciones recientes ────────
    col_dept, col_imports = st.columns([1, 1], gap="medium")

    with col_dept:
        st.markdown(
            "<h3 style='margin-bottom:12px;'>Estado por departamento</h3>",
            unsafe_allow_html=True,
        )
        if departamentos:
            dept_rows = []
            for dept in departamentos:
                badge_text = estado_importacion(dept["ultima_importacion"])
                variant = (
                    "success" if "🟢" in badge_text
                    else "warning" if "🟡" in badge_text
                    else "danger"
                )
                clean_status = badge_text.replace("🟢 ", "").replace("🟡 ", "").replace("🔴 ", "")
                dept_rows.append({
                    "Departamento": dept["departamento"],
                    "Equipos": dept["equipos_activos"],
                    "Software": dept["software_visible"],
                    "Última importación": str(dept["ultima_importacion"] or "—"),
                    "Estado": clean_status,
                })
            st.dataframe(
                pd.DataFrame(dept_rows),
                hide_index=True,
                use_container_width=True,
                height=240,
            )
        else:
            empty_state("Sin departamentos", "No hay departamentos configurados.", "ti ti-building-off")

    with col_imports:
        st.markdown(
            "<h3 style='margin-bottom:12px;'>Alertas de importación</h3>",
            unsafe_allow_html=True,
        )
        alertas = [
            {
                "Equipo": row["nombre"],
                "Departamento": row["departamento_nombre"],
                "Última importación": str(row["ultima_importacion"] or "—"),
                "Días": row["dias_desde_importacion"] or "—",
                "Responsable": row.get("responsable") or "—",
            }
            for row in equipos_estado
            if row["dias_desde_importacion"] is None
            or row["dias_desde_importacion"] > 30
            or not row.get("responsable")
        ]
        if alertas:
            st.dataframe(
                pd.DataFrame(alertas[:50]),
                hide_index=True,
                use_container_width=True,
                height=240,
            )
        else:
            empty_state("Sin alertas", "Todas las importaciones están al día.", "ti ti-circle-check")

    st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)

    # ── Exportar todo ────────────────────────────────────────────
    with get_engine().connect() as db:
        excel_completo = generar_excel_completo(db)
    st.download_button(
        "Exportar inventario completo",
        data=excel_completo,
        file_name=f"Inventario_Asserta_{date.today().isoformat()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


navigation = st.navigation(
    {
        "Inicio": [
            st.Page(dashboard, title="Dashboard", url_path="dashboard", icon=":material/dashboard:"),
        ],
        "Inventario de software": [
            st.Page("pages/1_Inventario_de_software.py", title="Resumen", icon=":material/apps:"),
            st.Page("pages/10_Direccion.py", title="Dirección", icon=":material/corporate_fare:"),
            st.Page("pages/11_IT.py", title="IT", icon=":material/terminal:"),
            st.Page("pages/12_Silicon.py", title="Silicon", icon=":material/memory:"),
            st.Page("pages/13_Data_Science.py", title="Data Science", icon=":material/analytics:"),
            st.Page("pages/14_Administracion.py", title="Administración", icon=":material/admin_panel_settings:"),
            st.Page("pages/15_Servidores.py", title="Servidores", icon=":material/dns:"),
        ],
        "Gestión": [
            st.Page("pages/2_Estado_Importaciones.py", title="Importaciones", icon=":material/sync:"),
            st.Page("pages/3_Software_Empresa.py", title="Software empresa", icon=":material/business:"),
            st.Page("pages/4_Calidad_Datos.py", title="Calidad de datos", icon=":material/verified:"),
            st.Page("pages/5_Equipos.py", title="Equipos", icon=":material/devices:"),
            st.Page("pages/6_Software_Autorizado.py", title="Autorizado", icon=":material/shield:"),
        ],
    }
)
navigation.run()
