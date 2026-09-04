from __future__ import annotations

import pandas as pd
import streamlit as st

from core.casillas import normalize_booth_catalog, read_booth_catalog
from core.cartography import load_section_catalog, source_metadata
from core.historical_booths import fetch_iees_historical_2024
from core.local_store import get_local_booth_catalog_meta, get_local_booths, get_local_sections, set_local_booths
from core.runtime import active_mode
from core.ui import page_header

page_header("Catálogos", "Cartografía territorial y casillas electorales")
mode=active_mode()
if mode!="LOCAL":
    st.info("La administración V3 de catálogos se prueba primero en modo temporal. Al activar un catálogo nuevo, las asignaciones de casilla se recalculan sin volver a cargar las personas.")
    st.stop()

t1,t2,t3=st.tabs(["Cartografía Sinaloa","Casillas históricas 2024","Cargar/actualizar casillas"])
with t1:
    cat=load_section_catalog(); meta=source_metadata()
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Secciones",f"{len(cat):,}")
    c2.metric("Municipios",cat["municipio"].nunique() if not cat.empty else 0)
    c3.metric("Distritos locales",cat["distrito_local"].nunique() if not cat.empty else 0)
    c4.metric("Distritos federales",cat["distrito_federal"].nunique() if not cat.empty else 0)
    st.success("La cartografía seccional ya viene instalada en V3. El usuario normal no necesita cargar GeoJSON.")
    st.json(meta)
    if not cat.empty:
        st.dataframe(cat.head(200),use_container_width=True,hide_index=True,height=480)

with t2:
    current=get_local_booths(); meta=get_local_booth_catalog_meta()
    if not current.empty:
        st.success(f"Catálogo activo: {len(current):,} casillas · {current['seccion'].nunique():,} secciones")
        if meta: st.json(meta)
    else:
        st.warning("No hay catálogo de casillas activo todavía.")
    st.write("El catálogo histórico se usa **solo para pruebas y referencia**. Cuando INE/IEES publique el proceso vigente, se sustituye sin perder la estructura de personas.")
    if st.button("Descargar y activar histórico IEES 2024",type="primary",use_container_width=True):
        try:
            with st.spinner("Consultando fuente pública IEES..."):
                booths,hmeta=fetch_iees_historical_2024()
            set_local_booths(booths,hmeta)
            st.success(f"Activadas {len(booths):,} casillas históricas.")
            st.rerun()
        except Exception as exc:
            st.error(f"No fue posible descargarlo automáticamente: {exc}")
            st.caption("Puedes cargar el archivo manualmente en la pestaña siguiente si ya lo tienes descargado.")

with t3:
    st.write("Acepta un Excel de casillas del proceso que quieras usar. El nuevo catálogo reemplaza al anterior, pero no borra personas ni jerarquías.")
    up=st.file_uploader("Catálogo de casillas (Excel)",type=["xlsx","xlsm","xls"],key="booth_catalog_v3")
    if up:
        raw,sheets=read_booth_catalog(up.getvalue()); sheet=st.selectbox("Hoja",sheets,key="booth_sheet_v3"); raw,_=read_booth_catalog(up.getvalue(),sheet); norm,mapping=normalize_booth_catalog(raw)
        st.dataframe(pd.DataFrame([{"campo":k,"columna":v or "NO DETECTADA"} for k,v in mapping.items()]),use_container_width=True,hide_index=True)
        st.dataframe(norm.head(100),use_container_width=True,hide_index=True)
        proceso=st.text_input("Proceso electoral",value="Proceso por definir")
        fuente=st.text_input("Fuente",value="INE/IEES")
        estatus=st.selectbox("Estatus",["OFICIAL_VIGENTE","HISTORICO_REFERENCIA","OPERATIVO_POR_VALIDAR"])
        if st.button("Activar catálogo cargado",type="primary",use_container_width=True):
            set_local_booths(norm,{"proceso":proceso,"fuente":fuente,"estatus":estatus,"registros":len(norm),"secciones":int(norm['seccion'].nunique())})
            st.success("Catálogo activado."); st.rerun()
