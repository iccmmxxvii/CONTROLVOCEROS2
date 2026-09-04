import streamlit as st

from core.local_store import get_local_payload
from core.runtime import active_mode
from core.repo_seed import bootstrap_repo_seed

st.set_page_config(
    page_title="ICC Control Territorial V3.3.2",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Regla visual: utilizar todo el espacio útil disponible.
st.markdown(
    """
    <style>
      .block-container {
        max-width: 100% !important;
        padding-top: 1.15rem !important;
        padding-left: 1.35rem !important;
        padding-right: 1.35rem !important;
        padding-bottom: 2rem !important;
      }
      [data-testid="stMetric"] {
        background: #FAFAFB;
        border: 1px solid #ECEFF3;
        border-radius: 14px;
        padding: 0.85rem 1rem;
      }
      div[data-testid="stDataFrame"] {
        border-radius: 12px;
        overflow: hidden;
      }
      .icc-muted { color:#6B7280; }
    </style>
    """,
    unsafe_allow_html=True,
)

# La base de 12,211 registros viene incluida dentro del repositorio.
seed_error = None
try:
    with st.spinner("Cargando base precargada y preparando indicadores territoriales..."):
        bootstrap_repo_seed(auto_booths=True)
except Exception as exc:
    seed_error = str(exc)

mode = active_mode()
if seed_error:
    st.error(
        "No fue posible activar la base precargada. "
        "Verifica data/base/icc_estructura_12211.csv.gz. "
        f"Detalle: {seed_error}"
    )

with st.sidebar:
    if mode == "LOCAL":
        payload = get_local_payload()
        if payload.get("source_kind") == "REPO_SEED":
            st.success("🟢 Base precargada activa")
        else:
            st.success("🟢 Base temporal activa")
        st.caption(f"Fuente: {payload.get('filename') or 'Base local'}")
    elif mode == "SUPABASE":
        st.success("🟢 Supabase conectado")
    else:
        st.info("⚪ Sin base activa")

# Menú operativo simplificado. Los módulos administrativos y futuros se
# conservan físicamente en pages/, pero no se muestran al usuario.
pages = {
    "Inicio": [
        st.Page("pages/00_Dashboard.py", title="Dashboard", icon="🏠", default=True),
    ],
    "Carga": [
        st.Page("pages/01_Importar_Excel.py", title="Cargar Excel", icon="📥"),
    ],
    "Estructura": [
        st.Page("pages/02_Personas.py", title="Personas", icon="👥"),
        st.Page("pages/03_Estructura.py", title="Estructura", icon="🌳"),
    ],
    "Territorio": [
        st.Page("pages/04_Secciones.py", title="Reporte de secciones", icon="🧭"),
        st.Page("pages/05_Mapa.py", title="Mapa seccional", icon="🗺️"),
    ],
    "Análisis": [
        st.Page("pages/06_Reportes.py", title="Reportes", icon="📊"),
    ],
}

# Conservados para uso futuro/administrativo, pero ocultos del menú:
# - pages/07_Catalogos.py
# - pages/08_Importaciones.py
# - pages/09_Captura_y_Edicion.py
# - pages/10_Casillas_y_Responsables.py
# - pages/11_Pendientes_y_Conflictos.py
pg = st.navigation(pages, position="sidebar", expanded=True)
pg.run()
