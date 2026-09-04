from __future__ import annotations

import streamlit as st

from core.import_commit import confirm_import
from core.local_store import get_local_incidents, local_imports_dataframe
from core.queries import imports_dataframe, incidents_dataframe
from core.runtime import active_mode, optional_client
from core.ui import page_header

page_header("Importaciones", "Historial, incidencias y cargas temporales")
mode = active_mode()
if mode == "LOCAL":
    df = local_imports_dataframe(); inc = get_local_incidents()
    st.caption("🟢 Historial de la sesión actual")
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.subheader("Incidencias")
    if inc.empty: st.success("Sin incidencias registradas.")
    else: st.dataframe(inc, use_container_width=True, hide_index=True, height=380)
    st.info("Esta carga es temporal y no está persistida. Para conservarla entre reinicios será necesario confirmar en Supabase.")
    st.stop()
if mode != "SUPABASE": st.info("Aún no hay una base activa."); st.stop()
client = optional_client()
if client is None: st.warning("No se pudo conectar a Supabase."); st.stop()
df = imports_dataframe(client)
if df.empty: st.info("Aún no hay importaciones registradas."); st.stop()
cols = [c for c in ["created_at", "filename", "sheet_name", "structure_name", "total_rows", "status", "confirmed_at", "id"] if c in df]
st.dataframe(df[cols], use_container_width=True, hide_index=True, height=350)
labels = {f"{r['filename']} · {r['status']} · {r['id'][:8]}": r["id"] for _, r in df.iterrows()}
selected_label = st.selectbox("Revisar importación", list(labels)); import_id = labels[selected_label]
inc = incidents_dataframe(client, import_id); st.subheader("Incidencias")
if inc.empty: st.success("Sin incidencias registradas.")
else: st.dataframe(inc, use_container_width=True, hide_index=True, height=330)
row = df[df["id"] == import_id].iloc[0]
if row.get("status") in {"STAGING", "FAILED"}:
    st.warning("Esta carga no está confirmada. Puedes reintentar la confirmación desde aquí.")
    if st.button("Reintentar confirmación"):
        try:
            result = confirm_import(client, import_id, structure_name=row.get("structure_name"), allow_provisional_sections=True); st.success("Confirmación completada."); st.json(result)
        except Exception as exc: st.exception(exc)
