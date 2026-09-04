import pandas as pd
import streamlit as st

from core.local_store import build_demo_dataset, get_local_booth_catalog_meta, get_local_payload, get_local_sections, local_dashboard_metrics
from core.queries import dashboard_metrics
from core.runtime import active_mode, optional_client

MORENA = "#C0311A"

st.title("ICC Control Territorial V3.3.2")
st.caption("Concentración de estructura, cobertura territorial y lectura ejecutiva por sección electoral")
mode = active_mode()

if mode == "EMPTY":
    st.error(
        "La base precargada no está activa. Esta versión no requiere que cargues el Excel manualmente. "
        "Revisa que el repositorio tenga el archivo data/base/icc_estructura_12211.csv.gz y que app.py esté en la raíz."
    )
    st.code("data/base/icc_estructura_12211.csv.gz", language="text")
    st.stop()

if mode == "LOCAL":
    p = get_local_payload()
    m = local_dashboard_metrics()
    sections = get_local_sections()
    if p.get("source_kind") == "REPO_SEED":
        st.success(f"Base operativa precargada · {m['promovidos']:,} registros · Grupo 0 activo · cartografía Sinaloa instalada")
    else:
        st.success(f"Base temporal · {len(p.get('files', []))} archivo(s) acumulados · cartografía Sinaloa instalada")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Personas en red", f"{m['personas']:,}")
    c2.metric("Promovidos registrados", f"{m['promovidos']:,}")
    c3.metric("Coordinadores", f"{m['coordinadores']:,}")
    c4.metric("Secciones con registros", f"{m['secciones_con_registros']:,}")

    c5, c6, c7, c8, c9, c10 = st.columns(6)
    c5.metric("Secciones cartografía", f"{m['secciones_catalogo']:,}")
    c6.metric("Secciones sin registros", f"{m['secciones_sin_registros']:,}")
    c7.metric("Casillas catalogadas", f"{m['casillas_catalogadas']:,}")
    c8.metric("Casilla exacta", f"{m['promovidos_casilla_exacta']:,}")
    c9.metric("Casilla sugerida", f"{m['promovidos_casilla_sugerida']:,}")
    c10.metric("Pendientes casilla", f"{m['promovidos_sin_casilla']:,}")

    if m["secciones_catalogo"]:
        pct = 100 * m["secciones_con_registros"] / m["secciones_catalogo"]
        st.progress(min(max(pct / 100, 0), 1), text=f"Cobertura territorial de secciones con registros: {pct:.1f}%")

    booth_meta = get_local_booth_catalog_meta()
    booth_status = str(booth_meta.get("estatus") or "") if booth_meta else ""
    if booth_meta and booth_status != "NO_DISPONIBLE_AUTOMATICAMENTE" and m["casillas_catalogadas"] > 0:
        st.info(
            f"🗳️ Catálogo de casillas activo: {booth_meta.get('proceso','Catálogo')} · "
            f"{booth_status} · {booth_meta.get('registros', m['casillas_catalogadas']):,} registros"
        )
    elif booth_status == "NO_DISPONIBLE_AUTOMATICAMENTE":
        st.warning(
            "El catálogo histórico/oficial de casillas no pudo recuperarse automáticamente en esta sesión. "
            "La base territorial sigue activa y los promovidos permanecen como pendientes de casilla, sin generar ceros falsos."
        )
    else:
        st.warning("No hay catálogo de casillas activo. La base territorial permanece disponible; la asignación por casilla se completará cuando el catálogo esté disponible.")

    st.subheader("Accesos operativos")
    a, b, c, d = st.columns(4)
    a.page_link("pages/05_Mapa.py", label="🗺️ Mapa seccional", use_container_width=True)
    b.page_link("pages/04_Secciones.py", label="🧭 Reporte de secciones", use_container_width=True)
    c.page_link("pages/03_Estructura.py", label="🌳 Estructura", use_container_width=True)
    d.page_link("pages/06_Reportes.py", label="📊 Reportes", use_container_width=True)

    st.subheader("Cobertura por distrito local")
    if not sections.empty:
        cov = sections.groupby("distrito_local", dropna=False).agg(
            secciones=("numero", "nunique"),
            secciones_con_registros=("promovidos", lambda x: int((x.fillna(0) > 0).sum())),
            promovidos=("promovidos", "sum"),
        ).reset_index()
        cov["cobertura_pct"] = (cov["secciones_con_registros"] / cov["secciones"] * 100).round(1)
        valid = cov[cov["distrito_local"].notna()].copy()
        if not valid.empty:
            chart = valid.sort_values("distrito_local").set_index(valid["distrito_local"].astype(int).astype(str))["cobertura_pct"]
            st.bar_chart(chart, color=MORENA, height=300)
        display = cov.rename(columns={
            "distrito_local": "Distrito local",
            "secciones": "Secciones",
            "secciones_con_registros": "Con registros",
            "promovidos": "Promovidos",
            "cobertura_pct": "Cobertura %",
        })
        display["Distrito local"] = display["Distrito local"].apply(lambda x: "Pendiente de validar" if pd.isna(x) else int(x))
        st.dataframe(display, use_container_width=True, hide_index=True, height=350)
else:
    client = optional_client()
    if client is None:
        st.error("Supabase no disponible. Puedes seguir en modo temporal.")
        st.stop()
    m = dashboard_metrics(client)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Personas", m["personas"])
    c2.metric("Secciones", m["secciones_con_registros"])
    c3.metric("Para revisar", m["personas_revisar"])
    c4.metric("Importaciones", m["importaciones_confirmadas"])

st.caption("V3.3.2 prioriza: Excel → validación → estructura → sección → cartografía derivada → casilla → reportes. Los datos derivados conservan su origen y no se completan con supuestos.")
