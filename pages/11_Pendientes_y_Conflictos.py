from __future__ import annotations

import pandas as pd
import streamlit as st

from core.local_store import get_local_booth_assignments, get_local_incidents, get_local_people, get_local_sections
from core.runtime import active_mode
from core.ui import page_header


def _fmt_date(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "No disponible"
    try:
        return pd.to_datetime(value).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(value)


def _reason(value):
    if not value:
        return "Pendiente de validar"
    mapping = {
        "SECCION_SIN_CASILLAS_CATALOGO_ACTIVO": "Sección sin casillas en catálogo activo",
        "SECCION_SIN_CASILLAS_CATALOGADAS": "Sección sin casillas en catálogo activo",
        "CATALOGO_SIN_RANGOS_ALFABETICOS": "Catálogo sin rangos alfabéticos suficientes",
        "NOMBRE_SIN_APELLIDO_DETERMINABLE": "Nombre sin apellido determinable",
        "RANGO_ALFABETICO_AMBIGUO": "Rango alfabético ambiguo",
        "APELLIDO_FUERA_RANGOS_CATALOGO": "Apellido sin correspondencia única en rangos",
        "CASILLA_EXPLICITA_NO_COINCIDE_CATALOGO": "Casilla indicada no coincide con catálogo",
        "FALTAN_DATOS_PARA_DETERMINAR_CASILLA": "Faltan datos para determinar casilla",
        "PROYECCION_ALFABETICA_LISTA_NOMINAL": "Sugerencia por orden alfabético ponderado con lista nominal",
        "PROYECCION_ALFABETICA_EQUITATIVA": "Sugerencia por orden alfabético entre casillas B/C",
        "EXTRAORDINARIA_SIN_LOCALIDAD": "Casilla extraordinaria: falta localidad para asignar con certeza",
    }
    return mapping.get(str(value), str(value).replace("_", " ").title())


page_header("Pendientes y conflictos", "Centro de control de calidad con trazabilidad por archivo, estructura, importación y fila")
if active_mode() != "LOCAL":
    st.info("Esta vista V3 está optimizada primero para el flujo temporal de cargas Excel.")
    st.stop()

people = get_local_people()
sections = get_local_sections()
incidents = get_local_incidents()
assignments = get_local_booth_assignments()

no_phone = people[people.get("telefono", pd.Series(index=people.index, dtype=object)).isna()] if not people.empty else pd.DataFrame()
no_section = people[people.get("seccion", pd.Series(index=people.index, dtype=object)).isna()] if not people.empty else pd.DataFrame()
no_parent = people[(people.get("superior_directo_nombre", pd.Series(index=people.index, dtype=object)).isna()) & people.get("roles", pd.Series(index=people.index, dtype=str)).fillna("").str.contains("PROMOVIDO")] if not people.empty else pd.DataFrame()
with_presence = sections[sections.get("promovidos", pd.Series(index=sections.index, dtype=int)).fillna(0) > 0] if not sections.empty else pd.DataFrame()
no_coord = with_presence[with_presence.get("coordinadores", pd.Series(index=with_presence.index, dtype=int)).fillna(0) == 0] if not with_presence.empty else pd.DataFrame()
pending_booth = assignments[assignments.get("casilla_id", pd.Series(index=assignments.index, dtype=object)).isna()] if not assignments.empty else pd.DataFrame()
suggested_booth = assignments[assignments.get("estado_asignacion", pd.Series(index=assignments.index, dtype=object)).fillna("").eq("SUGERIDA")] if not assignments.empty else pd.DataFrame()
territorial = incidents[incidents.get("origen_incidencia", pd.Series(index=incidents.index, dtype=str)).fillna("") == "CARTOGRAFIA"] if not incidents.empty else pd.DataFrame()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Incidencias", len(incidents))
c2.metric("Conflictos territoriales", len(territorial))
c3.metric("Casilla sugerida", len(suggested_booth))
c4.metric("Promovidos sin casilla", len(pending_booth))
c5.metric("Secciones sin coordinador", len(no_coord))
c6, c7, c8 = st.columns(3)
c6.metric("Personas sin teléfono", len(no_phone))
c7.metric("Personas sin sección", len(no_section))
c8.metric("Promovidos sin superior", len(no_parent))

tabs = st.tabs(["Incidencias", "Casillas sugeridas", "Casillas pendientes", "Personas incompletas"])

with tabs[0]:
    if incidents.empty:
        st.success("No hay incidencias registradas.")
    else:
        f1, f2, f3 = st.columns(3)
        sev_values = sorted(incidents.get("severidad", pd.Series(dtype=str)).dropna().astype(str).unique().tolist())
        sev = f1.multiselect("Severidad", sev_values, default=sev_values)
        files = sorted(incidents.get("archivo_origen", pd.Series(dtype=str)).dropna().astype(str).unique().tolist())
        file_sel = f2.selectbox("Archivo Excel", ["TODOS"] + files)
        structures = sorted(incidents.get("estructura_origen", pd.Series(dtype=str)).dropna().astype(str).unique().tolist())
        structure_sel = f3.selectbox("Estructura", ["TODAS"] + structures)
        f = incidents.copy()
        if sev and "severidad" in f:
            f = f[f["severidad"].isin(sev)]
        if file_sel != "TODOS" and "archivo_origen" in f:
            # Incluye conflictos multiorigen donde el archivo está listado en archivos_involucrados.
            mask = f["archivo_origen"].fillna("").eq(file_sel)
            if "archivos_involucrados" in f:
                mask = mask | f["archivos_involucrados"].fillna("").str.contains(file_sel, regex=False)
            f = f[mask]
        if structure_sel != "TODAS" and "estructura_origen" in f:
            f = f[f["estructura_origen"].fillna("") == structure_sel]

        out = pd.DataFrame({
            "Archivo Excel": f.get("archivo_origen", pd.Series(index=f.index, dtype=object)),
            "Archivos involucrados": f.get("archivos_involucrados", pd.Series(index=f.index, dtype=object)),
            "Estructura": f.get("estructura_origen", pd.Series(index=f.index, dtype=object)),
            "Fecha de carga": f.get("fecha_importacion", pd.Series(index=f.index, dtype=object)).map(_fmt_date),
            "Fila": f.get("fila_excel", pd.Series(index=f.index, dtype=object)),
            "Filas involucradas": f.get("filas_involucradas", pd.Series(index=f.index, dtype=object)),
            "Severidad": f.get("severidad", pd.Series(index=f.index, dtype=object)),
            "Tipo": f.get("tipo", pd.Series(index=f.index, dtype=object)),
            "Campo": f.get("campo", pd.Series(index=f.index, dtype=object)),
            "Valor": f.get("valor", pd.Series(index=f.index, dtype=object)),
            "Mensaje": f.get("mensaje", pd.Series(index=f.index, dtype=object)),
        })
        for col in ["Archivo Excel", "Estructura", "Filas involucradas", "Archivos involucrados"]:
            out[col] = out[col].fillna("No disponible")
        st.dataframe(out, use_container_width=True, hide_index=True, height=560)

with tabs[1]:
    if suggested_booth.empty:
        st.success("No hay asignaciones sugeridas para revisar.")
    else:
        st.caption("Las sugerencias ayudan al control operativo, pero no sustituyen una asignación oficial/determinística.")
        f1, f2 = st.columns(2)
        sections_s = sorted(pd.to_numeric(suggested_booth.get("seccion"), errors="coerce").dropna().astype(int).unique().tolist())
        section_sel = f1.selectbox("Sección", ["TODAS"] + sections_s, key="suggested_section")
        reasons_s = sorted(suggested_booth.get("criterio_asignacion", pd.Series(dtype=str)).dropna().astype(str).unique().tolist())
        reason_s = f2.selectbox("Criterio", ["TODOS"] + reasons_s, key="suggested_reason", format_func=lambda x: x if x == "TODOS" else _reason(x))
        f = suggested_booth.copy()
        if section_sel != "TODAS":
            f = f[pd.to_numeric(f["seccion"], errors="coerce") == int(section_sel)]
        if reason_s != "TODOS":
            f = f[f["criterio_asignacion"] == reason_s]
        out = pd.DataFrame({
            "Promovido": f.get("promovido"),
            "Sección": f.get("seccion"),
            "Casilla sugerida": f.get("clave_casilla"),
            "Apellido usado": f.get("apellido_usado"),
            "Confianza apellido": f.get("apellido_confianza"),
            "Criterio": f.get("criterio_asignacion", pd.Series(index=f.index, dtype=object)).map(_reason),
            "Archivo Excel": f.get("archivo_origen"),
            "Fila": f.get("fila_excel"),
        })
        st.dataframe(out, use_container_width=True, hide_index=True, height=560)

with tabs[2]:
    if pending_booth.empty:
        st.success("No hay promovidos pendientes de casilla.")
    else:
        f1, f2 = st.columns(2)
        files = sorted(pending_booth.get("archivo_origen", pd.Series(dtype=str)).dropna().astype(str).unique().tolist())
        file_sel = f1.selectbox("Archivo Excel", ["TODOS"] + files, key="pending_file")
        reasons = sorted(pending_booth.get("criterio_asignacion", pd.Series(dtype=str)).dropna().astype(str).unique().tolist())
        reason_sel = f2.selectbox("Motivo", ["TODOS"] + reasons, format_func=lambda x: x if x == "TODOS" else _reason(x))
        f = pending_booth.copy()
        if file_sel != "TODOS":
            f = f[f["archivo_origen"] == file_sel]
        if reason_sel != "TODOS":
            f = f[f["criterio_asignacion"] == reason_sel]
        out = pd.DataFrame({
            "Promovido": f.get("promovido"),
            "Coordinador directo": f.get("coordinador_directo"),
            "Sección": f.get("seccion"),
            "Municipio": f.get("municipio"),
            "Apellido usado": f.get("apellido_usado"),
            "Origen apellido": f.get("apellido_origen"),
            "Confianza": f.get("apellido_confianza"),
            "Estado": f.get("estado_asignacion"),
            "Motivo": f.get("criterio_asignacion", pd.Series(index=f.index, dtype=object)).map(_reason),
            "Archivo Excel": f.get("archivo_origen"),
            "Estructura": f.get("estructura_origen"),
            "Fecha de carga": f.get("fecha_importacion", pd.Series(index=f.index, dtype=object)).map(_fmt_date),
            "Fila": f.get("fila_excel"),
        })
        st.dataframe(out, use_container_width=True, hide_index=True, height=560)

with tabs[3]:
    choice = st.radio("Mostrar", ["Sin teléfono", "Sin sección", "Promovidos sin superior"], horizontal=True)
    data = {"Sin teléfono": no_phone, "Sin sección": no_section, "Promovidos sin superior": no_parent}[choice]
    if data.empty:
        st.success("Sin pendientes en esta categoría.")
    else:
        cols = [c for c in ["nombre_completo", "telefono", "seccion", "municipio", "superior_directo_nombre", "archivo_origen", "estructuras"] if c in data.columns]
        st.dataframe(data[cols], use_container_width=True, hide_index=True, height=500)
