from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from supabase import Client

from core.db import add_incident, get_import_normalized, update_import_status
from core.hierarchy import infer_root, resolve_parent_map, split_path
from core.normalization import normalize_municipality, normalize_name

SINALOA_MUNICIPALITIES = {
    "AHOME", "ANGOSTURA", "BADIRAGUATO", "CHOIX", "CONCORDIA", "COSALA", "CULIACAN", "ELOTA",
    "ESCUINAPA", "EL FUERTE", "GUASAVE", "MAZATLAN", "MOCORITO", "NAVOLATO", "ROSARIO",
    "SALVADOR ALVARADO", "SAN IGNACIO", "SINALOA", "ELDORADO", "JUAN JOSE RIOS",
}


def _one(client: Client, table: str, **filters: Any) -> Optional[Dict[str, Any]]:
    query = client.table(table).select("*")
    for key, value in filters.items():
        query = query.eq(key, value)
    rows = query.limit(1).execute().data or []
    return rows[0] if rows else None


def _get_role_id(client: Client, code: str) -> int:
    row = _one(client, "roles_estructura", codigo=code)
    if not row:
        raise RuntimeError(f"No existe el rol {code}. Ejecute el esquema SQL actualizado.")
    return int(row["id"])


def _get_or_create_person(client: Client, name: str, phone: Optional[str] = None, validation: str = "VALIDADO") -> Dict[str, Any]:
    normalized = normalize_name(name)
    if not normalized:
        raise ValueError("Nombre vacío")

    existing = _one(client, "personas", nombre_normalizado=normalized)
    if existing:
        changes: Dict[str, Any] = {}
        if phone and not existing.get("telefono"):
            changes["telefono"] = phone
        if validation == "REVISAR" and existing.get("estado_validacion") == "VALIDADO":
            changes["estado_validacion"] = "REVISAR"
        if changes:
            response = client.table("personas").update(changes).eq("id", existing["id"]).execute()
            return response.data[0]
        return existing

    payload = {
        "nombre_completo": name.strip(),
        "nombre_normalizado": normalized,
        "telefono": phone,
        "estado_validacion": validation,
    }
    return client.table("personas").insert(payload).execute().data[0]


def _get_or_create_structure(client: Client, name: str, root_person_id: str) -> Dict[str, Any]:
    rows = client.table("estructuras").select("*").ilike("nombre", name).limit(1).execute().data or []
    existing = rows[0] if rows else None
    if existing:
        if not existing.get("persona_raiz_id"):
            return client.table("estructuras").update({"persona_raiz_id": root_person_id}).eq("id", existing["id"]).execute().data[0]
        return existing
    return client.table("estructuras").insert({
        "nombre": name,
        "persona_raiz_id": root_person_id,
        "descripcion": "Estructura importada desde Excel",
    }).execute().data[0]


def _get_municipality(client: Client, normalized_name: str) -> Optional[Dict[str, Any]]:
    return _one(client, "municipios", nombre_normalizado=normalized_name)


def _get_or_create_section(client: Client, number: int, municipality_id: int, allow_provisional: bool, import_id: str) -> Optional[Dict[str, Any]]:
    existing = _one(client, "secciones_electorales", entidad=25, numero=number)
    if existing:
        if existing.get("municipio_id") and int(existing["municipio_id"]) != int(municipality_id):
            add_incident(client, import_id, "ERROR", "SECCION_MUNICIPIO_CONFLICTO", f"La sección {number} ya existe asociada a otro municipio.", field_name="seccion", original_value=str(number))
            return None
        if not existing.get("municipio_id"):
            existing = client.table("secciones_electorales").update({"municipio_id": municipality_id}).eq("id", existing["id"]).execute().data[0]
        return existing
    if not allow_provisional:
        return None
    return client.table("secciones_electorales").insert({
        "entidad": 25,
        "numero": number,
        "municipio_id": municipality_id,
        "fuente_catalogo": "IMPORTACION_EXCEL",
        "estado_catalogo": "PROVISIONAL",
        "vigencia": "PENDIENTE_VALIDACION_OFICIAL",
    }).execute().data[0]


