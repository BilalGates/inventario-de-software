from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from database.connection import get_engine
from modules.equipos import (
    actualizar_usuario_dispositivo,
    alertas_equipo,
    crear_equipo,
    dar_baja_equipo,
    estado_importacion,
    exportar_equipos_excel,
    existe_equipo,
    importar_equipos_desde_lista,
    listar_equipos,
)
from modules.importacion import ultima_importacion_por_equipos, ultimas_importaciones_por_equipo
from modules.software import listar_departamentos
from utils.parser import parse_equipos_file, parse_equipos_paste
from utils.theme import apply_theme, sidebar_logo
from utils.ui_components import empty_state, page_header


apply_theme()
sidebar_logo()

page_header("Equipos", "Gestión global de todos los dispositivos de la empresa.")

try:
    with get_engine().connect() as db:
        departamentos = listar_departamentos(db)
        equipos = listar_equipos(db, es_servidor=False)
        latest_imports = ultima_importacion_por_equipos(db, [equipo["id"] for equipo in equipos])
except Exception as exc:
    st.error("No se pudo cargar la información de equipos.")
    st.exception(exc)
    st.stop()

dept_options = {dept["nombre"]: dept["id"] for dept in departamentos}

col1, col2 = st.columns(2)
with col1:
    dept_filter = st.multiselect("Departamento", list(dept_options.keys()))
with col2:
    texto = st.text_input("Buscar dispositivo o usuario")

filtered = equipos
if dept_filter:
    selected_ids = {dept_options[name] for name in dept_filter}
    filtered = [eq for eq in filtered if eq["departamento_id"] in selected_ids]
if texto.strip():
    needle = texto.strip().lower()
    filtered = [
        eq
        for eq in filtered
        if needle in (eq.get("nombre") or "").lower()
        or needle in (eq.get("notas") or "").lower()
        or needle in (eq.get("departamento_nombre") or "").lower()
    ]

if filtered:
    rows = []
    for equipo in filtered:
        latest = latest_imports.get(equipo["id"], {})
        rows.append(
            {
                **equipo,
                "ultima_importacion": latest.get("fecha_importacion"),
                "import_total": latest.get("n_total"),
                "import_nuevos": latest.get("n_nuevos"),
                "import_actualizados": latest.get("n_actualizados"),
                "import_eliminados": latest.get("n_eliminados"),
                "import_cambios_version": latest.get("n_cambios_version"),
            }
        )
    display = pd.DataFrame(rows).rename(
        columns={
            "departamento_nombre": "Departamento",
            "nombre": "Dispositivo",
            "notas": "Usuario del dispositivo",
            "ultima_importacion": "Última importación",
            "import_total": "Total",
            "import_nuevos": "Nuevos",
            "import_actualizados": "Actualizados",
            "import_eliminados": "Eliminados",
            "import_cambios_version": "Cambios versión",
        }
    )
    display["Activo"] = display["activo"].map(lambda value: "Sí" if value else "No")
    display["Estado importación"] = display["Última importación"].map(estado_importacion)
    st.dataframe(
        display[
            [
                "Departamento",
                "Dispositivo",
                "Usuario del dispositivo",
                "Última importación",
                "Estado importación",
                "Total",
                "Nuevos",
                "Actualizados",
                "Eliminados",
                "Cambios versión",
                "fecha_alta",
                "fecha_baja",
            ]
        ],
        hide_index=True,
        use_container_width=True,
    )
else:
    empty_state("Sin equipos", "No hay dispositivos que coincidan con los filtros.", "ti ti-device-laptop-off")

