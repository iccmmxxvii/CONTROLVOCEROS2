from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from core.local_store import (
    get_local_booth_assignments,
    get_local_booth_catalog_meta,
    get_local_booths,
    get_local_normalized,
    get_local_sections,
)
from core.report_export import executive_excel_bytes
from core.casillas import is_exact_assignment_status, is_suggested_assignment_status
from core.runtime import active_mode
from core.ui import page_header

GUINDA = "#AF272F"
GUINDA_DARK = "#7D1D24"
GUINDA_SOFT = "#F4DADC"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _num(value) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _unique_join(values) -> str:
    clean = sorted({str(x).strip() for x in values if pd.notna(x) and str(x).strip()})
    return ", ".join(clean)


def _section_filter(df: pd.DataFrame, municipality, dl, dfed) -> pd.DataFrame:
    out = df.copy()
    if municipality != "TODOS":
        out = out[out["municipio"].astype(str) == str(municipality)]
    if dl != "TODOS":
        out = out[pd.to_numeric(out["distrito_local"], errors="coerce") == int(dl)]
    if dfed != "TODOS":
        out = out[pd.to_numeric(out["distrito_federal"], errors="coerce") == int(dfed)]
    return out


def _normalized_filter(normalized: pd.DataFrame, group0: str, allowed_sections: set[int]) -> pd.DataFrame:
    out = normalized.copy()
    if group0 != "TODOS":
        out = out[out.get("grupo_0", pd.Series(index=out.index, dtype=object)).fillna("").astype(str) == group0]
    if allowed_sections:
        sec_num = pd.to_numeric(out.get("seccion"), errors="coerce")
        out = out[sec_num.isin(allowed_sections)]
    else:
        out = out.iloc[0:0]
    return out


def _filtered_assignments(assignments: pd.DataFrame, normalized_filtered: pd.DataFrame) -> pd.DataFrame:
    if assignments.empty or normalized_filtered.empty:
        return pd.DataFrame(columns=assignments.columns if not assignments.empty else [])
    allowed = set(normalized_filtered.index.tolist())
    return assignments[assignments["registro_idx"].isin(allowed)].copy()


def _build_coverage(sections: pd.DataFrame, normalized: pd.DataFrame, assignments: pd.DataFrame) -> pd.DataFrame:
    base_cols = [c for c in [
        "numero", "municipio", "distrito_local", "distrito_federal", "tipo_seccion",
        "casillas_catalogadas"
    ] if c in sections.columns]
    base = sections[base_cols].drop_duplicates("numero").copy()
    base["numero_num"] = pd.to_numeric(base["numero"], errors="coerce")

    if normalized.empty:
        metrics = pd.DataFrame(columns=["seccion_num", "promovidos", "grupos_0_con_presencia", "grupo_0_presencia"])
    else:
        work = normalized.dropna(subset=["seccion"]).copy()
        work["seccion_num"] = pd.to_numeric(work["seccion"], errors="coerce")
        agg_spec = {"promovidos": ("promovido_normalizado", "size")}
        if "grupo_0" in work.columns:
            agg_spec["grupos_0_con_presencia"] = ("grupo_0", lambda x: len({str(v).strip() for v in x.dropna() if str(v).strip()}))
            agg_spec["grupo_0_presencia"] = ("grupo_0", _unique_join)
        metrics = work.groupby("seccion_num", dropna=False).agg(**agg_spec).reset_index()
        if "grupos_0_con_presencia" not in metrics:
            metrics["grupos_0_con_presencia"] = 0
        if "grupo_0_presencia" not in metrics:
            metrics["grupo_0_presencia"] = ""

    base = base.merge(metrics, left_on="numero_num", right_on="seccion_num", how="left")
    base["promovidos"] = pd.to_numeric(base.get("promovidos"), errors="coerce").fillna(0).astype(int)
    base["grupos_0_con_presencia"] = pd.to_numeric(base.get("grupos_0_con_presencia"), errors="coerce").fillna(0).astype(int)
    base["grupo_0_presencia"] = base.get("grupo_0_presencia", pd.Series(index=base.index, dtype=object)).fillna("")

    exact, suggested, pending = {}, {}, {}
    if not assignments.empty:
        states = assignments.get("estado_asignacion", pd.Series(index=assignments.index, dtype=object))
        exact_mask = states.map(is_exact_assignment_status) & assignments["casilla_id"].notna()
        suggested_mask = states.map(is_suggested_assignment_status) & assignments["casilla_id"].notna()
        exact = assignments[exact_mask].groupby("seccion").size().to_dict()
        suggested = assignments[suggested_mask].groupby("seccion").size().to_dict()
        pending = assignments[assignments["casilla_id"].isna()].groupby("seccion").size().to_dict()
    base["casilla_exacta"] = base["numero"].map(exact).fillna(0).astype(int)
    base["casilla_sugerida"] = base["numero"].map(suggested).fillna(0).astype(int)
    base["pendientes_casilla"] = base["numero"].map(pending).fillna(0).astype(int)
    base["estado_presencia"] = base["promovidos"].map(lambda x: "CON PRESENCIA" if int(x) > 0 else "SIN PRESENCIA")
    return base.drop(columns=[c for c in ["numero_num", "seccion_num"] if c in base.columns])


