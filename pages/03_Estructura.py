from __future__ import annotations

import pandas as pd
import streamlit as st

from core.db import fetch_all
from core.local_store import get_local_payload, get_local_tree
from core.queries import tree_dataframe
from core.runtime import active_mode, optional_client
from core.ui import page_header


def _descendants(df: pd.DataFrame, person_id) -> pd.DataFrame:
    if df.empty or person_id is None or "superior_directo_id" not in df.columns:
        return pd.DataFrame()
    found_ids = set()
    frontier = {person_id}
    while frontier:
        children = df[df["superior_directo_id"].isin(frontier)]
        new_ids = set(children["persona_id"].dropna()) - found_ids
        if not new_ids:
            break
        found_ids.update(new_ids)
        frontier = new_ids
    return df[df["persona_id"].isin(found_ids)].copy()


def _render_dependency(df: pd.DataFrame, person: str):
    rows = df[df["nombre_completo"] == person].sort_values("nivel")
    if rows.empty:
        return
    row = rows.iloc[0]
    route_names = row.get("ruta_nombres") or []
    if isinstance(route_names, str):
        route_names = [x.strip() for x in route_names.split("→") if x.strip()]
    if not route_names:
        chain = [person]
        parent = row.get("superior_directo_nombre")
        guard = set(chain)
        while parent and parent not in guard:
            chain.append(parent)
            guard.add(parent)
            parent_rows = df[df["nombre_completo"] == parent]
            parent = None if parent_rows.empty else parent_rows.iloc[0].get("superior_directo_nombre")
        route_names = list(reversed(chain))

    person_id = row.get("persona_id")
    direct = df[df["superior_directo_id"] == person_id].copy() if "superior_directo_id" in df.columns else pd.DataFrame()
    total = _descendants(df, person_id)

    st.markdown(f"### {person}")
    a, b, c, d = st.columns(4)
    a.metric("Nivel relativo", int(row.get("nivel") or 0))
    b.metric("Dependientes directos", len(direct))
    c.metric("Red descendente", len(total))
    d.metric("Rol", str(row.get("roles") or "INTEGRANTE"))

    with st.container(border=True):
        st.markdown("**Superior directo**")
        st.write(row.get("superior_directo_nombre") or "Raíz / sin superior")
        st.markdown("**Cadena de dependencia**")
        st.write(" → ".join(route_names))

    if not direct.empty:
        st.markdown("#### Dependientes directos")
        cols = [c for c in ["nombre_completo", "nivel", "roles", "secciones"] if c in direct.columns]
        st.dataframe(direct[cols], use_container_width=True, hide_index=True, height=min(320, 45 + 35 * len(direct)))


page_header("Estructura", "Dependencia jerárquica calculada: busca una persona y la plataforma traza su cadena automáticamente")
mode = active_mode()
if mode == "LOCAL":
    payload = get_local_payload()
    df = get_local_tree()
    st.caption(f"🟢 Base temporal · {payload.get('structure_name') or 'Estructura temporal'}")
elif mode == "SUPABASE":
    client = optional_client()
    if client is None:
        st.warning("No se pudo conectar a Supabase.")
        st.stop()
    structures = fetch_all(client, "estructuras", select="id,nombre,persona_raiz_id", filters={"activo": True}, order="nombre")
    if not structures:
        st.info("Aún no existe ninguna estructura confirmada.")
        st.stop()
    labels = {x["nombre"]: x["id"] for x in structures}
    selected_name = st.selectbox("Estructura", list(labels))
    df = tree_dataframe(client, labels[selected_name])
else:
    st.info("Carga un Excel o activa la base demo para visualizar la red.")
    st.stop()

if df.empty:
    st.warning("No hay miembros navegables.")
    st.stop()

# En bases consolidadas permite acotar una estructura sin obligar al usuario.
view = df.copy()
if "estructura_nombre" in view.columns:
    structures = sorted(view["estructura_nombre"].dropna().astype(str).unique().tolist())
    if len(structures) > 1:
        selected_structure = st.selectbox("Estructura a consultar", ["TODAS"] + structures)
        if selected_structure != "TODAS":
            view = view[view["estructura_nombre"] == selected_structure].copy()

search = st.text_input("Buscar persona dentro de la estructura", placeholder="Escribe nombre o parte del nombre")
matched = view[view["nombre_completo"].fillna("").str.contains(search, case=False, regex=False)] if search else view
unique_matches = sorted(matched["nombre_completo"].dropna().astype(str).unique().tolist())

c1, c2, c3 = st.columns(3)
c1.metric("Miembros", view["persona_id"].nunique())
c2.metric("Profundidad máxima", int(view["nivel"].max()) if "nivel" in view and not view.empty else 0)
c3.metric("Resultados", len(unique_matches) if search else len(view))

show_cols = [c for c in ["nivel", "nombre_completo", "superior_directo_nombre", "roles", "estructura_nombre"] if c in matched.columns]
st.dataframe(matched[show_cols], use_container_width=True, hide_index=True, height=min(360, 45 + 34 * max(1, min(len(matched), 9))))

selected_person = None
if search and len(unique_matches) == 1:
    selected_person = unique_matches[0]
    st.success(f"Selección automática: {selected_person}")
elif search and len(unique_matches) > 1:
    selected_person = st.selectbox("Selecciona uno de los resultados", unique_matches, key="estructura_resultado")
elif search and not unique_matches:
    st.warning("No se encontraron coincidencias.")

# El selector manual queda solo como respaldo.
with st.expander("Selección manual (respaldo)", expanded=False):
    options = sorted(view["nombre_completo"].dropna().astype(str).unique().tolist())
    manual = st.selectbox("Persona", ["Seleccionar..."] + options, key="estructura_manual")
    if not selected_person and manual != "Seleccionar...":
        selected_person = manual

st.divider()
st.subheader("Trazar dependencia")
if selected_person:
    _render_dependency(view, selected_person)
else:
    st.info("Busca una persona arriba. Si hay una sola coincidencia, su dependencia se trazará automáticamente.")
