from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from database.connection import get_engine
from modules.autorizado import (
    autorizar_exclusivos_automaticamente,
    autorizar_softwares,
    detectar_autorizados_para_promocion,
    detectar_software_exclusivo,
    promocionar_autorizaciones_generales,
)
from modules.equipos import (
    actualizar_usuario_dispositivo,
    alertas_equipo,
    crear_equipo,
    estado_importacion,
    existe_equipo,
    exportar_equipos_excel,
    listar_equipos,
)
from modules.exportacion import generar_excel, generar_excel_importaciones
from modules.importacion import (
    aplicar_diff,
    calcular_diff,
    contar_reactivaciones_pendientes,
    listar_reactivaciones_pendientes,
    resolver_reactivacion,
    ultima_importacion_por_equipo,
    ultimas_importaciones_por_equipo,
)
from modules.software import (
    actualizar_software_revision,
    contar_software_sin_dispositivos,
    eliminar_software_inventario,
    listar_departamentos_con_estadisticas,
    listar_inventario,
    obtener_departamento,
    ocultar_software_sin_dispositivos,
)
from utils.parser import parse_file, parse_paste


st.session_state.setdefault("departamento_id", None)
st.session_state.setdefault("departamento_nombre", None)


def _bool_filter(label: str, key: str):
    value = st.selectbox(label, ["Todos", "SÃ­", "No", "Pendiente"], key=key)
    return {"Todos": "todos", "SÃ­": True, "No": False, "Pendiente": None}[value]


def _bool_input(label: str, value, key: str):
    reverse = {True: "SÃ­", False: "No", None: "Pendiente", 1: "SÃ­", 0: "No"}
    selected = st.selectbox(
        label,
        ["Pendiente", "SÃ­", "No"],
        index=["Pendiente", "SÃ­", "No"].index(reverse.get(value, "Pendiente")),
        key=key,
    )
    return {"SÃ­": True, "No": False, "Pendiente": None}[selected]


def _paginate(df: pd.DataFrame, key: str, page_size: int = 25) -> pd.DataFrame:
    return df


def _clear_import_state(departamento_id: int) -> None:
    for suffix in ("diff", "programas", "equipo_import", "metodo", "import_equipo", "new_eq", "new_user", "paste", "file"):
        st.session_state.pop(f"{suffix}_{departamento_id}", None)
    nonce_key = f"import_reset_nonce_{departamento_id}"
    st.session_state[nonce_key] = st.session_state.get(nonce_key, 0) + 1


def _format_audit_row(row: dict) -> dict:
    return {
        "Fecha": row.get("fecha_importacion"),
        "MÃ©todo": row.get("metodo"),
        "Total": row.get("n_total"),
        "Nuevos": row.get("n_nuevos"),
        "Actualizados": row.get("n_actualizados"),
        "Eliminados": row.get("n_eliminados"),
        "Cambios versiÃ³n": row.get("n_cambios_version"),
    }


def _render_import_audit(equipo_id: int) -> None:
    with get_engine().connect() as db:
        latest = ultima_importacion_por_equipo(db, equipo_id)
        recent = ultimas_importaciones_por_equipo(db, equipo_id, limit=5)
    if not latest:
        st.info("Sin importaciones registradas para este dispositivo.")
        return
    cols = st.columns(6)
    cols[0].metric("Ãšltima importaciÃ³n", str(latest["fecha_importacion"]))
    cols[1].metric("MÃ©todo", latest["metodo"])
    cols[2].metric("Total", latest["n_total"] or 0)
    cols[3].metric("Nuevos", latest["n_nuevos"] or 0)
    cols[4].metric("Eliminados", latest["n_eliminados"] or 0)
    cols[5].metric("Cambios versiÃ³n", latest["n_cambios_version"] or 0)
    with st.expander("Ãšltimas importaciones"):
        st.dataframe(pd.DataFrame([_format_audit_row(row) for row in recent]), hide_index=True, use_container_width=True)


