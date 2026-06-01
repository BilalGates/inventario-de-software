from __future__ import annotations

import pandas as pd
import streamlit as st

from database.connection import get_engine
from modules.equipos import listar_estado_importaciones
from modules.software import listar_departamentos
from utils.theme import apply_theme, sidebar_logo
from utils.ui_components import empty_state, page_header


apply_theme()
sidebar_logo()

page_header("Estado de importaciones", "Monitoreo de importaciones por equipo")

try:
    with get_engine().connect() as db:
        departamentos = listar_departamentos(db)
        rows = listar_estado_importaciones(db)
except Exception as exc:
    st.error("No se pudo cargar el estado de importaciones.")
    st.exception(exc)
    st.stop()

dept_options = {"Todos": None} | {dept["nombre"]: dept["id"] for dept in departamentos}
col_dept, col_state = st.columns(2)
with col_dept:
    selected_dept = st.selectbox("Departamento", list(dept_options.keys()))
with col_state:
    selected_state = st.selectbox("Estado", ["Todos", "Solo pendientes (>30 dias)", "Nunca importados"])

filtered = rows
departamento_id = dept_options[selected_dept]
if departamento_id is not None:
    filtered = [row for row in filtered if row["departamento_id"] == departamento_id]
if selected_state == "Solo pendientes (>30 dias)":
    filtered = [
        row
        for row in filtered
        if row["dias_desde_importacion"] is None or row["dias_desde_importacion"] > 30
    ]
elif selected_state == "Nunca importados":
    filtered = [row for row in filtered if row["dias_desde_importacion"] is None]

total = len(filtered)
al_dia = len([row for row in filtered if row["dias_desde_importacion"] is not None and row["dias_desde_importacion"] < 30])
pendientes = len([row for row in filtered if row["dias_desde_importacion"] is not None and row["dias_desde_importacion"] >= 30])
nunca = len([row for row in filtered if row["dias_desde_importacion"] is None])

metric_cols = st.columns(4)
metric_cols[0].metric("Total equipos", total)
metric_cols[1].metric("Al dia", al_dia)
metric_cols[2].metric("Pendientes", pendientes)
metric_cols[3].metric("Nunca importados", nunca)

display = pd.DataFrame(
    [
        {
            "Equipo": row["nombre"],
            "Departamento": row["departamento_nombre"],
            "Ultima importacion": row["ultima_importacion"],
            "Dias desde ultima importacion": row["dias_desde_importacion"],
            "Estado": row["estado_importacion"],
        }
        for row in filtered
    ]
)

if display.empty:
    empty_state("Sin resultados", "No hay equipos que coincidan con los filtros.", "ti ti-device-laptop-off")
else:
    st.dataframe(display, hide_index=True, use_container_width=True)