def _ensure_membership(client: Client, structure_id: str, person_id: str, parent_id: Optional[str], import_id: str, row_number: Optional[int] = None) -> None:
    existing = _one(client, "estructura_miembros", estructura_id=structure_id, persona_id=person_id, activo=True)
    if existing:
        if existing.get("superior_directo_id") != parent_id and parent_id:
            client.table("estructura_miembros").update({"superior_directo_id": parent_id, "updated_at": datetime.now(timezone.utc).isoformat()}).eq("id", existing["id"]).execute()
        return
    client.table("estructura_miembros").insert({
        "estructura_id": structure_id,
        "persona_id": person_id,
        "superior_directo_id": parent_id,
        "source_import_id": import_id,
        "source_row_number": row_number,
    }).execute()


def _ensure_role(client: Client, structure_id: str, person_id: str, role_id: int, import_id: str) -> None:
    existing = client.table("persona_roles_estructura").select("id").eq("estructura_id", structure_id).eq("persona_id", person_id).eq("rol_id", role_id).eq("activo", True).limit(1).execute().data or []
    if existing:
        return
    client.table("persona_roles_estructura").insert({
        "estructura_id": structure_id,
        "persona_id": person_id,
        "rol_id": role_id,
        "source_import_id": import_id,
    }).execute()


def _ensure_section_link(client: Client, person_id: str, section_id: int, import_id: str, row_number: int) -> None:
    existing = client.table("persona_secciones").select("id").eq("persona_id", person_id).eq("seccion_id", section_id).eq("tipo_vinculo", "REGISTRO_TERRITORIAL").eq("activo", True).limit(1).execute().data or []
    if existing:
        return
    client.table("persona_secciones").insert({
        "persona_id": person_id,
        "seccion_id": section_id,
        "tipo_vinculo": "REGISTRO_TERRITORIAL",
        "es_principal": True,
        "source_import_id": import_id,
        "source_row_number": row_number,
    }).execute()


def _ensure_address(client: Client, person_id: str, record: Dict[str, Any], municipality_id: Optional[int], import_id: str, row_number: int) -> None:
    address_fields = ["calle", "numero_exterior", "numero_interior", "colonia", "localidad", "codigo_postal", "referencias"]
    if not any(record.get(k) for k in address_fields):
        return
    existing = client.table("persona_domicilios").select("id").eq("source_import_id", import_id).eq("source_row_number", row_number).limit(1).execute().data or []
    if existing:
        return
    client.table("persona_domicilios").insert({
        "persona_id": person_id,
        "calle": record.get("calle"),
        "numero_exterior": record.get("numero_exterior"),
        "numero_interior": record.get("numero_interior"),
        "colonia": record.get("colonia"),
        "codigo_postal": record.get("codigo_postal"),
        "localidad": record.get("localidad"),
        "municipio_id": municipality_id,
        "estado": "SINALOA",
        "referencias": record.get("referencias"),
        "source_import_id": import_id,
        "source_row_number": row_number,
    }).execute()


