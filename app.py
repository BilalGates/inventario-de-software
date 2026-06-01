from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from database.connection import get_engine
from modules.equipos import estado_importacion, listar_estado_importaciones
from modules.exportacion import generar_excel_completo
from modules.software import dashboard_metricas, estado_departamentos


st.set_page_config(page_title="Inventario Software Asserta", layout="wide")
st.session_state.setdefault("departamento_id", None)
st.session_state.setdefault("departamento_nombre", None)


def dashboard() -> None:
    st.title("Inventario Software Asserta")

    try:
        with get_engine().connect() as db:
            metricas = dashboard_metricas(db)
            departamentos = estado_departamentos(db)
            equipos_estado = listar_estado_importaciones(db)
    except Exception as exc:
        st.error("No se pudo conectar con MySQL.")
        st.exception(exc)
        st.stop()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Equipos activos", metricas["equipos_activos"])
    col2.metric("Software activo", metricas["software_activo"])
    col3.metric("Importaciones este mes", metricas["importaciones_mes"])
    if metricas["autorizado_pendiente_promocion"] > 0:
        col4.metric(
            "Autorizados a revisar",
            metricas["autorizado_pendiente_promocion"],
            delta="Mover a inventario",
            delta_color="inverse",
        )
    else:
        col4.metric(
            "Software sin dispositivo",
            metricas["software_sin_dispositivo"],
            delta="Revisar" if metricas["software_sin_dispositivo"] else None,
            delta_color="inverse",
        )

    st.subheader("Estado por departamento")
    dept_rows = []
    for dept in departamentos:
        dept_rows.append(
            {
                "Departamento": dept["departamento"],
                "Equipos activos": dept["equipos_activos"],
                "Software visible": dept["software_visible"],
                "Última importación": dept["ultima_importacion"],
                "Estado": estado_importacion(dept["ultima_importacion"]),
            }
        )
    st.dataframe(pd.DataFrame(dept_rows), hide_index=True, use_container_width=True)

    st.subheader("Alertas activas")
    alertas = [
        {
            "Equipo": row["nombre"],
            "Departamento": row["departamento_nombre"],
            "Última importación": row["ultima_importacion"],
            "Estado": row["estado_importacion"],
            "Responsable": row.get("responsable") or "",
        }
        for row in equipos_estado
        if row["dias_desde_importacion"] is None
        or row["dias_desde_importacion"] > 30
        or not row.get("responsable")
    ]

    if alertas:
        st.dataframe(pd.DataFrame(alertas[:50]), hide_index=True, use_container_width=True)
        if len(alertas) > 50:
            st.caption(f"Mostrando 50 de {len(alertas)} alertas.")
    else:
        st.success("No hay alertas activas.")

    st.divider()
    with get_engine().connect() as db:
        excel_completo = generar_excel_completo(db)
    st.download_button(
        "Exportar todo",
        data=excel_completo,
        file_name=f"Inventario_Asserta_Completo_{date.today().isoformat()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# Promocion automatica al iniciar sesion (una vez por sesion)
if not st.session_state.get("_promocion_ejecutada"):
    try:
        with get_engine().begin() as _db:
            from modules.autorizado import promover_todos_los_pendientes

            _result = promover_todos_los_pendientes(_db)
            if _result["total"]:
                st.toast(
                    f"{_result['total']} programa(s) movidos al inventario del departamento "
                    f"({_result['por_antiguedad']} por antiguedad, "
                    f"{_result['por_multidevice']} por multiples dispositivos).",
                    icon="ℹ️",
                )
    except Exception:
        pass
    finally:
        st.session_state["_promocion_ejecutada"] = True


navigation = st.navigation(
    {
        "Inicio": [
            st.Page(dashboard, title="Dashboard", url_path="dashboard"),
        ],
        "Inventario de software": [
            st.Page("pages/1_Inventario_de_software.py", title="Resumen"),
            st.Page("pages/10_Direccion.py", title="Dirección"),
            st.Page("pages/11_IT.py", title="IT"),
            st.Page("pages/12_Silicon.py", title="Silicon"),
            st.Page("pages/13_Data_Science.py", title="Data Science"),
            st.Page("pages/14_Administracion.py", title="Administración"),
            st.Page("pages/15_Servidores.py", title="Servidores"),
        ],
        "Gestión": [
            st.Page("pages/2_Estado_Importaciones.py", title="Estado Importaciones"),
            st.Page("pages/3_Software_Empresa.py", title="Software Empresa"),
            st.Page("pages/4_Calidad_Datos.py", title="Calidad Datos"),
            st.Page("pages/5_Equipos.py", title="Equipos"),
            st.Page("pages/6_Software_Autorizado.py", title="Software Autorizado"),
        ],
    }
)
navigation.run()