if filtered:
    export_name = f"Inventario_Equipos_Empresa_{date.today().isoformat()}.xlsx"
    data = exportar_equipos_excel(filtered, "Equipos")
    st.download_button(
        "Exportar equipos a Excel",
        data=data,
        file_name=export_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

with st.expander("Agregar dispositivo"):
    with st.form("add_equipo_global"):
        departamento_label = st.selectbox("Departamento", list(dept_options.keys()))
        nombre = st.text_input("Nombre del dispositivo")
        usuario = st.text_input("Usuario del dispositivo")
        submitted = st.form_submit_button("Guardar")
        if submitted:
            if not nombre.strip():
                st.error("El nombre del dispositivo es obligatorio.")
            else:
                departamento_id = dept_options[departamento_label]
                created = False
                with get_engine().begin() as db:
                    if existe_equipo(db, departamento_id, nombre):
                        st.error("Ya existe un dispositivo con ese nombre en ese departamento.")
                    else:
                        crear_equipo(db, departamento_id, nombre, usuario.strip() or None)
                        created = True
                if created:
                    st.success("Dispositivo agregado.")
                    st.rerun()

with st.expander("Importar dispositivos desde datos"):
    tab_paste, tab_file = st.tabs(["Pegar texto", "Subir fichero"])
    parsed: list[dict] | None = None
    with tab_paste:
        import_texto = st.text_area(
            "Pega los datos aquí (separados por tabulaciones)",
            height=200,
            placeholder="Nº\tNombre del Equipo\tTipo de Dispositivo\tSistema Operativo\tProcesador\tMemoria RAM\tAlmacenamiento\tDepartamento\tUbicación Física\tEstado\tObservaciones\tCoste\tFecha de Adquisición",
        )
        if st.button("Analizar texto", key="analyze_paste"):
            if not import_texto.strip():
                st.warning("Pega los datos primero.")
            else:
                parsed = parse_equipos_paste(import_texto)
    with tab_file:
        uploaded = st.file_uploader("Subir fichero CSV o XLSX", type=["csv", "xlsx"], key="file_equipos")
        if uploaded and st.button("Analizar fichero", key="analyze_file"):
            parsed = parse_equipos_file(uploaded.getvalue(), uploaded.name)
    if parsed is not None:
        if not parsed:
            st.warning("No se pudieron extraer datos.")
        else:
            st.success(f"Se han detectado {len(parsed)} dispositivos.")
            st.dataframe(pd.DataFrame(parsed), hide_index=True, use_container_width=True)
            if st.button("Importar dispositivos", type="primary"):
                with get_engine().begin() as db:
                    depts = listar_departamentos(db)
                    resultado = importar_equipos_desde_lista(db, parsed, depts, es_servidor=False)
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

if filtered:
    labels = {f"{eq['departamento_nombre']} - {eq['nombre']} (id {eq['id']})": eq for eq in filtered}
    selected_label = st.selectbox("Editar o eliminar dispositivo", list(labels.keys()))
    selected = labels[selected_label]

    with st.expander("Ficha del equipo", expanded=True):
        st.subheader(selected["nombre"])
        col_hw1, col_hw2 = st.columns(2)
        with col_hw1:
            st.write("**Hardware**")
            st.write(f"Tipo: {selected.get('tipo_dispositivo') or '-'}")
            st.write(f"Marca / Modelo: {selected.get('marca_modelo') or '-'}")
            st.write(f"Nº de serie: {selected.get('num_serie') or '-'}")
            st.write(f"Dirección MAC: {selected.get('mac_address') or '-'}")
            st.write(f"Sistema operativo: {selected.get('sistema_operativo') or '-'}")
            st.write(f"Procesador: {selected.get('procesador') or '-'}")
            st.write(f"RAM: {selected.get('ram') or '-'}")
            st.write(f"Almacenamiento: {selected.get('almacenamiento') or '-'}")
        with col_hw2:
            st.write("**Responsabilidad y actividad**")
            st.write(f"Responsable: {selected.get('responsable') or '-'}")
            st.write(f"Usuario: {selected.get('notas') or '-'}")
            st.write(f"Ubicación: {selected.get('ubicacion') or '-'}")
            st.write(f"Coste: {selected.get('coste') or '-'}")
            st.write(f"Fecha adquisición: {selected.get('fecha_adquisicion') or '-'}")
            st.write(f"Última importación: {selected.get('ultima_importacion') or '-'}")
            st.write(f"Estado importación: {estado_importacion(selected.get('ultima_importacion'))}")
            st.write(f"Software activo instalado: {selected.get('total_software_activo') or 0}")
        alerts = alertas_equipo(selected)
        if alerts:
            st.write("**Alertas**")
            for alert in alerts:
                st.warning(alert)
        else:
            st.success("Sin alertas activas.")

    with get_engine().connect() as db:
        recent_imports = ultimas_importaciones_por_equipo(db, selected["id"], limit=5)
    with st.expander("Últimas importaciones del dispositivo"):
        if recent_imports:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Fecha": row["fecha_importacion"],
                            "Método": row["metodo"],
                            "Total": row["n_total"],
                            "Nuevos": row["n_nuevos"],
                            "Actualizados": row["n_actualizados"],
                            "Eliminados": row["n_eliminados"],
                            "Cambios versión": row["n_cambios_version"],
                        }
                        for row in recent_imports
                    ]
                ),
                hide_index=True,
                use_container_width=True,
            )
        else:
            empty_state("Sin importaciones", "No hay importaciones registradas para este dispositivo.", "ti ti-database-off")

    with st.form("edit_equipo_global"):
        usuario = st.text_input("Usuario del dispositivo", value=selected.get("notas") or "")
        if st.form_submit_button("Guardar usuario"):
            with get_engine().begin() as db:
                actualizar_usuario_dispositivo(db, selected["id"], usuario.strip() or None)
            st.success("Usuario actualizado.")
            st.rerun()

    confirm_key = f"confirm_baja_equipo_{selected['id']}"
    if selected["activo"]:
        if not st.session_state.get(confirm_key):
            if st.button("Eliminar dispositivo"):
                st.session_state[confirm_key] = True
                st.rerun()
        else:
            st.warning("Pulsa de nuevo para confirmar. El dispositivo se marcará como inactivo, no se borrará el histórico.")
            if st.button("Confirmar eliminación"):
                with get_engine().begin() as db:
                    dar_baja_equipo(db, selected["id"])
                st.session_state[confirm_key] = False
                st.success("Dispositivo eliminado del listado activo.")
                st.rerun()
    else:
        st.info("Este dispositivo ya está inactivo.")