def confirm_import(client: Client, import_id: str, structure_name: Optional[str] = None, allow_provisional_sections: bool = True) -> Dict[str, Any]:
    records = get_import_normalized(client, import_id)
    if not records:
        raise RuntimeError("La importación no tiene registros normalizados en staging.")

    update_import_status(client, import_id, "CONFIRMING")
    root_name = infer_root(records)
    if not root_name:
        update_import_status(client, import_id, "FAILED")
        raise RuntimeError("No fue posible inferir la raíz de la estructura desde GRUPO 1.")

    parent_map, hierarchy_conflicts = resolve_parent_map(records)
    for conflict in hierarchy_conflicts:
        add_incident(client, import_id, "ADVERTENCIA", "JERARQUIA_AMBIGUA", f"{conflict['persona']}: {conflict['alternativas']}. Se eligió: {conflict['superior_elegido'] or 'sin superior'}.")

    person_cache: Dict[str, Dict[str, Any]] = {}
    terminal_by_name: Dict[str, Dict[str, Any]] = {}
    for record in records:
        name = record.get("promovido_normalizado")
        if name:
            terminal_by_name.setdefault(name, record)

    # Crear todos los nodos de la red, coordinadores y promovidos.
    all_names = set(parent_map)
    all_names.add(root_name)
    for name in sorted(all_names):
        terminal = terminal_by_name.get(name)
        validation = "REVISAR" if terminal and terminal.get("estado_validacion") == "REVISAR" else "VALIDADO"
        phone = terminal.get("telefono") if terminal else None
        person_cache[name] = _get_or_create_person(client, name, phone=phone, validation=validation)

    root_person = person_cache[root_name]
    structure = _get_or_create_structure(client, structure_name or f"Estructura {root_name.title()}", root_person["id"])
    structure_id = structure["id"]
    coordinator_role = _get_role_id(client, "COORDINADOR")
    promoted_role = _get_role_id(client, "PROMOVIDO")

    # Membresías y roles jerárquicos.
    for name, parent_name in parent_map.items():
        person = person_cache[name]
        parent = person_cache.get(parent_name) if parent_name else None
        _ensure_membership(client, structure_id, person["id"], parent["id"] if parent else None, import_id)
        if name == root_name or any(name in split_path(r.get("ruta_jerarquica")) for r in records):
            _ensure_role(client, structure_id, person["id"], coordinator_role, import_id)

    summary = defaultdict(int)
    summary["registros_staging"] = len(records)
    summary["conflictos_jerarquia"] = len(hierarchy_conflicts)

    for record in records:
        name = record.get("promovido_normalizado")
        if not name:
            summary["omitidos"] += 1
            continue
        person = person_cache[name]
        _ensure_role(client, structure_id, person["id"], promoted_role, import_id)
        summary["promovidos_procesados"] += 1

        municipality_name = normalize_municipality(record.get("municipio"))
        municipality = _get_municipality(client, municipality_name) if municipality_name else None
        if not municipality:
            client.table("personas").update({"estado_validacion": "REVISAR"}).eq("id", person["id"]).execute()
            add_incident(client, import_id, "ERROR", "MUNICIPIO_NO_CATALOGADO", f"Municipio no encontrado en el catálogo de Sinaloa: {record.get('municipio')}", row_number=record.get("fila_excel"), field_name="municipio", original_value=str(record.get("municipio")))
            summary["sin_municipio_valido"] += 1
            continue

        section_number = record.get("seccion")
        section = _get_or_create_section(client, int(section_number), int(municipality["id"]), allow_provisional_sections, import_id) if section_number else None
        if not section:
            client.table("personas").update({"estado_validacion": "REVISAR"}).eq("id", person["id"]).execute()
            add_incident(client, import_id, "ERROR", "SECCION_NO_CATALOGADA", f"Sección {section_number} no disponible para vincular.", row_number=record.get("fila_excel"), field_name="seccion", original_value=str(section_number))
            summary["sin_seccion_valida"] += 1
        else:
            _ensure_section_link(client, person["id"], int(section["id"]), import_id, int(record["fila_excel"]))
            summary["vinculos_seccion"] += 1

        _ensure_address(client, person["id"], record, int(municipality["id"]), import_id, int(record["fila_excel"]))

    update_import_status(client, import_id, "CONFIRMED", {
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
        "structure_name": structure["nombre"],
    })
    summary["estructura_id"] = structure_id
    summary["estructura_nombre"] = structure["nombre"]
    summary["personas_red"] = len(person_cache)
    return dict(summary)
