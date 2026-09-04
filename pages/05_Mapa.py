from __future__ import annotations

import html

import pandas as pd
import pydeck as pdk
import streamlit as st

from core.cartography import build_geojson_with_metrics, source_metadata
from core.db import fetch_all
from core.local_store import get_local_booth_summary, get_local_booths, get_local_sections
from core.queries import booths_dataframe, sections_dataframe
from core.runtime import active_mode, optional_client
from core.ui import page_header

LAYER_ID = "secciones-operativas"


def _safe_int(value) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _prepare_booth_detail(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()
    out = summary.copy()
    for col in ["promovidos", "coordinadores_con_promovidos", "promovidos_coordinador_top"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0).astype(int)
    return out


def _prepare_booth_catalog_local() -> pd.DataFrame:
    booths = get_local_booths().copy()
    if booths.empty:
        return booths
    for col in ["seccion", "numero_casilla"]:
        if col in booths.columns:
            booths[col] = pd.to_numeric(booths[col], errors="coerce")
    return booths


def _prepare_booth_catalog_supabase(client) -> pd.DataFrame:
    try:
        rows = fetch_all(client, "casillas_electorales", select="seccion,clave_casilla,tipo_casilla,numero_casilla,activo", filters={"activo": True}, order="seccion")
    except Exception:
        try:
            rows = fetch_all(client, "casillas_electorales", select="seccion,clave_casilla,tipo_casilla,numero_casilla", order="seccion")
        except Exception:
            rows = []
    booths = pd.DataFrame(rows)
    if booths.empty:
        return booths
    for col in ["seccion", "numero_casilla"]:
        if col in booths.columns:
            booths[col] = pd.to_numeric(booths[col], errors="coerce")
    return booths


def _normalize_key(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    if not text:
        return ""
    try:
        n = int(float(text))
        if str(n) == text or text.replace('.0', '') == str(n):
            return str(n)
    except Exception:
        pass
    return text


def _build_section_booth_display(sections_df: pd.DataFrame, booth_summary: pd.DataFrame, booth_catalog: pd.DataFrame) -> pd.DataFrame:
    base = sections_df.copy()
    if base.empty:
        return base

    catalog_by_sec = {}
    if not booth_catalog.empty:
        cat = booth_catalog.copy()
        if "clave_casilla" not in cat.columns and "tipo_casilla" in cat.columns:
            cat["clave_casilla"] = cat.apply(lambda r: f"{_safe_int(r.get('seccion'))} {r.get('tipo_casilla')}" if pd.notna(r.get('seccion')) else str(r.get('tipo_casilla')), axis=1)
        sort_cols = [c for c in ["seccion", "numero_casilla", "tipo_casilla", "clave_casilla"] if c in cat.columns]
        if sort_cols:
            cat = cat.sort_values(sort_cols, na_position="last")
        for sec, g in cat.groupby("seccion", dropna=False):
            sec_key = _normalize_key(sec)
            items = []
            for _, row in g.iterrows():
                clave = row.get("clave_casilla") or row.get("tipo_casilla") or "Casilla"
                items.append({"clave": str(clave), "promovidos": 0, "coordinadores": 0})
            unique = []
            seen = set()
            for it in items:
                if it["clave"] not in seen:
                    seen.add(it["clave"])
                    unique.append(it)
            catalog_by_sec[sec_key] = unique

    summary_by_sec = {}
    if not booth_summary.empty:
        bs = booth_summary.copy()
        sort_cols = [c for c in ["seccion", "clave_casilla", "tipo_casilla"] if c in bs.columns]
        if sort_cols:
            bs = bs.sort_values(sort_cols, na_position="last")
        for sec, g in bs.groupby("seccion", dropna=False):
            sec_key = _normalize_key(sec)
            summary_by_sec[sec_key] = []
            for _, row in g.iterrows():
                clave = row.get("clave_casilla") or row.get("tipo_casilla") or "Casilla"
                summary_by_sec[sec_key].append({
                    "clave": str(clave),
                    "promovidos": _safe_int(row.get("promovidos")),
                    "coordinadores": _safe_int(row.get("coordinadores_con_promovidos")),
                })

    rows = []
    for _, row in base.iterrows():
        sec_key = _normalize_key(row.get("numero"))
        merged = []
        seen = {}
        for item in catalog_by_sec.get(sec_key, []):
            clone = dict(item)
            merged.append(clone)
            seen[clone["clave"]] = clone
        for item in summary_by_sec.get(sec_key, []):
            if item["clave"] in seen:
                seen[item["clave"]]["promovidos"] = item["promovidos"]
                seen[item["clave"]]["coordinadores"] = item["coordinadores"]
            else:
                clone = dict(item)
                merged.append(clone)
                seen[clone["clave"]] = clone
        html_parts = [f"{html.escape(str(it['clave']))}: {it['promovidos']}" for it in merged]
        text_parts = [f"{it['clave']}: {it['promovidos']}" for it in merged]
        pending = _safe_int(row.get("promovidos_sin_casilla"))
        if pending > 0:
            html_parts.append(f"Pendientes: {pending}")
            text_parts.append(f"Pendientes: {pending}")
        if not html_parts:
            html_parts = ["Sin catálogo de casillas activo"]
            text_parts = ["Sin catálogo de casillas activo"]
        rec = row.to_dict()
        # El tooltip de PyDeck escapa el HTML contenido dentro de propiedades
        # dinámicas. Mantener el dato como texto puro evita mostrar <br/> o </b>.
        rec["casillas_resumen_html"] = " • ".join(text_parts)
        rec["casillas_resumen_text"] = " • ".join(text_parts)
        rec["casillas_resumen_tooltip"] = " • ".join(text_parts)
        rec["casillas_detalle_lista"] = merged
        rows.append(rec)
    return pd.DataFrame(rows)


def _selection_object(event):
    try:
        selection = event.selection
    except Exception:
        try:
            selection = event.get("selection", {})
        except Exception:
            selection = {}
    try:
        objects = selection.get("objects", {})
    except Exception:
        objects = getattr(selection, "objects", {}) or {}
    picked = objects.get(LAYER_ID, []) if isinstance(objects, dict) else []
    if not picked:
        return None
    obj = picked[0]
    if isinstance(obj, dict) and isinstance(obj.get("properties"), dict):
        return obj["properties"]
    return obj if isinstance(obj, dict) else None


def _section_row(df: pd.DataFrame, section_value):
    if df.empty or section_value is None:
        return None
    mask = pd.to_numeric(df["numero"], errors="coerce") == pd.to_numeric(pd.Series([section_value]), errors="coerce").iloc[0]
    m = df[mask]
    return None if m.empty else m.iloc[0]


def _render_kpi_card(title: str, value: int | str):
    st.markdown(
        f"""
        <div style="padding:14px 16px;border:1px solid #E7EBF0;border-radius:14px;background:#F8FAFC;">
            <div style="font-size:0.85rem;color:#6B7280;margin-bottom:6px;">{html.escape(str(title))}</div>
            <div style="font-size:2rem;font-weight:700;line-height:1.1;color:#1F2A44;">{html.escape(str(value))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_section_summary(row):
    municipality = row.get("municipio") or "No disponible"
    dl = row.get("distrito_local") if pd.notna(row.get("distrito_local")) else "N/D"
    dfed = row.get("distrito_federal") if pd.notna(row.get("distrito_federal")) else "N/D"
    tipo = row.get("tipo_seccion") or "No disponible"
    mayor = row.get("coordinador_mayor_estructura") or "Sin registros"
    st.markdown(
        f"""
        <div style="padding:18px;border-radius:16px;background:linear-gradient(135deg,#7D1D24 0%,#AF272F 100%);color:white;">
            <div style="font-size:0.9rem;opacity:.9;">Detalle de sección</div>
            <div style="font-size:2rem;font-weight:800;margin-top:6px;">Sección {html.escape(str(_safe_int(row.get('numero')) or row.get('numero')))}</div>
            <div style="margin-top:8px;font-size:0.95rem;opacity:.95;">{html.escape(str(municipality))} · DL {html.escape(str(dl))} · DF {html.escape(str(dfed))}</div>
            <div style="margin-top:12px;display:inline-block;padding:6px 10px;border-radius:999px;background:rgba(255,255,255,.12);font-size:.85rem;">Tipo: {html.escape(str(tipo))}</div>
            <div style="margin-top:12px;font-size:0.95rem;"><b>Mayor estructura:</b> {html.escape(str(mayor))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_detail_panel(row, booth_detail: pd.DataFrame):
    if row is None:
        st.subheader("Detalle de sección")
        st.info("Haz clic sobre una sección del mapa para ver su ficha operativa.")
        st.caption("El hover solo muestra un resumen rápido para mantener la cartografía despejada.")
        return

    _render_section_summary(row)
    st.write("")
    a, b = st.columns(2)
    with a:
        _render_kpi_card("Promovidos", _safe_int(row.get("promovidos")))
    with b:
        _render_kpi_card("Coordinadores", _safe_int(row.get("coordinadores")))
    c, d = st.columns(2)
    with c:
        _render_kpi_card("Casillas catalogadas", _safe_int(row.get("casillas_catalogadas")))
    with d:
        _render_kpi_card("Pendientes sin casilla", _safe_int(row.get("promovidos_sin_casilla")))

    st.write("")
    with st.container(border=True):
        st.markdown("#### Ubicación y lectura operativa")
        u1, u2 = st.columns(2)
        u1.markdown(f"**Municipio:** {row.get('municipio') or 'No disponible'}")
        u1.markdown(f"**Distrito local:** {row.get('distrito_local') if pd.notna(row.get('distrito_local')) else 'N/D'}")
        u2.markdown(f"**Distrito federal:** {row.get('distrito_federal') if pd.notna(row.get('distrito_federal')) else 'N/D'}")
        u2.markdown(f"**Tipo de sección:** {row.get('tipo_seccion') or 'No disponible'}")

    st.write("")
    with st.container(border=True):
        st.markdown("#### Promovidos por casilla")
        detail_list = row.get("casillas_detalle_lista") or []
        if detail_list:
            display = pd.DataFrame(detail_list)
            display["promovidos"] = pd.to_numeric(display["promovidos"], errors="coerce").fillna(0).astype(int)
            display["coordinadores"] = pd.to_numeric(display.get("coordinadores", 0), errors="coerce").fillna(0).astype(int)
            display = display.rename(columns={"clave": "Casilla", "promovidos": "Promovidos", "coordinadores": "Coordinadores"})
            if "Coordinadores" not in display.columns:
                display["Coordinadores"] = 0
            st.dataframe(display[[c for c in ["Casilla", "Promovidos", "Coordinadores"] if c in display.columns]], use_container_width=True, hide_index=True, height=min(320, 42 + 36 * max(1, len(display))))
        else:
            st.info("Sin catálogo de casillas activo para esta sección.")
        pending = _safe_int(row.get("promovidos_sin_casilla"))
        if pending:
            st.warning(f"Pendientes de casilla exacta: {pending}")
        else:
            st.success("Sin pendientes de casilla exacta en esta sección.")



page_header(
    "Mapa territorial V3.3.2",
    "Vista operativa ampliada por sección: cobertura, promovidos y casillas. Haz clic en una sección para ver su ficha a la derecha.",
)

mode = active_mode()
client = None
booth_detail = pd.DataFrame()
booth_catalog = pd.DataFrame()
if mode == "LOCAL":
    booth_detail = _prepare_booth_detail(get_local_booth_summary())
    booth_catalog = _prepare_booth_catalog_local()
    df = _build_section_booth_display(get_local_sections(), booth_detail, booth_catalog)
    st.caption("🟢 Cartografía poligonal precargada")
elif mode == "SUPABASE":
    client = optional_client()
    if client is None:
        st.stop()
    booth_detail = _prepare_booth_detail(booths_dataframe(client))
    booth_catalog = _prepare_booth_catalog_supabase(client)
    df = _build_section_booth_display(sections_dataframe(client), booth_detail, booth_catalog)
else:
    st.info("Carga datos primero.")
    st.stop()

if df.empty:
    st.stop()

# V3.3: se retira el bloque técnico de Fuente cartográfica del flujo visual.
c1, c2, c3, c4 = st.columns(4)
muni = c1.selectbox("Municipio", ["TODOS"] + sorted(df["municipio"].dropna().astype(str).unique().tolist()))
dl = c2.selectbox("Distrito local", ["TODOS"] + sorted(pd.to_numeric(df["distrito_local"], errors="coerce").dropna().astype(int).unique().tolist()))
dfederal = c3.selectbox("Distrito federal", ["TODOS"] + sorted(pd.to_numeric(df["distrito_federal"], errors="coerce").dropna().astype(int).unique().tolist()))
pres = c4.selectbox("Cobertura", ["TODAS", "CON REGISTROS", "SIN REGISTROS"])
metric = st.selectbox("Intensidad del mapa", ["promovidos", "coordinadores", "casillas_catalogadas", "promovidos_sin_casilla"])

f = df.copy()
if muni != "TODOS":
    f = f[f["municipio"] == muni]
if dl != "TODOS":
    f = f[pd.to_numeric(f["distrito_local"], errors="coerce") == int(dl)]
if dfederal != "TODOS":
    f = f[pd.to_numeric(f["distrito_federal"], errors="coerce") == int(dfederal)]
if pres == "CON REGISTROS":
    f = f[f["promovidos"].fillna(0) > 0]
elif pres == "SIN REGISTROS":
    f = f[f["promovidos"].fillna(0) == 0]

collection = build_geojson_with_metrics(f, f["numero"].tolist())
maxv = max([float((feat.get("properties") or {}).get(metric) or 0) for feat in collection.get("features", [])] + [1.0])
row_map = {_normalize_key(r.get("numero")): r for _, r in f.iterrows()}

# Paleta MORENA reforzada. Se usa un guinda visible incluso con pocos registros
# y se intensifica de forma progresiva para que el mapa no se vea pálido.
soft = (220, 132, 140)   # guinda claro, claramente visible
base = (175, 39, 47)     # #AF272F
for feat in collection.get("features", []):
    props = feat.get("properties") or {}
    sec_key = _normalize_key(props.get("seccion"))
    row = row_map.get(sec_key)
    if row is not None:
        props["casillas_resumen_html"] = row.get("casillas_resumen_html", "Sin catálogo de casillas activo")
        props["casillas_resumen_text"] = row.get("casillas_resumen_text", "Sin catálogo de casillas activo")
        props["casillas_resumen_tooltip"] = row.get("casillas_resumen_tooltip", row.get("casillas_resumen_text", "Sin catálogo de casillas activo"))
    metric_value = float(props.get(metric) or 0)
    raw_intensity = min(1.0, metric_value / maxv)
    # Curva de raíz cuadrada: hace visibles las secciones de baja presencia sin
    # perder el contraste de las secciones con mayor concentración.
    intensity = raw_intensity ** 0.5
    has_records = int(props.get("promovidos") or 0) > 0
    if has_records:
        visible_intensity = 0.28 + (0.72 * intensity)
        props["fill_r"] = int(soft[0] + (base[0] - soft[0]) * visible_intensity)
        props["fill_g"] = int(soft[1] + (base[1] - soft[1]) * visible_intensity)
        props["fill_b"] = int(soft[2] + (base[2] - soft[2]) * visible_intensity)
        props["fill_a"] = int(165 + 60 * intensity)
    else:
        props["fill_r"] = 255
        props["fill_g"] = 255
        props["fill_b"] = 255
        props["fill_a"] = 0

if not collection.get("features"):
    st.warning("No hay polígonos para los filtros seleccionados.")
    st.stop()

lat_series = pd.to_numeric(f.get("centroide_lat"), errors="coerce")
lon_series = pd.to_numeric(f.get("centroide_lon"), errors="coerce")
lat = float(lat_series.dropna().mean()) if lat_series.notna().any() else 25.0
lon = float(lon_series.dropna().mean()) if lon_series.notna().any() else -107.5
zoom = 8 if muni != "TODOS" else 6

layer = pdk.Layer(
    "GeoJsonLayer",
    collection,
    id=LAYER_ID,
    pickable=True,
    auto_highlight=True,
    stroked=True,
    filled=True,
    get_fill_color="[properties.fill_r, properties.fill_g, properties.fill_b, properties.fill_a]",
    get_line_color="[70, 70, 70, 185]",
    line_width_min_pixels=0.8,
    highlight_color=[255, 193, 7, 210],
)

tooltip = {
    "html": "<div style='min-width:240px'><b>Sección {seccion}</b><br/>Promovidos: {promovidos}<br/><b>Promovidos por casilla:</b><br/><span>{casillas_resumen_tooltip}</span><br/><span style='opacity:.8'>Clic para detalle</span></div>",
    "style": {
        "backgroundColor": "#2B2024",
        "color": "white",
        "fontSize": "14px",
        "padding": "10px 12px",
        "borderRadius": "8px",
    },
}

deck = pdk.Deck(
    layers=[layer],
    initial_view_state=pdk.ViewState(latitude=lat, longitude=lon, zoom=zoom),
    tooltip=tooltip,
    map_style=None,
)

# V3.3: mapa más alto y ficha fija a la derecha.
map_col, detail_col = st.columns([4.8, 1.65], gap="large")
with map_col:
    event = st.pydeck_chart(
        deck,
        use_container_width=True,
        height=980,
        on_select="rerun",
        selection_mode="single-object",
        key="icc_mapa_secciones_v332",
    )

selected = _selection_object(event)
selected_section = selected.get("seccion") if selected else None
if selected_section is not None:
    st.session_state["icc_selected_section"] = selected_section
elif "icc_selected_section" in st.session_state:
    selected_section = st.session_state["icc_selected_section"]

selected_row = _section_row(f, selected_section)
with detail_col:
    _render_detail_panel(selected_row, booth_detail)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Polígonos", f"{len(f):,}")
m2.metric("Con registros", f"{int((f['promovidos'].fillna(0) > 0).sum()):,}")
m3.metric("Promovidos", f"{int(f['promovidos'].fillna(0).sum()):,}")
m4.metric("Coordinadores", f"{int(f['coordinadores'].fillna(0).sum()):,}")
st.caption("Las secciones con información se muestran en escala guinda MORENA reforzada; las secciones sin registros quedan transparentes con contorno.")