def _render_exclusive_software(dept: dict) -> None:
    with get_engine().connect() as db:
        candidates = detectar_software_exclusivo(db, dept["id"])
    if not candidates:
        return
    st.subheader("Software exclusivo detectado")
    st.caption("Programas instalados en un Ãºnico dispositivo y todavÃ­a no incluidos en Software Autorizado.")
    df = pd.DataFrame(candidates).rename(
        columns={
            "nombre": "Nombre",
            "version_referencia": "VersiÃ³n",
            "fabricante": "Fabricante",
            "equipo": "Equipo donde estÃ¡ instalado",
        }
    )
    st.dataframe(df[["Nombre", "VersiÃ³n", "Fabricante", "Equipo donde estÃ¡ instalado"]], hide_index=True, use_container_width=True)
    motivo = "Detectado automÃ¡ticamente: instalado en un Ãºnico dispositivo"
    selected_ids = []
    with st.expander("Seleccionar software exclusivo"):
        for item in candidates:
            if st.checkbox(item["nombre"], key=f"exclusive_{dept['id']}_{item['id']}"):
                selected_ids.append(item["id"])
    col_all, col_selected = st.columns(2)
    with col_all:
        if st.button("AÃ±adir todos a software autorizado", key=f"auth_all_{dept['id']}"):
            with get_engine().begin() as db:
                inserted = autorizar_softwares(db, [item["id"] for item in candidates], motivo)
            st.success(f"Software autorizado aÃ±adido: {inserted}")
            st.rerun()
    with col_selected:
        if st.button("AÃ±adir seleccionados", key=f"auth_selected_{dept['id']}", disabled=not selected_ids):
            with get_engine().begin() as db:
                inserted = autorizar_softwares(db, selected_ids, motivo)
            st.success(f"Software autorizado aÃ±adido: {inserted}")
            st.rerun()


def _render_authorization_promotions(dept: dict, candidates: list[dict] | None = None) -> None:
    if candidates is None:
        with get_engine().connect() as db:
            candidates = detectar_autorizados_para_promocion(db, dept["id"])
    if not candidates:
        return
    st.subheader("Software autorizado en 3 o mÃ¡s equipos")
    st.warning(
        "Estos programas estaban autorizados para un equipo concreto, pero ahora aparecen en 3 o mÃ¡s equipos. "
        "Puedes promocionarlos a autorizaciÃ³n general."
    )
    df = pd.DataFrame(candidates).rename(
        columns={
            "nombre": "Nombre",
            "version_referencia": "VersiÃ³n",
            "fabricante": "Fabricante",
            "departamento": "Departamento",
            "n_equipos": "Equipos",
            "equipos": "Equipos donde estÃ¡ instalado",
        }
    )
    st.dataframe(
        df[["Nombre", "VersiÃ³n", "Fabricante", "Departamento", "Equipos", "Equipos donde estÃ¡ instalado"]],
        hide_index=True,
        use_container_width=True,
    )
    confirm = st.checkbox(
        "Confirmo que quiero aplicar este cambio y autorizarlo de forma general",
        key=f"confirm_promote_auth_{dept['id']}",
    )
    if st.button(
        "Aplicar cambio a software autorizado",
        key=f"promote_auth_{dept['id']}",
        disabled=not confirm,
    ):
        motivo = "Promocionado automÃ¡ticamente tras confirmaciÃ³n: instalado en 3 o mÃ¡s equipos"
        with get_engine().begin() as db:
            updated = promocionar_autorizaciones_generales(
                db,
                [item["id"] for item in candidates],
                motivo,
            )
        st.success(f"Autorizaciones actualizadas: {updated}")
        st.rerun()


