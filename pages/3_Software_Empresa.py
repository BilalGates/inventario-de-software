from __future__ import annotations

import pandas as pd
import streamlit as st

from database.connection import get_engine
from modules.equipos import listar_equipos
from modules.software import listar_departamentos, listar_inventario_empresa
from utils.theme import apply_theme, sidebar_logo
from utils.ui_components import empty_state, page_header


apply_theme()
sidebar_logo()

page_header("Software de la empresa", "Visión global de todo el software registrado")


def _paginate(df: pd.DataFrame, key: str, page_size: int = 25) -> pd.DataFrame:
    if len(df) <= 50:
        return df
    page_key = f"page_{key}"
    max_page = max((len(df) - 1) // page_size, 0)
    st.session_state[page_key] = min(st.session_state.get(page_key, 0), max_page)
    col_prev, col_info, col_next = st.columns([1, 2, 1])
    with col_prev:
        if st.button("Anterior", key=f"prev_{key}", disabled=st.session_state[page_key] <= 0):
            st.session_state[page_key] -= 1
            st.rerun()
    with col_info:
        st.caption(f"Pagina {st.session_state[page_key] + 1} de {max_page + 1}")
    with col_next:
        if st.button("Siguiente", key=f"next_{key}", disabled=st.session_state[page_key] >= max_page):
            st.session_state[page_key] += 1
            st.rerun()
    start = st.session_state[page_key] * page_size
    return df.iloc[start : start + page_size]

try:
    with get_engine().connect() as db:
        departamentos = listar_departamentos(db)
        equipos = []
        for dept in departamentos:
            equipos.extend(listar_equipos(db, dept["id"], solo_activos=True))
except Exception as exc:
    st.error("No se pudo cargar el inventario global.")
    st.exception(exc)
    st.stop()

dept_options = {dept["nombre"]: dept["id"] for dept in departamentos}
equipo_options = {f"{eq['nombre']} ({eq['departamento_id']})": eq["id"] for eq in equipos}

col1, col2, col3 = st.columns([2, 2, 1])
with col1:
    selected_depts = st.multiselect("Departamentos", list(dept_options.keys()))
with col2:
    selected_equipos = st.multiselect("Dispositivos", list(equipo_options.keys()))
with col3:
    vista = st.radio("Vista", ["Básica", "Detallada"], horizontal=True)
solo_comun = st.checkbox("Solo software común", value=False)
texto = st.text_input("Buscar software...")

with get_engine().connect() as db:
    rows = listar_inventario_empresa(
        db,
        departamento_ids=[dept_options[name] for name in selected_depts],
        equipo_ids=[equipo_options[name] for name in selected_equipos],
        solo_comun=solo_comun,
        texto_libre=texto or None,
    )

df = pd.DataFrame(rows)
if df.empty:
    empty_state("Sin software", "No hay software que coincida con los filtros.", "ti ti-apps-off")
else:
    display = df[
        [
            "nombre",
            "fabricantes",
            "versiones",
            "departamentos",
            "dispositivos",
            "clasificaciones",
            "en_guia_105",
            "observaciones",
            "fecha_ultima_actualizacion",
            "n_departamentos",
        ]
    ].copy()
    display["en_guia_105"] = display["en_guia_105"].map(lambda value: "Pendiente" if pd.isna(value) else ("Sí" if bool(value) else "No"))
    display = display.rename(
        columns={
            "nombre": "Programa",
            "fabricantes": "Fabricante",
            "versiones": "Versión",
            "departamentos": "Departamentos",
            "dispositivos": "Dispositivos",
            "clasificaciones": "Clasificación",
            "en_guia_105": "Guía 105",
            "observaciones": "Observaciones",
            "fecha_ultima_actualizacion": "Última actualización",
            "n_departamentos": "Nº departamentos",
        }
    )
    fixed = ["Programa", "Fabricante", "Versión", "Dispositivos", "Última actualización"]
    detail = ["Departamentos", "Nº departamentos", "Clasificación", "Guía 105", "Observaciones"]
    columns = fixed + (detail if vista == "Detallada" else [])
    st.dataframe(_paginate(display[columns], "software_empresa"), hide_index=True, use_container_width=True)
