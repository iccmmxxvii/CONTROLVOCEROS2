from __future__ import annotations

import pandas as pd
import streamlit as st

from core.local_store import get_local_booth_assignments, get_local_booth_summary, get_local_booths, get_local_normalized, get_local_sections
from core.queries import sections_dataframe
from core.runtime import active_mode, optional_client
from core.ui import page_header

MORENA = "#C0311A"

def _safe_int(value) -> int:
    try:
        if pd.isna(value):
            return 0
    except Exception:
        pass
    try:
        return int(float(value))
    except Exception:
        return 0


def _coverage_status(row) -> str:
    promoted = _safe_int(row.get("promovidos"))
    pending = _safe_int(row.get("promovidos_sin_casilla"))
    suggested = _safe_int(row.get("promovidos_casilla_sugerida"))
    if promoted <= 0:
        return "SIN REGISTROS"
    if pending > 0:
        return "CON PENDIENTES"
    if suggested > 0:
        return "CON SUGERENCIAS"
    return "CON REGISTROS"


def _section_booths(section, booths: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    if booths.empty:
        return pd.DataFrame()
    sec = booths[booths["seccion"].astype(str) == str(section)].copy()
    if sec.empty:
        return sec
    if summary.empty:
        sec["promovidos"] = 0
        return sec
    sm = summary[summary["seccion"].astype(str) == str(section)].copy()
    if "casilla_id" in sec.columns and "casilla_id" in sm.columns:
        values = sm[[c for c in ["casilla_id", "promovidos", "promovidos_exactos", "promovidos_sugeridos"] if c in sm.columns]].drop_duplicates("casilla_id")
        sec = sec.merge(values, on="casilla_id", how="left")
    else:
        sec["promovidos"] = 0
    sec["promovidos"] = pd.to_numeric(sec.get("promovidos", 0), errors="coerce").fillna(0).astype(int)
    return sec


page_header("Reporte de Secciones", "Lectura operativa y ejecutiva de cobertura territorial por sección electoral")
mode = active_mode()
booths = pd.DataFrame()
booth_summary = pd.DataFrame()
booth_assignments = pd.DataFrame()
normalized = pd.DataFrame()
if mode == "LOCAL":
    df = get_local_sections()
    booths = get_local_booths()
    booth_summary = get_local_booth_summary()
    booth_assignments = get_local_booth_assignments()
    normalized = get_local_normalized()
    st.caption("🟢 Cartografía Sinaloa precargada + base temporal")
elif mode == "SUPABASE":
    client = optional_client()
    if client is None:
        st.stop()
    df = sections_dataframe(client)
else:
    st.info("Carga un Excel o activa demo.")
    st.stop()
if df.empty:
    st.info("Sin secciones.")
    st.stop()

work = df.copy()
work["estado_operativo"] = work.apply(_coverage_status, axis=1)

# Filtros compactos.
f1, f2, f3, f4, f5 = st.columns([1.35, 1, 1, 1.15, 1.15])
muni = f1.selectbox("Municipio", ["TODOS"] + sorted(work["municipio"].dropna().astype(str).unique().tolist()))
dl_vals = sorted(pd.to_numeric(work.get("distrito_local"), errors="coerce").dropna().astype(int).unique().tolist())
dl = f2.selectbox("Distrito local", ["TODOS"] + dl_vals)
df_vals = sorted(pd.to_numeric(work.get("distrito_federal"), errors="coerce").dropna().astype(int).unique().tolist())
dfed = f3.selectbox("Distrito federal", ["TODOS"] + df_vals)
coverage = f4.selectbox("Estado", ["TODAS", "CON REGISTROS", "CON SUGERENCIAS", "CON PENDIENTES", "SIN REGISTROS"])
q = f5.text_input("Sección", placeholder="Ej. 316")

f = work.copy()
if muni != "TODOS":
    f = f[f["municipio"] == muni]
if dl != "TODOS":
    f = f[pd.to_numeric(f["distrito_local"], errors="coerce") == int(dl)]
if dfed != "TODOS":
    f = f[pd.to_numeric(f["distrito_federal"], errors="coerce") == int(dfed)]
if coverage != "TODAS":
    f = f[f["estado_operativo"] == coverage]
if q:
    f = f[f["numero"].astype(str).str.contains(q, regex=False)]

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Secciones", f"{len(f):,}")
k2.metric("Con registros", f"{int((f['promovidos'].fillna(0) > 0).sum()):,}")
k3.metric("Sin registros", f"{int((f['promovidos'].fillna(0) == 0).sum()):,}")
k4.metric("Promovidos", f"{int(f['promovidos'].fillna(0).sum()):,}")
k5.metric("Casillas", f"{int(f['casillas_catalogadas'].fillna(0).sum()):,}")
k6.metric("Pendientes casilla", f"{int(f['promovidos_sin_casilla'].fillna(0).sum()):,}")

r1, r2 = st.columns([1.6, 1])
with r1:
    st.markdown("#### Secciones con mayor estructura registrada")
    top = f[f["promovidos"].fillna(0) > 0].nlargest(10, "promovidos")[["numero", "municipio", "promovidos"]].copy()
    if top.empty:
        st.info("No hay secciones con registros en este filtro.")
    else:
        chart = top.copy()
        chart["Sección"] = chart["numero"].astype(str)
        st.bar_chart(chart.set_index("Sección")["promovidos"], color=MORENA, height=280)
with r2:
    st.markdown("#### Lectura rápida")
    with_records = int((f["promovidos"].fillna(0) > 0).sum())
    total = len(f)
    pct = (with_records / total * 100) if total else 0
    st.metric("Cobertura del filtro", f"{pct:.1f}%")
    st.write(f"**Con pendientes de casilla:** {int((f['promovidos_sin_casilla'].fillna(0) > 0).sum()):,} secciones")
    st.write(f"**Sin registros:** {int((f['promovidos'].fillna(0) == 0).sum()):,} secciones")

st.markdown("### Resumen operativo por sección")
summary_cols = [c for c in [
    "numero", "municipio", "distrito_local", "distrito_federal", "tipo_seccion",
    "promovidos", "grupos_0_con_presencia", "grupo_0_presencia", "casillas_catalogadas",
    "promovidos_casilla_exacta", "promovidos_casilla_sugerida", "promovidos_sin_casilla", "estado_operativo"
] if c in f.columns]
display = f[summary_cols].copy().rename(columns={
    "numero": "Sección",
    "municipio": "Municipio",
    "distrito_local": "DL",
    "distrito_federal": "DF",
    "tipo_seccion": "Tipo",
    "promovidos": "Promovidos",
    "grupos_0_con_presencia": "Grupos 0",
    "grupo_0_presencia": "Grupo 0 con presencia",
    "casillas_catalogadas": "Casillas",
    "promovidos_casilla_exacta": "Casilla exacta",
    "promovidos_casilla_sugerida": "Casilla sugerida",
    "promovidos_sin_casilla": "Pendientes casilla",
    "estado_operativo": "Estado",
})
for c in ["DL", "DF", "Tipo"]:
    if c in display.columns:
        display[c] = display[c].apply(lambda x: "Pendiente de validar" if pd.isna(x) else x)
st.dataframe(display, use_container_width=True, hide_index=True, height=430)

if not f.empty:
    section_options = [int(x) if str(x).replace(".0", "").isdigit() else x for x in f["numero"].dropna().tolist()]
    selected = st.selectbox("Ver ficha de sección", section_options)
    row = f[pd.to_numeric(f["numero"], errors="coerce") == pd.to_numeric(pd.Series([selected]), errors="coerce").iloc[0]].iloc[0]
    st.markdown(f"### Sección {selected} · {row.get('municipio') or 'Municipio no disponible'}")
    d1, d2, d3, d4, d5, d6 = st.columns(6)
    d1.metric("Promovidos", _safe_int(row.get("promovidos")))
    d2.metric("Grupos 0", _safe_int(row.get("grupos_0_con_presencia")))
    d3.metric("Casillas", _safe_int(row.get("casillas_catalogadas")))
    d4.metric("Casilla exacta", _safe_int(row.get("promovidos_casilla_exacta")))
    d5.metric("Casilla sugerida", _safe_int(row.get("promovidos_casilla_sugerida")))
    d6.metric("Pendientes", _safe_int(row.get("promovidos_sin_casilla")))

    info1, info2 = st.columns(2)
    with info1:
        st.markdown("**Datos territoriales**")
        st.write(f"Distrito local: {row.get('distrito_local') if pd.notna(row.get('distrito_local')) else 'Pendiente de validar'}")
        st.write(f"Distrito federal: {row.get('distrito_federal') if pd.notna(row.get('distrito_federal')) else 'Pendiente de validar'}")
        st.write(f"Tipo: {row.get('tipo_seccion') or 'Pendiente de validar'}")
    with info2:
        st.markdown("**Estructura**")
        st.write(f"Grupo 0 con presencia: {row.get('grupo_0_presencia') or 'Sin presencia'}")
        st.write(f"Estado: {_coverage_status(row)}")

    if mode == "LOCAL":
        sec_booths = _section_booths(selected, booths, booth_summary)
        st.markdown("#### Promovidos por casilla")
        if sec_booths.empty:
            st.info("La sección no tiene casillas en el catálogo activo.")
        else:
            cas_display = sec_booths[[c for c in ["clave_casilla", "promovidos", "promovidos_exactos", "promovidos_sugeridos"] if c in sec_booths.columns]].copy()
            cas_display = cas_display.rename(columns={
                "clave_casilla": "Casilla", "promovidos": "Promovidos total",
                "promovidos_exactos": "Exactos", "promovidos_sugeridos": "Sugeridos"
            })
            st.dataframe(cas_display.fillna(0), use_container_width=True, hide_index=True, height=min(300, 45 + 36 * len(cas_display)))

    if mode == "LOCAL" and not normalized.empty:
        sec_norm = normalized[pd.to_numeric(normalized.get("seccion"), errors="coerce") == int(selected)].copy()
        if not sec_norm.empty:
            st.markdown("#### Promovidos de la sección")
            sec_norm["registro_idx"] = sec_norm.index
            cols = [c for c in ["registro_idx", "promovido_normalizado", "telefono", "grupo_0", "fila_excel"] if c in sec_norm.columns]
            detail = sec_norm[cols].copy()
            if not booth_assignments.empty:
                ass_cols = [c for c in ["registro_idx", "clave_casilla", "estado_asignacion", "criterio_descripcion"] if c in booth_assignments.columns]
                detail = detail.merge(booth_assignments[ass_cols], on="registro_idx", how="left")
            detail = detail.rename(columns={
                "promovido_normalizado": "Promovido", "telefono": "Teléfono", "grupo_0": "Grupo 0",
                "fila_excel": "Fila Excel", "clave_casilla": "Casilla", "estado_asignacion": "Estado casilla",
                "criterio_descripcion": "Criterio"
            })
            if "Casilla" in detail.columns:
                detail["Casilla"] = detail["Casilla"].fillna("Pendiente de asignación individual")
            st.dataframe(detail.drop(columns=["registro_idx"], errors="ignore"), use_container_width=True, hide_index=True, height=min(520, 48 + 34 * min(len(detail), 14)))

    st.page_link("pages/05_Mapa.py", label="🗺️ Abrir mapa seccional", use_container_width=False)

csv = display.to_csv(index=False).encode("utf-8-sig")
st.download_button("Descargar reporte filtrado CSV", csv, "reporte_secciones_v3.csv", "text/csv")

with st.expander("Detalle técnico / trazabilidad", expanded=False):
    tech_cols = [c for c in ["numero", "estado_catalogo", "municipio_conflicto", "centroide_lat", "centroide_lon"] if c in f.columns]
    if tech_cols:
        st.dataframe(f[tech_cols], use_container_width=True, hide_index=True, height=260)
    st.caption("Los datos territoriales derivados provienen de la cartografía precargada; los conteos son calculados por la plataforma.")
