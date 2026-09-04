from __future__ import annotations

import streamlit as st

from core.db import fetch_all
from core.local_store import get_local_people, get_local_sections, local_add_person
from core.manual_ops import create_person, ensure_membership, ensure_role, ensure_section_link, save_address, update_person
from core.runtime import active_mode, optional_client
from core.ui import page_header

page_header("Captura y edición", "Alta manual y corrección de registros")
mode = active_mode()
if mode == "LOCAL":
    st.caption("🟢 Captura temporal. Los cambios duran mientras permanezca activa la sesión.")
    people = get_local_people(); sections = get_local_sections()
    name = st.text_input("Nombre completo")
    phone = st.text_input("Celular")
    role = st.selectbox("Rol en estructura", ["PROMOVIDO"], help="En modo temporal, coordinadores se derivan de la jerarquía de los Excel. Las responsabilidades formales se asignan en Casillas y responsables.")
    parent_options = ["SIN SUPERIOR"] + sorted(people["nombre_completo"].dropna().tolist()) if not people.empty else ["SIN SUPERIOR"]
    parent = st.selectbox("Superior directo", parent_options)
    municipality_options = ["SIN DEFINIR"] + sorted(sections["municipio"].dropna().unique().tolist()) if not sections.empty else ["SIN DEFINIR"]
    municipality = st.selectbox("Municipio", municipality_options)
    section_options = ["SIN SECCION"]
    if not sections.empty:
        temp = sections if municipality == "SIN DEFINIR" else sections[sections["municipio"] == municipality]
        section_options += [str(x) for x in sorted(temp["numero"].dropna().unique().tolist(), key=lambda x: int(x) if str(x).isdigit() else str(x))]
    section = st.selectbox("Sección", section_options)
    if st.button("Agregar a la base temporal", type="primary"):
        try:
            local_add_person(name, phone, None if parent == "SIN SUPERIOR" else parent, role, None if section == "SIN SECCION" else section, None if municipality == "SIN DEFINIR" else municipality)
            st.success("Persona agregada a la sesión temporal."); st.rerun()
        except Exception as exc: st.error(str(exc))
    st.stop()

if mode != "SUPABASE": st.info("Carga un Excel para usar captura temporal o conecta Supabase para persistencia."); st.stop()
client = optional_client()
if client is None: st.warning("No se pudo conectar a Supabase."); st.stop()
people = fetch_all(client, "personas", select="id,nombre_completo,telefono,estado_validacion", filters={"activo": True}, order="nombre_completo")
structures = fetch_all(client, "estructuras", select="id,nombre", filters={"activo": True}, order="nombre")
roles = fetch_all(client, "roles_estructura", select="id,codigo,nombre", filters={"activo": True}, order="nombre")
sections = fetch_all(client, "vw_secciones_resumen", select="seccion_id,numero,municipio,distrito_local", order="numero")
municipalities = fetch_all(client, "municipios", select="id,nombre,nombre_normalizado", filters={"activo": True}, order="nombre")
new_tab, edit_tab = st.tabs(["Nueva persona", "Editar persona"])
with new_tab:
    name = st.text_input("Nombre completo", key="new_name"); phone = st.text_input("Celular", key="new_phone")
    structure_label = st.selectbox("Estructura", ["SIN ASIGNAR"] + [x["nombre"] for x in structures], key="new_structure"); structure = next((x for x in structures if x["nombre"] == structure_label), None)
    parent_options = ["SIN SUPERIOR"] + [p["nombre_completo"] for p in people]; parent_label = st.selectbox("Superior directo", parent_options, key="new_parent"); parent = next((p for p in people if p["nombre_completo"] == parent_label), None)
    role_label = st.selectbox("Rol en estructura", [r["nombre"] for r in roles], key="new_role") if roles else None; role = next((r for r in roles if r["nombre"] == role_label), None)
    section_labels = ["SIN SECCIÓN"] + [f"{s['numero']} · {s.get('municipio') or 'Sin municipio'}" for s in sections]; section_label = st.selectbox("Sección", section_labels, key="new_section"); section = next((s for s in sections if section_label.startswith(f"{s['numero']} ·")), None)
    with st.expander("Domicilio opcional"):
        muni_label = st.selectbox("Municipio del domicilio", ["SIN DEFINIR"] + [m["nombre"] for m in municipalities], key="new_address_muni"); address_muni = next((m for m in municipalities if m["nombre"] == muni_label), None)
        street = st.text_input("Calle", key="new_street"); exterior = st.text_input("Número exterior", key="new_ext"); neighborhood = st.text_input("Colonia", key="new_colonia"); locality = st.text_input("Localidad", key="new_locality"); postal = st.text_input("Código postal", key="new_cp"); refs = st.text_area("Referencias", key="new_refs")
    if st.button("Guardar persona", type="primary", key="create_person"):
        try:
            created = create_person(client, name, phone, "VALIDADO")
            if structure:
                ensure_membership(client, structure["id"], created["id"], parent["id"] if parent else None)
                if role: ensure_role(client, structure["id"], created["id"], int(role["id"]))
            if section: ensure_section_link(client, created["id"], int(section["seccion_id"]))
            save_address(client, created["id"], int(address_muni["id"]) if address_muni else None, street, exterior, neighborhood, locality, postal, refs)
            st.success("Persona registrada."); st.rerun()
        except Exception as exc: st.error(str(exc))
with edit_tab:
    if not people: st.info("No hay personas para editar.")
    else:
        selected_label = st.selectbox("Persona", [p["nombre_completo"] for p in people], key="edit_person"); selected = next(p for p in people if p["nombre_completo"] == selected_label)
        edit_name = st.text_input("Nombre", value=selected["nombre_completo"], key="edit_name"); edit_phone = st.text_input("Celular", value=selected.get("telefono") or "", key="edit_phone")
        validation = st.selectbox("Estado de validación", ["VALIDADO", "REVISAR"], index=0 if selected.get("estado_validacion") == "VALIDADO" else 1)
        structure_label = st.selectbox("Estructura", ["NO CAMBIAR"] + [x["nombre"] for x in structures], key="edit_structure"); structure = next((x for x in structures if x["nombre"] == structure_label), None)
        parent_label = st.selectbox("Nuevo superior directo", ["SIN SUPERIOR"] + [p["nombre_completo"] for p in people if p["id"] != selected["id"]], key="edit_parent"); parent = next((p for p in people if p["nombre_completo"] == parent_label), None)
        role_label = st.selectbox("Agregar/asegurar rol", [r["nombre"] for r in roles], key="edit_role") if roles else None; role = next((r for r in roles if r["nombre"] == role_label), None)
        section_labels = ["NO CAMBIAR"] + [f"{s['numero']} · {s.get('municipio') or 'Sin municipio'}" for s in sections]; section_label = st.selectbox("Agregar sección", section_labels, key="edit_section"); section = next((s for s in sections if section_label.startswith(f"{s['numero']} ·")), None)
        if st.button("Guardar cambios", type="primary", key="save_edit"):
            try:
                update_person(client, selected["id"], edit_name, edit_phone, validation)
                if structure:
                    ensure_membership(client, structure["id"], selected["id"], parent["id"] if parent else None)
                    if role: ensure_role(client, structure["id"], selected["id"], int(role["id"]))
                if section: ensure_section_link(client, selected["id"], int(section["seccion_id"]))
                st.success("Cambios guardados."); st.rerun()
            except Exception as exc: st.error(str(exc))