def _group0_summary(normalized: pd.DataFrame, assignments: pd.DataFrame) -> pd.DataFrame:
    if normalized.empty or "grupo_0" not in normalized.columns:
        return pd.DataFrame()
    work = normalized.dropna(subset=["grupo_0"]).copy()
    if work.empty:
        return pd.DataFrame()
    summary = work.groupby("grupo_0").agg(
        promovidos=("promovido_normalizado", "size"),
        secciones=("seccion", "nunique"),
        municipios=("municipio", "nunique") if "municipio" in work.columns else ("seccion", "nunique"),
        distritos_locales=("distrito_local", "nunique") if "distrito_local" in work.columns else ("seccion", "nunique"),
        distritos_federales=("distrito_federal", "nunique") if "distrito_federal" in work.columns else ("seccion", "nunique"),
    ).reset_index()
    return summary.sort_values(["promovidos", "secciones"], ascending=False).reset_index(drop=True)


def _territory_summary(coverage: pd.DataFrame, field: str, label: str) -> pd.DataFrame:
    if coverage.empty or field not in coverage.columns:
        return pd.DataFrame()
    g = coverage.groupby(field, dropna=False).agg(
        secciones=("numero", "nunique"),
        secciones_con_presencia=("estado_presencia", lambda x: int((x == "CON PRESENCIA").sum())),
        secciones_sin_presencia=("estado_presencia", lambda x: int((x == "SIN PRESENCIA").sum())),
        promovidos=("promovidos", "sum"),
    ).reset_index()
    g["cobertura_pct"] = (g["secciones_con_presencia"] / g["secciones"].replace(0, pd.NA) * 100).fillna(0).round(1)
    return g.rename(columns={field: label}).sort_values(["cobertura_pct", "promovidos"], ascending=False)


def _booth_executive(booths: pd.DataFrame, coverage: pd.DataFrame, assignments: pd.DataFrame) -> pd.DataFrame:
    cols = ["Casilla", "Sección", "Municipio", "Distrito local", "Distrito federal", "Promovidos totales"]
    if booths.empty:
        return pd.DataFrame(columns=cols)

    sec_allowed = set(pd.to_numeric(coverage.get("numero"), errors="coerce").dropna().astype(int).tolist())
    b = booths[pd.to_numeric(booths.get("seccion"), errors="coerce").isin(sec_allowed)].copy()
    if b.empty:
        return pd.DataFrame(columns=cols)

    sec_meta = coverage[[c for c in ["numero", "municipio", "distrito_local", "distrito_federal"] if c in coverage.columns]].drop_duplicates("numero")
    b["seccion_num"] = pd.to_numeric(b["seccion"], errors="coerce")
    sec_meta["seccion_num"] = pd.to_numeric(sec_meta["numero"], errors="coerce")
    b = b.merge(sec_meta.drop(columns=["numero"]), on="seccion_num", how="left", suffixes=("", "_sec"))

    all_assigned = {}
    if not assignments.empty and "casilla_id" in assignments.columns:
        all_assigned = assignments[assignments["casilla_id"].notna()].groupby("casilla_id").size().to_dict()

    result = pd.DataFrame({
        "Casilla": b.get("clave_casilla", b.get("tipo_casilla")),
        "Sección": b["seccion"],
        "Municipio": b.get("municipio_sec", b.get("municipio")),
        "Distrito local": b.get("distrito_local_sec", b.get("distrito_local")),
        "Distrito federal": b.get("distrito_federal_sec", b.get("distrito_federal")),
        "Promovidos totales": b["casilla_id"].map(all_assigned).fillna(0).astype(int),
    })
    return result.sort_values(["Municipio", "Sección", "Casilla"], na_position="last").reset_index(drop=True)


