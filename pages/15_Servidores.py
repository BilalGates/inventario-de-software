from __future__ import annotations

import pandas as pd
import streamlit as st

from database.connection import get_engine
from modules.departamento_page import render_departamento_page
from modules.equipos import (
    actualizar_usuario_dispositivo,
    alertas_equipo,
    crear_equipo,
    dar_baja_equipo,
    estado_importacion,
    existe_equipo,
    exportar_equipos_excel,
    importar_equipos_desde_lista,
    listar_equipos,
)
from modules.software import listar_departamentos
from utils.parser import parse_equipos_file, parse_equipos_paste
from utils.theme import apply_theme, sidebar_logo
from utils.ui_components import empty_state


apply_theme()
sidebar_logo()

render_departamento_page("servidores")


st.subheader("Dispositivos del tipo Servidor")

with get_engine().connect() as db:
    servidores = listar_equipos(db, es_servidor=True)
    departamentos = listar_departamentos(db)

if not servidores:
    empty_state("Sin servidores", "No hay servidores registrados.", "ti ti-server-off")
else:
    display = pd.DataFrame(servidores).rename(
        columns={
            "nombre": "Nombre del Equipo",
            "tipo_dispositivo": "Tipo",
            "sistema_operativo": "SO",
            "procesador": "Procesador",
            "ram": "RAM",
            "almacenamiento": "Disco",
            "departamento_nombre": "Departamento",
            "ubicacion": "Ubicación",
            "notas": "Observaciones",
            "coste": "Coste",
            "fecha_adquisicion": "Fecha Adq.",
        }
    )
    display["Estado"] = display["activo"].map(lambda v: "Activo" if v else "Inactivo")
    st.dataframe(display, hide_index=True, use_container_width=True)

    export_data = exportar_equipos_excel(servidores, "Servidores")
    st.download_button(
        "Exportar servidores a Excel",
        data=export_data,
        file_name=f"Inventario_Servidores.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

with st.expander("Agregar servidor manual"):
    with st.form("add_servidor"):
        serv_dept_label = st.selectbox("Departamento", [d["nombre"] for d in departamentos])
        serv_nombre = st.text_input("Nombre del servidor")
        serv_obs = st.text_input("Observaciones")
        if st.form_submit_button("Guardar"):
            if not serv_nombre.strip():
                st.error("El nombre es obligatorio.")
            else:
                dept_id = next(d["id"] for d in departamentos if d["nombre"] == serv_dept_label)
                with get_engine().begin() as db:
                    if existe_equipo(db, dept_id, serv_nombre):
                        st.error("Ya existe un servidor con ese nombre en ese departamento.")
                    else:
                        crear_equipo(db, dept_id, serv_nombre, serv_obs.strip() or None, es_servidor=True)
                        st.success("Servidor agregado.")
                        st.rerun()

with st.expander("Importar servidores desde datos"):
    tab_paste, tab_file = st.tabs(["Pegar texto", "Subir fichero"])
    parsed: list[dict] | None = None
    with tab_paste:
        import_texto = st.text_area(
            "Pega los datos aquí (separados por tabulaciones)",
            height=200,
            placeholder="Nº\tNombre del Equipo\tTipo de Dispositivo\tSistema Operativo\tProcesador\tMemoria RAM\tAlmacenamiento\tDepartamento\tUbicación Física\tEstado\tObservaciones\tCoste\tFecha de Adquisición",
        )
        if st.button("Analizar texto", key="analyze_serv_paste"):
            if not import_texto.strip():
                st.warning("Pega los datos primero.")
            else:
                parsed = parse_equipos_paste(import_texto)
    with tab_file:
        uploaded = st.file_uploader("Subir fichero CSV o XLSX", type=["csv", "xlsx"], key="file_serv")
        if uploaded and st.button("Analizar fichero", key="analyze_serv_file"):
            parsed = parse_equipos_file(uploaded.getvalue(), uploaded.name)
    if parsed is not None:
        if not parsed:
            st.warning("No se pudieron extraer datos.")
        else:
            st.success(f"Se han detectado {len(parsed)} servidores.")
            st.dataframe(pd.DataFrame(parsed), hide_index=True, use_container_width=True)
            if st.button("Importar servidores", type="primary"):
                with get_engine().begin() as db:
                    depts = listar_departamentos(db)
                    resultado = importar_equipos_desde_lista(db, parsed, depts, es_servidor=True)
                st.subheader("Resultado")
                c1, c2, c3 = st.columns(3)
                with c1: st.metric("Creados", resultado["creados"])
                with c2: st.metric("Actualizados", resultado["actualizados"])
                with c3: st.metric("Omitidos", resultado["omitidos"])
                if resultado["errores"]:
                    with st.expander("Errores"):
                        for err in resultado["errores"]:
                            st.warning(err)
                if resultado["creados"] > 0 or resultado["actualizados"] > 0:
                    st.success("Importación completada.")
                    st.rerun()

with st.expander("Ficha del servidor"):
    if not servidores:
        empty_state("Sin servidores", "No hay servidores para mostrar.", "ti ti-server-off")
    else:
        labels = {f"{s['nombre']} (id {s['id']})": s for s in servidores}
        selected_label = st.selectbox("Servidor", list(labels.keys()), key="serv_select")
        selected = labels[selected_label]
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Nombre:** {selected.get('nombre') or '-'}")
            st.write(f"**Tipo:** {selected.get('tipo_dispositivo') or '-'}")
            st.write(f"**SO:** {selected.get('sistema_operativo') or '-'}")
            st.write(f"**Procesador:** {selected.get('procesador') or '-'}")
            st.write(f"**RAM:** {selected.get('ram') or '-'}")
            st.write(f"**Almacenamiento:** {selected.get('almacenamiento') or '-'}")
        with col2:
            st.write(f"**Departamento:** {selected.get('departamento_nombre') or '-'}")
            st.write(f"**Ubicación:** {selected.get('ubicacion') or '-'}")
            st.write(f"**Coste:** {selected.get('coste') or '-'}")
            st.write(f"**Fecha adquisición:** {selected.get('fecha_adquisicion') or '-'}")
            st.write(f"**Estado:** {'Activo' if selected.get('activo') else 'Inactivo'}")
            st.write(f"**Observaciones:** {selected.get('notas') or '-'}")
        alerts = alertas_equipo(selected)
        if alerts:
            for alert in alerts:
                st.warning(alert)
        else:
            st.success("Sin alertas.")
        if selected["activo"]:
            if st.button("Dar de baja", key=f"baja_serv_{selected['id']}"):
                with get_engine().begin() as db:
                    dar_baja_equipo(db, selected["id"])
                st.success("Servidor dado de baja.")
                st.rerun()
