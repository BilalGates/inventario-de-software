from __future__ import annotations

import pandas as pd
import streamlit as st

from database.connection import get_engine
from modules.autorizado import (
    actualizar_autorizado,
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
from utils.theme import apply_theme, sidebar_logo
from utils.ui_components import empty_state, page_header


apply_theme()
sidebar_logo()

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
    st.error("No se pudo cargar software autorizado.")
    st.exception(exc)
    st.stop()

if pendientes_promocion > 0:
    st.warning(
        f"**{pendientes_promocion} programa(s)** deben pasar al inventario del departamento "
        f"(instalados en 2+ dispositivos o con mas de 3 meses de antiguedad). "
        f"Pulsa el boton para actualizarlos."
    )
    if st.button("Mover al inventario de departamento", type="primary"):
        with get_engine().begin() as db:
            resultado = promover_todos_los_pendientes(db)
        st.success(
            f"Movidos al inventario: {resultado['total']} "
            f"({resultado['por_antiguedad']} por antiguedad, "
            f"{resultado['por_multidevice']} por multiples dispositivos)."
        )
        st.rerun()

df = pd.DataFrame(grouped_rows)
if df.empty:
    empty_state("Sin software autorizado", "No hay software autorizado registrado.", "ti ti-shield-off")
else:
    display = df.rename(
        columns={
            "nombre": "Programa",
            "fabricantes": "Fabricante",
            "versiones": "Versiones",
            "departamentos": "Departamentos",
            "equipos_usuarios": "Equipos / Usuarios",
            "n_dispositivos": "Dispositivos",
            "observaciones": "Observaciones",
            "fecha_reciente": "Última autorización",
        }
    )
    st.dataframe(
        display[
            [
                "Programa",
                "Fabricante",
                "Versiones",
                "Departamentos",
                "Equipos / Usuarios",
                "Dispositivos",
                "Observaciones",
                "Última autorización",
            ]
        ],
        hide_index=True,
        use_container_width=True,
        column_config={
            "Dispositivos": st.column_config.NumberColumn("Dispositivos", format="%d"),
        },
    )

with st.expander("Añadir software autorizado"):
    dept_options = {"Sin departamento": None} | {dept["nombre"]: dept["id"] for dept in departamentos}
    equipo_options = {"Texto libre": None} | {f"{eq['nombre']} (id {eq['id']})": eq["id"] for eq in all_equipos}
    with st.form("add_autorizado"):
        nombre = st.text_input("Nombre")
        fabricante = st.text_input("Fabricante")
        tipo = st.text_input("Tipo")
        version = st.text_input("Versión")
        departamento_label = st.selectbox("Departamento", list(dept_options.keys()))
        equipo_label = st.selectbox("Equipo", list(equipo_options.keys()))
        usuario_texto = None
        if equipo_label == "Texto libre":
            usuario_texto = st.text_input("Equipo o usuario")
        observaciones = st.text_area("Observaciones")
        if st.form_submit_button("Guardar"):
            if not nombre.strip():
                st.error("El nombre es obligatorio.")
            else:
                with get_engine().begin() as db:
                    crear_autorizado(
                        db,
                        {
                            "departamento_id": dept_options[departamento_label],
                            "nombre": nombre.strip(),
                            "fabricante": fabricante.strip() or None,
                            "tipo": tipo.strip() or None,
                            "version": version.strip() or None,
                            "equipo_id": equipo_options[equipo_label],
                            "usuario_texto": usuario_texto.strip() if usuario_texto else None,
                            "observaciones": observaciones.strip() or None,
                        },
                    )
                st.success("Software autorizado añadido.")
                st.rerun()

if grouped_rows:
    st.subheader("Detalle y edición")
    group_options = {
        f"{row['nombre']} ({row.get('n_dispositivos', 0)} dispositivos)": row["grupo"]
        for row in grouped_rows
    }
    selected_label = st.selectbox("Programa autorizado", list(group_options.keys()))
    selected_group = group_options[selected_label]
    with get_engine().connect() as db:
        detail_rows = listar_autorizado_detalle_grupo(db, selected_group)
    detail_df = pd.DataFrame(
        [
            {
                "_id": row["id"],
                "Programa": row.get("nombre_visible"),
                "Fabricante": row.get("fabricante_visible"),
                "Tipo": row.get("tipo"),
                "Versión": row.get("version_visible"),
                "Departamento": row.get("departamento_nombre"),
                "Equipo/Usuario": row.get("equipo_nombre") or row.get("usuario_texto"),
                "Observaciones": row.get("observaciones"),
                "Fecha": row.get("fecha_autorizacion") or row.get("fecha_alta"),
            }
            for row in detail_rows
        ]
    )
    edited = st.data_editor(
        detail_df,
        hide_index=True,
        use_container_width=True,
        disabled=["_id", "Departamento", "Equipo/Usuario", "Fecha"],
        column_config={"_id": None},
        key=f"editor_autorizado_{selected_group}",
    )
    if st.button("Guardar cambios del detalle"):
        original_by_id = {row["id"]: row for row in detail_rows}
        updated = 0
        with get_engine().begin() as db:
            for item in edited.to_dict("records"):
                row_id = int(item["_id"])
                original = original_by_id[row_id]
                values = {
                    "nombre": item.get("Programa") or original.get("nombre"),
                    "fabricante": item.get("Fabricante") or None,
                    "tipo": item.get("Tipo") or None,
                    "version": item.get("Versión") or None,
                    "observaciones": item.get("Observaciones") or None,
                }
                if any(str(values[key] or "") != str(original.get(key) or original.get(f"{key}_visible") or "") for key in values):
                    actualizar_autorizado(db, row_id, values)
                    updated += 1
        st.success(f"Registros actualizados: {updated}")
        st.rerun()

    detail_labels = {f"{row['nombre_visible']} - {row.get('version_visible') or 'sin versión'} (id {row['id']})": row["id"] for row in detail_rows}
    selected_detail = st.selectbox("Registro individual a archivar", list(detail_labels.keys()))
    col_one, col_group = st.columns(2)
    with col_one:
        key = f"confirm_archive_aut_{detail_labels[selected_detail]}"
        if not st.session_state.get(key):
            if st.button("Archivar registro individual"):
                st.session_state[key] = True
                st.rerun()
        else:
            st.warning("Pulsa de nuevo para confirmar el archivo del registro.")
            if st.button("Confirmar archivo individual"):
                with get_engine().begin() as db:
                    eliminar_autorizado(db, detail_labels[selected_detail])
                st.session_state[key] = False
                st.success("Registro archivado.")
                st.rerun()
    with col_group:
        group_key = f"confirm_archive_group_{selected_group}"
        if not st.session_state.get(group_key):
            if st.button("Archivar programa completo"):
                st.session_state[group_key] = True
                st.rerun()
        else:
            st.warning("Pulsa de nuevo para confirmar el archivo de todo el grupo.")
            if st.button("Confirmar archivo del grupo"):
                with get_engine().begin() as db:
                    archived = eliminar_autorizado_grupo(db, selected_group)
                st.session_state[group_key] = False
                st.success(f"Registros archivados: {archived}")
                st.rerun()
