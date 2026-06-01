from __future__ import annotations

import pandas as pd
import streamlit as st

from database.connection import get_engine
from modules.autorizado import autorizar_softwares
from modules.software import (
    actualizar_fabricante,
    fabricantes_vacios,
    software_comun_no_autorizado,
    versiones_sospechosas,
)


st.title("Calidad de datos")

try:
    with get_engine().connect() as db:
        suspicious_versions = versiones_sospechosas(db)
        empty_manufacturers = fabricantes_vacios(db)
        common_not_authorized = software_comun_no_autorizado(db)
except Exception as exc:
    st.error("No se pudo cargar el reporte de calidad.")
    st.exception(exc)
    st.stop()

tab_versions, tab_manufacturers, tab_common = st.tabs(
    ["Versiones sospechosas", "Fabricantes vacios", "Software comun no autorizado"]
)

with tab_versions:
    if suspicious_versions:
        st.dataframe(
            pd.DataFrame(suspicious_versions).rename(
                columns={
                    "nombre": "Programa",
                    "version_referencia": "Version",
                    "fabricante": "Fabricante",
                }
            )[["Programa", "Version", "Fabricante"]],
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.success("No se han detectado versiones sospechosas.")

with tab_manufacturers:
    if not empty_manufacturers:
        st.success("No hay fabricantes vacios.")
    else:
        st.dataframe(
            pd.DataFrame(empty_manufacturers).rename(
                columns={
                    "nombre": "Programa",
                    "version_referencia": "Version",
                    "fabricante": "Fabricante",
                }
            )[["Programa", "Version", "Fabricante"]],
            hide_index=True,
            use_container_width=True,
        )
        labels = {
            f"{row['nombre']} - {row.get('version_referencia') or 'sin version'} (id {row['id']})": row
            for row in empty_manufacturers
        }
        selected_label = st.selectbox("Software a editar", list(labels.keys()))
        selected = labels[selected_label]
        with st.form("edit_fabricante"):
            fabricante = st.text_input("Fabricante", value=selected.get("fabricante") or "")
            if st.form_submit_button("Guardar fabricante"):
                with get_engine().begin() as db:
                    actualizar_fabricante(db, selected["id"], fabricante.strip() or None)
                st.success("Fabricante actualizado.")
                st.rerun()

with tab_common:
    if not common_not_authorized:
        st.success("No hay software comun pendiente de autorizacion.")
    else:
        st.dataframe(
            pd.DataFrame(common_not_authorized).rename(
                columns={
                    "nombre": "Programa",
                    "n_departamentos": "Departamentos",
                }
            )[["Programa", "Departamentos"]],
            hide_index=True,
            use_container_width=True,
        )
        motivo = "Autorizado desde calidad de datos: software comun en mas de 3 departamentos"
        labels = {
            f"{row['nombre']} ({row['n_departamentos']} departamentos)": row["software_id"]
            for row in common_not_authorized
        }
        selected_label = st.selectbox("Software a autorizar", list(labels.keys()))
        confirm_key = f"confirm_autorizar_{labels[selected_label]}"
        if not st.session_state.get(confirm_key):
            if st.button("Autorizar software seleccionado"):
                st.session_state[confirm_key] = True
                st.rerun()
        else:
            st.warning(
                f"¿Confirmas la autorización de **{selected_label}**? "
                f"Esta acción no se puede deshacer fácilmente."
            )
            if st.button("Confirmar autorización", type="primary"):
                with get_engine().begin() as db:
                    inserted = autorizar_softwares(db, [labels[selected_label]], motivo)
                st.session_state[confirm_key] = False
                st.success(f"Software autorizado añadido: {inserted}")
                st.rerun()