def _render_cleanup(dept: dict) -> None:
    with get_engine().connect() as db:
        all_counts = contar_software_sin_dispositivos(db)
    dept_count = next((row["total"] for row in all_counts if row["departamento_id"] == dept["id"]), 0)
    if not dept_count:
        st.caption("No hay software activo sin dispositivos en este departamento.")
        return
    with st.expander("Limpieza de software sin dispositivos"):
        detail = ", ".join(f"{row['departamento']}: {row['total']}" for row in all_counts)
        st.warning(
            f"Esta operaciÃ³n ocultarÃ¡ {dept_count} registros de este departamento que no tienen ningÃºn dispositivo asignado. "
            f"Detalle global: {detail}"
        )
        confirm = st.checkbox("Confirmo que quiero ocultar estos registros", key=f"confirm_clean_{dept['id']}")
        if st.button("Ocultar software sin dispositivos", key=f"clean_orphans_{dept['id']}", disabled=not confirm):
            with get_engine().begin() as db:
                hidden = ocultar_software_sin_dispositivos(db, dept["id"])
            st.success(f"Registros ocultados del inventario: {hidden}")
            st.rerun()


def render_inventario(dept: dict) -> None:
    _render_cleanup(dept)
    with get_engine().connect() as db:
        equipos = listar_equipos(db, dept["id"], solo_activos=True)
    equipo_options = {equipo["nombre"]: equipo["id"] for equipo in equipos}
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        texto = st.text_input("Programa", key=f"buscar_{dept['id']}")
    with col2:
        equipo_selected = st.multiselect("Dispositivo", list(equipo_options.keys()), key=f"equipo_filter_{dept['id']}")
    with col3:
        vista = st.radio(
            "Vista",
            ["BÃ¡sica", "Detallada"],
            horizontal=True,
            key=f"vista_inventario_{dept['id']}",
        )
    with get_engine().connect() as db:
        inventario = listar_inventario(
            db,
            dept["id"],
            equipo_ids=[equipo_options[name] for name in equipo_selected],
            en_guia_105="todos",
            texto_libre=texto or None,
        )
    if not inventario:
        st.info("No hay software que coincida con los filtros.")
        return
    rows_by_id = {row["id"]: row for row in inventario}
    display_rows = []
    for row in inventario:
        display_rows.append(
            {
                "_id": row["id"],
                "Archivar": False,
                "ID": row.get("codigo"),
                "Programa": row.get("nombre"),
                "Fabricante": row.get("fabricante"),
                "VersiÃ³n": row.get("version_referencia"),
                "Dispositivos": row.get("dispositivos"),
                "Ãšltima actualizaciÃ³n": row.get("fecha_ultima_actualizacion"),
                "ClasificaciÃ³n": row.get("clasificacion_informacion"),
                "GuÃ­a 105": "Pendiente" if row.get("en_guia_105") is None else ("SÃ­" if row.get("en_guia_105") else "No"),
                "Observaciones": row.get("observaciones"),
            }
        )
    base_cols = ["_id", "Archivar", "ID", "Programa", "Fabricante", "VersiÃ³n", "Dispositivos", "Ãšltima actualizaciÃ³n"]
    detail_cols = ["ClasificaciÃ³n", "GuÃ­a 105", "Observaciones"]
    visible_cols = base_cols + (detail_cols if vista == "Detallada" else [])
    display = pd.DataFrame(display_rows)[visible_cols]
    page_df = _paginate(display, f"inventory_{dept['id']}")
    edited = st.data_editor(
        page_df,
        hide_index=True,
        use_container_width=True,
        disabled=["_id", "ID", "Programa", "Dispositivos", "Ãšltima actualizaciÃ³n"],
        column_config={
            "_id": None,
            "Archivar": st.column_config.CheckboxColumn(
                "Archivar",
                help="Marca esta casilla y guarda para ocultar el registro del inventario.",
                default=False,
            ),
        },
        key=f"editor_inventory_{dept['id']}_{vista}",
    )
    if st.button("Guardar cambios del listado", key=f"save_inventory_{dept['id']}"):
        updated = 0
        archived = 0
        with get_engine().begin() as db:
            for item in edited.to_dict("records"):
                if item.get("Archivar"):
                    eliminar_software_inventario(db, int(item["_id"]))
                    archived += 1
                    continue
                original = rows_by_id[int(item["_id"])]
                values = {
                    "fabricante": item.get("Fabricante") or None,
                    "version_referencia": item.get("VersiÃ³n") or None,
                    "fecha_ultima_actualizacion": date.today(),
                }
                if vista == "Detallada":
                    guia_value = item.get("GuÃ­a 105")
                    values.update(
                        {
                            "clasificacion_informacion": item.get("ClasificaciÃ³n") or "Media",
                            "en_guia_105": {"SÃ­": True, "No": False}.get(guia_value),
                            "observaciones_elena": item.get("Observaciones") or None,
                            "observaciones_toni": None,
                        }
                    )
                changed = any(
                    values.get(key) != original.get(key)
                    for key in values
                    if key != "fecha_ultima_actualizacion"
                )
                if changed:
                    actualizar_software_revision(db, int(item["_id"]), values)
                    updated += 1
        st.success(f"Registros actualizados: {updated}. Registros archivados: {archived}.")
        st.rerun()