def _download_xlsx(df: pd.DataFrame, label: str, filename: str, key: str):
    if df is None or df.empty:
        return
    data = executive_excel_bytes({label[:31]: df}, title=f"ICC Control Territorial - {label}")
    st.download_button(
        f"⬇️ Descargar tabla {label}",
        data=data,
        file_name=filename,
        mime=XLSX_MIME,
        key=key,
    )


def _clean_display(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in out.columns:
        if out[c].dtype == object:
            out[c] = out[c].fillna("No disponible")
    return out


page_header(
    "Reportes ejecutivos V3.3",
    "Concentrados operativos por Grupo 0, cobertura, distritos y casillas. Cada tabla puede descargarse de forma independiente.",
)

if active_mode() != "LOCAL":
    st.info("Los reportes ejecutivos están habilitados para la base precargada/local V3.3.")
    st.stop()

normalized_all = get_local_normalized()
sections_all = get_local_sections()
assignments_all = get_local_booth_assignments()
booths = get_local_booths()
booth_meta = get_local_booth_catalog_meta()

if normalized_all.empty or sections_all.empty:
    st.warning("No hay base operativa disponible.")
    st.stop()

g0_values = sorted(normalized_all.get("grupo_0", pd.Series(dtype=str)).dropna().astype(str).unique().tolist())
municipalities = sorted(sections_all.get("municipio", pd.Series(dtype=str)).dropna().astype(str).unique().tolist())
dl_values = sorted(pd.to_numeric(sections_all.get("distrito_local"), errors="coerce").dropna().astype(int).unique().tolist())
df_values = sorted(pd.to_numeric(sections_all.get("distrito_federal"), errors="coerce").dropna().astype(int).unique().tolist())

f1, f2, f3, f4 = st.columns([1.5, 1.25, 1, 1])
g0 = f1.selectbox("Grupo 0", ["TODOS"] + g0_values)
municipality = f2.selectbox("Municipio", ["TODOS"] + municipalities)
dl = f3.selectbox("Distrito local", ["TODOS"] + dl_values)
dfed = f4.selectbox("Distrito federal", ["TODOS"] + df_values)

sections_filtered = _section_filter(sections_all, municipality, dl, dfed)
allowed_sections = set(pd.to_numeric(sections_filtered["numero"], errors="coerce").dropna().astype(int).tolist())
normalized = _normalized_filter(normalized_all, g0, allowed_sections)
assignments = _filtered_assignments(assignments_all, normalized)
coverage = _build_coverage(sections_filtered, normalized, assignments)
g0_summary = _group0_summary(normalized, assignments)
mun_summary = _territory_summary(coverage, "municipio", "Municipio")
dl_summary = _territory_summary(coverage, "distrito_local", "Distrito local")
df_summary = _territory_summary(coverage, "distrito_federal", "Distrito federal")
booth_exec = _booth_executive(booths, coverage, assignments)

with_records = int((coverage["promovidos"] > 0).sum()) if not coverage.empty else 0
without_records = int((coverage["promovidos"] == 0).sum()) if not coverage.empty else 0
if assignments.empty:
    assigned_exact, assigned_suggested, pending_exact = 0, 0, len(normalized)
else:
    states = assignments.get("estado_asignacion", pd.Series(index=assignments.index, dtype=object))
    assigned_exact = int((states.map(is_exact_assignment_status) & assignments["casilla_id"].notna()).sum())
    assigned_suggested = int((states.map(is_suggested_assignment_status) & assignments["casilla_id"].notna()).sum())
    pending_exact = int(assignments["casilla_id"].isna().sum())

k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
k1.metric("Promovidos", f"{len(normalized):,}")
k2.metric("Grupos 0", f"{normalized.get('grupo_0', pd.Series(dtype=str)).nunique():,}")
k3.metric("Secciones con presencia", f"{with_records:,}")
k4.metric("Secciones sin presencia", f"{without_records:,}")
k5.metric("Casilla exacta", f"{assigned_exact:,}")
k6.metric("Casilla sugerida", f"{assigned_suggested:,}")
k7.metric("Pendientes", f"{pending_exact:,}")

caption = f"Filtro activo: Grupo 0 = {g0} · Municipio = {municipality} · DL = {dl} · DF = {dfed}."
if booth_meta:
    caption += f" Casillas: {booth_meta.get('estatus', 'sin estatus')} ({booth_meta.get('origen_carga', booth_meta.get('fuente', 'catálogo'))})."
st.caption(caption)

# V3.3: sin botón global de Excel. Cada tabla descarga su propio Excel.
r1, r2, r3, r4 = st.tabs(["Resumen ejecutivo", "Grupo 0", "Cobertura territorial", "Casillas"])

with r1:
    left, right = st.columns([1.25, 1])
    with left:
        st.markdown("### Promovidos por Grupo 0")
        if g0_summary.empty:
            st.info("Sin registros para el filtro.")
        else:
            chart = g0_summary.head(15).set_index("grupo_0")["promovidos"]
            st.bar_chart(chart, color=GUINDA, height=420)
    with right:
        st.markdown("### Cobertura del filtro")
        total_sections = len(coverage)
        pct = (with_records / total_sections * 100) if total_sections else 0
        st.metric("Cobertura de secciones", f"{pct:.1f}%")
        st.write(f"**Municipios con presencia:** {normalized.get('municipio', pd.Series(dtype=str)).nunique():,}")
        st.write(f"**Distritos locales con presencia:** {pd.to_numeric(normalized.get('distrito_local'), errors='coerce').nunique():,}")
        st.write(f"**Distritos federales con presencia:** {pd.to_numeric(normalized.get('distrito_federal'), errors='coerce').nunique():,}")

    st.markdown("### Cobertura por municipio")
    if not mun_summary.empty:
        muni_disp = mun_summary.rename(columns={
            "secciones": "Secciones", "secciones_con_presencia": "Con presencia",
            "secciones_sin_presencia": "Sin presencia", "promovidos": "Promovidos", "cobertura_pct": "Cobertura %"
        })
        st.dataframe(muni_disp.style.bar(subset=["Cobertura %"], color=GUINDA_SOFT), use_container_width=True, hide_index=True, height=480)
        _download_xlsx(muni_disp, "Municipios", "reporte_municipios.xlsx", "dl_municipios_xlsx")

with r2:
    st.markdown("### Concentrado por Grupo 0")
    if g0_summary.empty:
        st.info("Sin información para el filtro.")
    else:
        disp = g0_summary.rename(columns={
            "grupo_0": "Grupo 0", "promovidos": "Promovidos", "secciones": "Secciones",
            "municipios": "Municipios", "distritos_locales": "DL", "distritos_federales": "DF"
        })
        st.dataframe(disp.style.bar(subset=["Promovidos"], color=GUINDA_SOFT), use_container_width=True, hide_index=True, height=450)
        _download_xlsx(disp, "Grupo 0", "reporte_grupo0.xlsx", "dl_grupo0_xlsx")

with r3:
    st.markdown("### Secciones: presencia y ausencia")
    c1, c2 = st.columns([1.3, 1])
    with c1:
        presence_filter = st.selectbox("Mostrar", ["TODAS", "CON PRESENCIA", "SIN PRESENCIA"], key="rep_presence_filter_v33")
    with c2:
        q = st.text_input("Buscar sección", placeholder="Ej. 2329", key="rep_section_search_v33")

    coverage_export = coverage.rename(columns={
        "numero": "Sección", "municipio": "Municipio", "distrito_local": "Distrito local",
        "distrito_federal": "Distrito federal", "tipo_seccion": "Tipo sección",
        "promovidos": "Promovidos", "grupos_0_con_presencia": "Grupos 0 con presencia",
        "grupo_0_presencia": "Grupo 0 presencia", "casillas_catalogadas": "Casillas catalogadas",
        "casilla_exacta": "Casilla exacta", "casilla_sugerida": "Casilla sugerida",
        "pendientes_casilla": "Pendientes casilla", "estado_presencia": "Estado presencia",
    })
    sec = coverage_export.copy()
    if presence_filter != "TODAS":
        sec = sec[sec["Estado presencia"] == presence_filter]
    if q:
        sec = sec[sec["Sección"].astype(str).str.contains(q, regex=False)]
    display_cols = [c for c in [
        "Sección", "Municipio", "Distrito local", "Distrito federal", "Tipo sección",
        "Promovidos", "Grupos 0 con presencia", "Grupo 0 presencia", "Casillas catalogadas",
        "Casilla exacta", "Casilla sugerida", "Pendientes casilla", "Estado presencia"
    ] if c in sec.columns]
    sec_disp = sec[display_cols]
    st.dataframe(sec_disp, use_container_width=True, hide_index=True, height=560)
    _download_xlsx(sec_disp, "Cobertura por sección", "cobertura_secciones.xlsx", "dl_secciones_xlsx")

    st.markdown("### Distritos")
    d1, d2 = st.columns(2)
    with d1:
        st.markdown("#### Distrito local")
        if not dl_summary.empty:
            dl_disp = dl_summary.rename(columns={
                "secciones": "Secciones", "secciones_con_presencia": "Con presencia",
                "secciones_sin_presencia": "Sin presencia", "promovidos": "Promovidos", "cobertura_pct": "Cobertura %"
            })
            st.dataframe(dl_disp.style.bar(subset=["Cobertura %"], color=GUINDA_SOFT), use_container_width=True, hide_index=True, height=380)
            _download_xlsx(dl_disp, "Distritos locales", "distritos_locales.xlsx", "dl_local_xlsx")
    with d2:
        st.markdown("#### Distrito federal")
        if not df_summary.empty:
            df_disp = df_summary.rename(columns={
                "secciones": "Secciones", "secciones_con_presencia": "Con presencia",
                "secciones_sin_presencia": "Sin presencia", "promovidos": "Promovidos", "cobertura_pct": "Cobertura %"
            })
            st.dataframe(df_disp.style.bar(subset=["Cobertura %"], color=GUINDA_SOFT), use_container_width=True, hide_index=True, height=380)
            _download_xlsx(df_disp, "Distritos federales", "distritos_federales.xlsx", "dl_federal_xlsx")

with r4:
    st.markdown("### Promovidos por casilla")
    if booth_meta:
        st.caption(f"Catálogo activo: {booth_meta.get('proceso', '')} · {booth_meta.get('estatus', '')} · {booth_meta.get('registros', len(booths)):,} registros")

    booth_q = st.text_input("Buscar casilla o sección", key="booth_q_report_v33")
    bv = booth_exec.copy()
    if booth_q:
        txt = bv.get("Casilla", pd.Series(index=bv.index, dtype=str)).fillna("").astype(str) + " " + bv.get("Sección", pd.Series(index=bv.index, dtype=str)).fillna("").astype(str)
        bv = bv[txt.str.contains(booth_q, case=False, regex=False)]

    st.caption("Concentrado ejecutivo: Casilla, sección, municipio, distritos y promovidos totales. No se muestran IDs internos ni se separan roles.")
    bv = _clean_display(bv)
    st.dataframe(bv, use_container_width=True, hide_index=True, height=560)
    _download_xlsx(bv, "Casillas", "reporte_casillas.xlsx", "dl_casillas_xlsx")
