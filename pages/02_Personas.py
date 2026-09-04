from __future__ import annotations

import pandas as pd
import streamlit as st

from core.local_store import get_local_people
from core.queries import people_dataframe
from core.runtime import active_mode, optional_client
from core.ui import page_header

page_header("Personas", "Consulta central de integrantes, roles, sección, distritos y superior directo")
mode = active_mode()
if mode == "LOCAL": df = get_local_people(); st.caption("🟢 Base temporal enriquecida con cartografía")
elif mode == "SUPABASE":
    client = optional_client()
    if client is None: st.stop()
    df = people_dataframe(client)
else:
    st.info("Primero carga un Excel o activa la base demostrativa desde Dashboard."); st.stop()
if df.empty: st.info("Aún no hay personas para mostrar."); st.stop()

search = st.text_input("Buscar por nombre o teléfono")
municipality = st.selectbox("Municipio", ["TODOS"] + sorted(df.get("municipio", pd.Series(dtype=str)).dropna().astype(str).unique().tolist()))
role = st.selectbox("Rol", ["TODOS"] + sorted({r for value in df.get("roles", pd.Series(dtype=str)).dropna() for r in str(value).split(", ") if r}))
filtered=df.copy()
if search:
    s=search.upper().strip(); mask=filtered["nombre_completo"].fillna("").str.upper().str.contains(s,regex=False)
    if "telefono" in filtered: mask=mask|filtered["telefono"].fillna("").astype(str).str.contains(search,regex=False)
    filtered=filtered[mask]
if municipality!="TODOS": filtered=filtered[filtered["municipio"]==municipality]
if role!="TODOS": filtered=filtered[filtered["roles"].fillna("").str.contains(role,regex=False)]

c1,c2,c3,c4=st.columns(4); c1.metric("Resultados",len(filtered)); c2.metric("Con teléfono",int(filtered["telefono"].notna().sum()) if "telefono" in filtered else 0); c3.metric("Para revisar",int((filtered["estado_validacion"]=="REVISAR").sum()) if "estado_validacion" in filtered else 0); c4.metric("Secciones",filtered["seccion"].nunique() if "seccion" in filtered else 0)
cols=[c for c in ["nombre_completo","telefono","roles","superior_directo_nombre","municipio","seccion","distrito_local","distrito_federal","tipo_seccion","municipio_origen","estado_validacion","archivo_origen"] if c in filtered]
display=filtered[cols].copy()
for c in display.columns:
    if display[c].dtype==object: display[c]=display[c].fillna("No disponible")
st.dataframe(display,use_container_width=True,hide_index=True,height=560)
st.download_button("Descargar resultados CSV",display.to_csv(index=False).encode("utf-8-sig"),"personas_filtradas.csv","text/csv")