def render_importar(dept: dict) -> None:
    result_key = f"last_import_result_{dept['id']}"
    last_result = st.session_state.get(result_key)
    if last_result:
        st.success(
            f"ImportaciÃ³n registrada con id {last_result['importacion_id']}. "
            f"Software exclusivos autorizados: {last_result.get('exclusivos_autorizados', 0)}. "
            f"Reactivaciones pendientes: {last_result['reactivaciones_pendientes']}"
        )
        st.page_link("pages/1_Inventario_de_software.py", label="Revisar cola de reactivaciones")
        _render_authorization_promotions(dept)
        if st.button("Ocultar resumen de la Ãºltima importaciÃ³n", key=f"hide_import_result_{dept['id']}"):
            st.session_state.pop(result_key, None)
            st.rerun()
    with get_engine().connect() as db:
        equipos = listar_equipos(db, dept["id"], solo_activos=True)
    nonce = st.session_state.get(f"import_reset_nonce_{dept['id']}", 0)
    options = ["+ Crear dispositivo nuevo"] + [f"{equipo['nombre']} (id {equipo['id']})" for equipo in equipos]
    selected = st.selectbox("Dispositivo", options, key=f"import_equipo_{dept['id']}_{nonce}")
    nuevo_nombre = None
    usuario = None
    if selected == "+ Crear dispositivo nuevo":
        st.info("Este dispositivo todavÃ­a no tiene historial de importaciones.")
        nuevo_nombre = st.text_input("Nombre del nuevo dispositivo", key=f"new_eq_{dept['id']}_{nonce}")
        usuario = st.text_input("Usuario del dispositivo", key=f"new_user_{dept['id']}_{nonce}")
    else:
        selected_equipo_id = equipos[options.index(selected) - 1]["id"]
        _render_import_audit(selected_equipo_id)
    tab_paste, tab_file = st.tabs(["Pegar texto", "Subir fichero"])
    programas = None
    metodo = "paste"
    with tab_paste:
        pasted = st.text_area(
            "Listado copiado desde Panda Adaptive Defense",
            height=220,
            placeholder="Nombre\tEditor\tFecha de instalaciÃ³n\tTamaÃ±o\tVersiÃ³n",
            key=f"paste_{dept['id']}_{nonce}",
        )
        if st.button("Analizar texto", key=f"analyze_paste_{dept['id']}"):
            programas = parse_paste(pasted)
            metodo = "paste"
    with tab_file:
        uploaded = st.file_uploader("CSV o XLSX", type=["csv", "xlsx"], key=f"file_{dept['id']}_{nonce}")
        if st.button("Analizar fichero", key=f"analyze_file_{dept['id']}"):
            if uploaded:
                programas = parse_file(uploaded.getvalue(), uploaded.name)
                metodo = "file"
            else:
                st.error("Sube un fichero primero.")
    pending_diff = st.session_state.get(f"diff_{dept['id']}")
    if programas is None and pending_diff:
        diff = pending_diff
        st.info("Hay un anÃ¡lisis pendiente de confirmar.")
        st.write({
            "nuevos": len(diff["nuevos"]),
            "actualizados": len(diff["actualizados"]),
            "cambios_version": len(diff["cambios_version"]),
            "eliminados": len(diff["eliminados"]),
        })
        if st.button("Confirmar e importar", type="primary", key=f"confirm_pending_import_{dept['id']}"):
            with get_engine().begin() as db:
                importacion_id = aplicar_diff(
                    st.session_state[f"equipo_import_{dept['id']}"],
                    st.session_state[f"programas_{dept['id']}"],
                    st.session_state[f"diff_{dept['id']}"],
                    db,
                    st.session_state[f"metodo_{dept['id']}"],
                )
                exclusive_authorized = autorizar_exclusivos_automaticamente(db, dept["id"])
                pending = contar_reactivaciones_pendientes(db, dept["id"])
            st.session_state[result_key] = {
                "importacion_id": importacion_id,
                "exclusivos_autorizados": exclusive_authorized,
                "reactivaciones_pendientes": pending,
            }
            _clear_import_state(dept["id"])
            st.rerun()
        if st.button("Descartar anÃ¡lisis", key=f"discard_import_{dept['id']}"):
            _clear_import_state(dept["id"])
            st.rerun()
        return
    if programas is None:
        return
    if not programas:
        st.error("No se detectaron programas.")
        return
    with get_engine().begin() as db:
        if selected == "+ Crear dispositivo nuevo":
            if not nuevo_nombre or not nuevo_nombre.strip():
                st.error("Introduce el nombre del dispositivo.")
                return
            if existe_equipo(db, dept["id"], nuevo_nombre):
                st.error("Ya existe un dispositivo con ese nombre.")
                return
            equipo_id = crear_equipo(db, dept["id"], nuevo_nombre, usuario)
        else:
            equipo_id = equipos[options.index(selected) - 1]["id"]
        diff = calcular_diff(equipo_id, programas, db)
    st.session_state[f"diff_{dept['id']}"] = diff
    st.session_state[f"programas_{dept['id']}"] = programas
    st.session_state[f"equipo_import_{dept['id']}"] = equipo_id
    st.session_state[f"metodo_{dept['id']}"] = metodo
    st.success("AnÃ¡lisis preparado. Revisa el resumen y confirma.")
    st.write({
        "nuevos": len(diff["nuevos"]),
        "actualizados": len(diff["actualizados"]),
        "cambios_version": len(diff["cambios_version"]),
        "eliminados": len(diff["eliminados"]),
    })
    if st.button("Confirmar e importar", type="primary", key=f"confirm_import_{dept['id']}"):
        with get_engine().begin() as db:
            importacion_id = aplicar_diff(
                st.session_state[f"equipo_import_{dept['id']}"],
                st.session_state[f"programas_{dept['id']}"],
                st.session_state[f"diff_{dept['id']}"],
                db,
                st.session_state[f"metodo_{dept['id']}"],
            )
            exclusive_authorized = autorizar_exclusivos_automaticamente(db, dept["id"])
            pending = contar_reactivaciones_pendientes(db, dept["id"])
        st.session_state[result_key] = {
            "importacion_id": importacion_id,
            "exclusivos_autorizados": exclusive_authorized,
            "reactivaciones_pendientes": pending,
        }
        _clear_import_state(dept["id"])
        st.rerun()


