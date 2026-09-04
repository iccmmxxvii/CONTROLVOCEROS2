from __future__ import annotations

import pandas as pd
import streamlit as st

from core.local_store import (
    add_local_responsibility, get_local_booth_assignments, get_local_booth_catalog_meta,
    get_local_booth_summary, get_local_booths, get_local_coordinator_section,
    get_local_people, get_local_sections,
)
from core.runtime import active_mode
from core.ui import page_header

page_header("Casillas y responsables V2", "Desglose por sección/casilla, coordinadores con promovidos y responsabilidad formal")
if active_mode() != "LOCAL":
    st.info("Esta vista V2 se prueba primero en modo temporal; Supabase se actualiza con la migración V2.")
    st.stop()

sections=get_local_sections(); booths=get_local_booths(); assignments=get_local_booth_assignments(); summary=get_local_booth_summary(); coord_sec=get_local_coordinator_section(); people=get_local_people(); booth_meta=get_local_booth_catalog_meta()
if sections.empty: st.info("Carga primero uno o varios Excel."); st.stop()

if booth_meta:
    st.info(f"Catálogo de casillas: {booth_meta.get('proceso','Sin proceso')} · {booth_meta.get('estatus','')} · fuente {booth_meta.get('fuente','No disponible')}")
else:
    st.warning("No hay catálogo de casillas activo. Puedes precargar el histórico IEES 2024 en Catálogos.")

only_presence=st.toggle("Mostrar solo secciones con registros",value=True)
base=sections[sections["promovidos"].fillna(0)>0].copy() if only_presence else sections.copy()
municipalities=["TODOS"]+sorted(base["municipio"].dropna().astype(str).unique().tolist()); muni=st.selectbox("Municipio",municipalities)
sec_df=base if muni=="TODOS" else base[base["municipio"]==muni]
if sec_df.empty: st.info("No hay secciones con esos filtros."); st.stop()
section=st.selectbox("Sección",sec_df["numero"].tolist())
sec_row=sec_df[sec_df["numero"].astype(str)==str(section)].iloc[0]

st.caption(f"Municipio: **{sec_row.get('municipio','No disponible')}** · Distrito local: **{sec_row.get('distrito_local','No disponible')}** · Distrito federal: **{sec_row.get('distrito_federal','No disponible')}** · Tipo: **{sec_row.get('tipo_seccion','No disponible')}**")
c1,c2,c3,c4=st.columns(4); c1.metric("Promovidos",int(sec_row.get("promovidos",0))); c2.metric("Coordinadores",int(sec_row.get("coordinadores",0))); c3.metric("Casillas catalogadas",int(sec_row.get("casillas_catalogadas",0))); c4.metric("Sin casilla definida",int(sec_row.get("promovidos_sin_casilla",0)))

st.subheader("Coordinadores con promovidos en la sección")
coord=coord_sec[coord_sec["seccion"].astype(str)==str(section)].copy() if not coord_sec.empty else pd.DataFrame()
if coord.empty: st.info("No hay coordinadores asociados en esta sección.")
else:
    st.dataframe(coord[["coordinador","promovidos","porcentaje_seccion"]],use_container_width=True,hide_index=True)
    top=coord.iloc[0]; formal=sec_row.get("responsable_formal")
    st.write(f"**Mayor estructura registrada:** {top['coordinador']} · {int(top['promovidos'])} promovidos")
    st.write(f"**Responsable formal:** {formal or 'SIN ASIGNAR'}")
    if formal and formal!=top["coordinador"]: st.warning("El responsable formal no coincide con el coordinador con mayor estructura registrada.")

st.subheader("Responsable formal de la sección")
coord_names=coord["coordinador"].dropna().astype(str).tolist() if not coord.empty else people[people["roles"].str.contains("COORDINADOR",na=False)]["nombre_completo"].tolist()
if coord_names:
    selected_resp=st.selectbox("Responsable",sorted(set(coord_names)),key="sec_resp_v2")
    if st.button("Guardar responsable de sección",use_container_width=True):
        add_local_responsibility(selected_resp,"SECCION",str(sec_row["seccion_id"]),f"Sección {section}"); st.success("Responsable actualizado."); st.rerun()

st.divider(); st.subheader("Casillas de la sección")
sec_booths=booths[booths["seccion"].astype(str)==str(section)] if not booths.empty else pd.DataFrame()
if sec_booths.empty:
    st.info("Esta sección todavía no tiene casillas en el catálogo activo. No se inventa una casilla.")
    st.stop()

sec_summary=summary[summary["seccion"].astype(str)==str(section)].copy() if not summary.empty else pd.DataFrame()
if sec_summary.empty:
    display=sec_booths.copy(); display["promovidos"]=0; display["coordinadores_con_promovidos"]=0; display["coordinador_mayor_estructura"]=None; display["responsable_formal"]=None
else:
    display=sec_booths.merge(sec_summary,on=["casilla_id","clave_casilla","seccion","municipio"],how="left",suffixes=("","_res"))
    for c in ["promovidos","coordinadores_con_promovidos","promovidos_coordinador_top"]:
        if c in display: display[c]=display[c].fillna(0).astype(int)
cols=[c for c in ["clave_casilla","tipo_casilla","lista_nominal","promovidos","coordinadores_con_promovidos","coordinador_mayor_estructura","responsable_formal","promovidos_coordinador_top","domicilio"] if c in display]
st.dataframe(display[cols].fillna("No disponible"),use_container_width=True,hide_index=True)

chosen_booth=st.selectbox("Casilla para detalle",sec_booths["clave_casilla"].tolist())
booth_id=sec_booths[sec_booths["clave_casilla"]==chosen_booth].iloc[0]["casilla_id"]
booth_assign=assignments[assignments["casilla_id"]==booth_id] if not assignments.empty else pd.DataFrame()
if booth_assign.empty:
    st.caption("No hay promovidos determinados para esta casilla. En secciones con varias casillas se requiere rango alfabético oficial, casilla explícita o criterio oficial suficiente.")
    by_coord=pd.DataFrame()
else:
    by_coord=booth_assign.groupby("coordinador_directo",dropna=False)["promovido"].nunique().reset_index(name="promovidos").sort_values("promovidos",ascending=False)
    st.dataframe(by_coord.fillna("Sin coordinador"),use_container_width=True,hide_index=True)

pending=assignments[(assignments["seccion"].astype(str)==str(section)) & assignments["casilla_id"].isna()] if not assignments.empty else pd.DataFrame()
if not pending.empty:
    st.warning(f"{pending['promovido'].nunique()} promovidos de esta sección siguen pendientes de casilla exacta. No se distribuyen artificialmente.")
    with st.expander("Ver motivos"):
        st.dataframe(pending[[c for c in ["promovido","coordinador_directo","criterio_asignacion"] if c in pending]],use_container_width=True,hide_index=True)

st.subheader("Responsable formal de casilla")
possible=by_coord["coordinador_directo"].dropna().astype(str).tolist() if not by_coord.empty else coord_names
if possible:
    resp_booth=st.selectbox("Responsable de la casilla",sorted(set(possible)),key="booth_resp_v2")
    if st.button("Guardar responsable de casilla",use_container_width=True):
        add_local_responsibility(resp_booth,"CASILLA",booth_id,chosen_booth); st.success("Responsable de casilla actualizado."); st.rerun()
