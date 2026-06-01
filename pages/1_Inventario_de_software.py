from __future__ import annotations

import pandas as pd
import streamlit as st

from database.connection import get_engine
from modules.software import listar_departamentos_con_estadisticas


st.title("Inventario de software")
st.caption("Selecciona un departamento para abrir su inventario dedicado.")

DEPARTMENT_PAGES = {
    "gerencia": "pages/10_Direccion.py",
    "it": "pages/11_IT.py",
    "silicon": "pages/12_Silicon.py",
    "data_science": "pages/13_Data_Science.py",
    "administracion": "pages/14_Administracion.py",
    "servidores": "pages/15_Servidores.py",
}

try:
    with get_engine().connect() as db:
        departamentos = listar_departamentos_con_estadisticas(db)
except Exception as exc:
    st.error("No se pudo conectar con MySQL.")
    st.exception(exc)
    st.stop()

if not departamentos:
    st.info("No hay departamentos registrados.")
    st.stop()

cols = st.columns(3)
for idx, dept in enumerate(departamentos):
    with cols[idx % 3]:
        with st.container(border=True):
            st.subheader(dept["nombre"])
            st.metric("Dispositivos activos", dept["n_equipos"])
            st.metric("Software visible", dept["n_software"])
            if st.button("Abrir inventario", key=f"open_dept_{dept['id']}", use_container_width=True):
                st.session_state["departamento_id"] = dept["id"]
                st.session_state["departamento_nombre"] = dept["nombre"]
                st.switch_page(DEPARTMENT_PAGES[dept["codigo"]])

st.divider()
st.subheader("Resumen")
st.dataframe(
    pd.DataFrame(
        [
            {
                "Departamento": dept["nombre"],
                "Dispositivos activos": dept["n_equipos"],
                "Software visible": dept["n_software"],
            }
            for dept in departamentos
        ]
    ),
    hide_index=True,
    use_container_width=True,
)