def render_exportar(dept: dict) -> None:
    detalle = st.checkbox("Incluir detalle por dispositivo", key=f"export_detail_{dept['id']}")
    if st.button("Generar Excel del departamento", key=f"export_{dept['id']}"):
        with get_engine().connect() as db:
            data = generar_excel(db, [dept["id"]], detalle_por_equipo=detalle)
        st.download_button(
            "Descargar Excel",
            data=data,
            file_name=f"inventario_{dept['codigo']}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"download_{dept['id']}",
        )
    if st.button("Exportar historial de importaciones", key=f"export_import_log_{dept['id']}"):
        with get_engine().connect() as db:
            data = generar_excel_importaciones(db, dept["id"])
        st.download_button(
            "Descargar historial",
            data=data,
            file_name=f"historial_importaciones_{dept['codigo']}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"download_import_log_{dept['id']}",
        )


def render_dispositivos(dept: dict, es_servidor: bool = False) -> None:
    with get_engine().connect() as db:
        equipos = listar_equipos(db, dept["id"], es_servidor=es_servidor)
    if not equipos:
        st.info("No hay dispositivos registrados.")
        return
    display = pd.DataFrame(equipos).rename(
        columns={
            "nombre": "Dispositivo",
            "notas": "Usuario del dispositivo",
            "ultima_importacion": "Ãšltima importaciÃ³n",
        }
    )
    display["Activo"] = display["activo"].map(lambda value: "SÃ­" if value else "No")
    display["Estado importaciÃ³n"] = display["Ãšltima importaciÃ³n"].map(estado_importacion)
    st.dataframe(
        display[
            [
                "Dispositivo",
                "Usuario del dispositivo",
                "Activo",
                "Ãšltima importaciÃ³n",
                "Estado importaciÃ³n",
                "total_software_activo",
                "fecha_alta",
                "fecha_baja",
            ]
        ],
        hide_index=True,
        use_container_width=True,
    )
    safe_dept = "".join(char if char.isalnum() else "_" for char in dept["nombre"]).strip("_")
    st.download_button(
        "Exportar equipos a Excel",
        data=exportar_equipos_excel(equipos, dept["nombre"]),
        file_name=f"Inventario_Equipos_{safe_dept}_{date.today().isoformat()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"download_equipos_{dept['id']}",
    )
    labels = {f"{equipo['nombre']} (id {equipo['id']})": equipo for equipo in equipos}
    selected_label = st.selectbox("Equipo", list(labels.keys()), key=f"user_eq_{dept['id']}")
    selected = labels[selected_label]
    with st.expander("Ficha del equipo", expanded=True):
        st.subheader(selected["nombre"])
        col_hw1, col_hw2 = st.columns(2)
        with col_hw1:
            st.write("**Hardware**")
            st.write(f"Tipo de dispositivo: {selected.get('tipo_dispositivo') or '-'}")
            st.write(f"Marca / Modelo: {selected.get('marca_modelo') or '-'}")
            st.write(f"NÂº de serie: {selected.get('num_serie') or '-'}")
            st.write(f"DirecciÃ³n MAC: {selected.get('mac_address') or '-'}")
            st.write(f"Sistema operativo: {selected.get('sistema_operativo') or '-'}")
            st.write(f"Procesador: {selected.get('procesador') or '-'}")
            st.write(f"RAM: {selected.get('ram') or '-'}")
            st.write(f"Almacenamiento: {selected.get('almacenamiento') or '-'}")
        with col_hw2:
            st.write("**Actividad**")
            st.write(f"Responsable: {selected.get('responsable') or '-'}")
            st.write(f"UbicaciÃ³n: {selected.get('ubicacion') or '-'}")
            st.write(f"Coste: {selected.get('coste') or '-'}")
            st.write(f"Fecha de adquisiciÃ³n: {selected.get('fecha_adquisicion') or '-'}")
            st.write(f"Ãšltima importaciÃ³n: {selected.get('ultima_importacion') or '-'}")
            st.write(f"MÃ©todo: {selected.get('ultimo_metodo') or '-'}")
            st.write(
                "Nuevos / actualizados / eliminados: "
                f"{selected.get('ultimo_nuevos') or 0} / "
                f"{selected.get('ultimo_actualizados') or 0} / "
                f"{selected.get('ultimo_eliminados') or 0}"
            )
            st.write(f"Software activo instalado: {selected.get('total_software_activo') or 0}")
        alerts = alertas_equipo(selected)
        if alerts:
            st.write("**Alertas**")
            for alert in alerts:
                st.warning(alert)
        else:
            st.success("Sin alertas activas.")

    with st.form(f"user_form_{dept['id']}"):
        usuario = st.text_input("Usuario del dispositivo", value=selected.get("notas") or "")
        if st.form_submit_button("Guardar usuario"):
            with get_engine().begin() as db:
                actualizar_usuario_dispositivo(db, selected["id"], usuario.strip() or None)
            st.success("Usuario actualizado.")
            st.rerun()


