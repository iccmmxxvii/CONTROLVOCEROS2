from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from core.config import get_settings
from core.db import create_import, find_import_by_hash, get_client, insert_incidents, insert_normalized_records, insert_raw_records, sha256_bytes
from core.hierarchy import infer_root, resolve_parent_map
from core.local_store import activate_local_dataset, get_local_booths, get_local_payload, set_local_booths
from core.import_commit import confirm_import
from core.import_excel import build_raw_records, normalize_dataframe, normalized_records, read_excel_bytes
from core.historical_booths import fetch_iees_historical_2024
from core.ui import page_header

page_header("Carga múltiple desde Excel", "Carga uno o varios archivos y consolídalos antes de persistir en Supabase")

@st.cache_data(show_spinner=False)
def _process_excel_cached(data: bytes):
    """Procesa cada archivo una sola vez por contenido, evitando reprocesarlo en cada rerun de Streamlit."""
    raw, sheets = read_excel_bytes(data)
    normalized, incidents, mapping = normalize_dataframe(raw)
    root = infer_root(normalized.to_dict("records") if not normalized.empty else [])
    _, conflicts = resolve_parent_map(normalized.to_dict("records") if not normalized.empty else [])
    return raw, sheets, normalized, incidents, mapping, root, conflicts

st.success("Carga rápida habilitada: los Excel se procesan por contenido una sola vez durante la sesión. VOCEROS se interpreta como PROMOVIDOS y cada archivo conserva su origen.")
with st.expander("Formato reconocido", expanded=False):
    st.markdown("""
**Base:** `GRUPO 1`, `GRUPO 2`, `GRUPO 3`, `GRUPO 4`, `VOCEROS/PROMOVIDOS`, `CELULAR`, `SECCION`, `MUNICIPIO`.

**Opcionales preparados:** `APELLIDO PATERNO`, `APELLIDO MATERNO`, `CASILLA`, `CALLE`, `COLONIA`, `LOCALIDAD`, `CP`, `REFERENCIAS`.

Si el Excel no trae apellidos separados, V3 intenta derivarlos desde el nombre completo y conserva `origen` y `confianza` de esa inferencia. La casilla solo se asigna cuando el catálogo y los criterios disponibles producen una correspondencia única.

Los archivos se consolidan en memoria para pruebas. El RAW original no se modifica.
""")
    template_path = Path(__file__).resolve().parents[1] / "templates" / "plantilla_carga_estructura.xlsx"
    if template_path.exists():
        st.download_button("Descargar plantilla Excel", template_path.read_bytes(), "plantilla_carga_estructura.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

auto_hist = st.checkbox("Actualizar catálogo histórico de casillas IEES 2024 si aún no está disponible", value=True, help="Se usa solo como referencia histórica. Cuando INE/IEES publique el catálogo vigente se podrá sustituir sin perder la base de personas.")

uploaded_files = st.file_uploader("Selecciona uno o varios Excel", type=["xlsx", "xlsm", "xls"], accept_multiple_files=True)
if not uploaded_files:
    payload = get_local_payload()
    if payload:
        st.info(f"Ya hay una base temporal activa con {len(payload.get('files', []))} archivo(s). Puedes seguir navegando o agregar más archivos aquí.")
        st.dataframe(pd.DataFrame(payload.get("files", [])), use_container_width=True, hide_index=True)
    else:
        st.info("Carga el primer Excel. Podrás agregar otros después sin perder la base temporal durante esta sesión.")
    st.stop()

st.subheader("Vista previa de archivos")
processed = []
for up in uploaded_files:
    try:
        data = up.getvalue()
        with st.spinner(f"Procesando {up.name}..."):
            raw, sheets, normalized, incidents, mapping, root, conflicts = _process_excel_cached(data)
        processed.append({"upload": up, "bytes": data, "raw": raw, "sheet": sheets[0], "normalized": normalized, "incidents": incidents, "mapping": mapping, "root": root, "conflicts": conflicts})
    except Exception as exc:
        st.error(f"{up.name}: no fue posible procesarlo: {exc}")

if not processed:
    st.stop()

summary_rows = []
for item in processed:
    n = item["normalized"]
    summary_rows.append({
        "archivo": item["upload"].name,
        "filas_excel": len(item["raw"]),
        "registros": len(n),
        "secciones": int(n["seccion"].nunique()) if not n.empty else 0,
        "raiz_inferida": item["root"],
        "revisar": int((n["estado_validacion"] == "REVISAR").sum()) if not n.empty else 0,
        "bloqueados": int((n["estado_validacion"] == "BLOQUEADO").sum()) if not n.empty else 0,
        "conflictos_jerarquia": len(item["conflicts"]),
    })
st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

st.subheader("Agregar a la base temporal")
replace = st.radio("¿Qué hacer con la base temporal actual?", ["Acumular con lo ya cargado", "Reemplazar y comenzar de nuevo"], horizontal=True)
structure_names = {}
for item in processed:
    default = f"Estructura {(item['root'] or Path(item['upload'].name).stem).title()}"
    structure_names[item["upload"].name] = st.text_input(f"Nombre de estructura · {item['upload'].name}", value=default, key=f"struct_{item['upload'].name}")

if st.button("📥 Activar / acumular archivos", type="primary", use_container_width=True):
    append = replace.startswith("Acumular") and bool(get_local_payload())
    for i, item in enumerate(processed):
        activate_local_dataset(item["normalized"], item["incidents"], structure_names[item["upload"].name], item["upload"].name, append=(append or i > 0))
    p = get_local_payload()
    hist_msg = None
    if auto_hist and get_local_booths().empty:
        try:
            with st.spinner("Precargando catálogo histórico de casillas IEES 2024..."):
                hist_booths, hist_meta = fetch_iees_historical_2024()
                set_local_booths(hist_booths, hist_meta)
                hist_msg = f"Catálogo histórico 2024 cargado: {len(hist_booths):,} casillas en {hist_booths['seccion'].nunique():,} secciones."
        except Exception as exc:
            hist_msg = f"No se pudo descargar automáticamente el catálogo histórico; la plataforma continúa y el sistema conservará los promovidos como pendientes hasta contar con el catálogo. Detalle: {exc}"
    p = get_local_payload()
    st.success(f"Base temporal consolidada: {len(p.get('files', []))} archivo(s), {len(p.get('people', pd.DataFrame()))} personas en red y {int((p.get('sections', pd.DataFrame()).get('promovidos', pd.Series(dtype=int)).fillna(0) > 0).sum())} secciones con registros.")
    if hist_msg:
        st.info(hist_msg)
    st.rerun()

payload = get_local_payload()
if payload:
    st.divider(); st.subheader("Base temporal acumulada")
    files_df = pd.DataFrame(payload.get("files", []))
    st.dataframe(files_df, use_container_width=True, hide_index=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Archivos", len(files_df))
    c2.metric("Personas en red", len(payload.get("people", pd.DataFrame())))
    c3.metric("Secciones cartografía", len(payload.get("sections", pd.DataFrame())))
    c4.metric("Conflictos jerárquicos", len(payload.get("hierarchy_conflicts", [])))
    cnav1, cnav2, cnav3 = st.columns(3)
    cnav1.page_link("pages/00_Dashboard.py", label="🏠 Dashboard", use_container_width=True)
    cnav2.page_link("pages/04_Secciones.py", label="🧭 Reporte de secciones", use_container_width=True)
    cnav3.page_link("pages/03_Estructura.py", label="🌳 Estructura", use_container_width=True)

st.divider(); st.subheader("Persistencia en Supabase (opcional durante pruebas)")
st.caption("Para persistir, guarda y confirma cada archivo por separado. La consolidación temporal puede seguir usándose sin Supabase.")
settings = get_settings(); client = None
if settings.database_configured:
    try: client = get_client(settings.supabase_url, settings.supabase_key)
    except Exception as exc: st.warning(f"Supabase no disponible: {exc}")
else:
    st.info("Supabase todavía no es obligatorio. La base temporal acumulada funciona durante la sesión.")

if client is not None:
    selected_name = st.selectbox("Archivo a persistir", [x["upload"].name for x in processed])
    item = next(x for x in processed if x["upload"].name == selected_name)
    structure_name = structure_names[selected_name]
    file_hash = sha256_bytes(item["bytes"])
    try:
        previous = find_import_by_hash(client, file_hash)
        if previous: st.warning(f"Este archivo ya aparece {len(previous)} vez/veces en Supabase.")
    except Exception: pass
    key = f"persisted_{file_hash}"
    c1, c2 = st.columns(2)
    if c1.button("1. Guardar archivo en staging", use_container_width=True):
        try:
            import_id = create_import(client, selected_name, item["bytes"], item["sheet"], len(item["raw"]), structure_name=structure_name)
            insert_raw_records(client, import_id, build_raw_records(item["raw"]))
            insert_normalized_records(client, import_id, normalized_records(item["normalized"]))
            insert_incidents(client, import_id, item["incidents"].to_dict("records") if not item["incidents"].empty else [])
            st.session_state[key] = import_id; st.success(f"Staging guardado: {import_id}")
        except Exception as exc: st.exception(exc)
    import_id = st.session_state.get(key)
    if c2.button("2. Confirmar importación", disabled=not import_id, use_container_width=True):
        try:
            result = confirm_import(client, import_id, structure_name=structure_name, allow_provisional_sections=True)
            st.success("Importación confirmada."); st.json(result); st.session_state.pop(key, None)
        except Exception as exc: st.exception(exc)