def render_reactivaciones(dept: dict) -> None:
    with get_engine().connect() as db:
        rows = listar_reactivaciones_pendientes(db, dept["id"])
    if not rows:
        st.info("No hay reactivaciones pendientes.")
        return
    st.dataframe(
        pd.DataFrame(rows)[["software_nombre", "version_referencia", "fabricante", "equipo", "fecha_deteccion"]],
        hide_index=True,
        use_container_width=True,
    )
    labels = {f"{row['software_nombre']} - {row['equipo']} (id {row['id']})": row["id"] for row in rows}
    selected_label = st.selectbox("Pendiente", list(labels.keys()), key=f"react_select_{dept['id']}")
    selected_id = labels[selected_label]
    col_reactivate, col_ignore = st.columns(2)
    with col_reactivate:
        if st.button("Reactivar", key=f"reactivate_{dept['id']}"):
            with get_engine().begin() as db:
                resolver_reactivacion(db, selected_id, "reactivar")
            st.success("Software reactivado.")
            st.rerun()
    with col_ignore:
        if st.button("Ignorar", key=f"ignore_reactivate_{dept['id']}"):
            with get_engine().begin() as db:
                resolver_reactivacion(db, selected_id, "ignorar")
            st.success("ReactivaciÃ³n ignorada.")
            st.rerun()


st.title("Inventario por departamento")

def render_departamento_page(departamento_codigo: str) -> None:
    try:
        with get_engine().connect() as db:
            departamentos = listar_departamentos_con_estadisticas(db)
    except Exception as exc:
        st.error("No se pudo conectar con MySQL.")
        st.exception(exc)
        st.stop()

    dept = next((item for item in departamentos if item["codigo"] == departamento_codigo), None)
    if not dept:
        st.error(f"No se encontró el departamento con código {departamento_codigo}.")
        st.stop()

    st.session_state["departamento_id"] = dept["id"]
    st.session_state["departamento_nombre"] = dept["nombre"]
    st.title(dept["nombre"])
    st.page_link("pages/1_Inventario_de_software.py", label="Volver al índice de departamentos")
    st.page_link("pages/3_Software_Empresa.py", label="Ver todo el software de la empresa")
    st.subheader(f"{dept['n_equipos']} dispositivos · {dept['n_software']} software")

    tab_inv, tab_import, tab_export, tab_devices, tab_reactivate = st.tabs(
        ["Inventario", "Importar", "Exportar", "Dispositivos", "Reactivaciones"]
    )
    with tab_inv:
        render_inventario(dept)
    with tab_import:
        render_importar(dept)
    with tab_export:
        render_exportar(dept)
    with tab_devices:
        render_dispositivos(dept, es_servidor=(departamento_codigo == "servidores"))
    with tab_reactivate:
        render_reactivaciones(dept)
