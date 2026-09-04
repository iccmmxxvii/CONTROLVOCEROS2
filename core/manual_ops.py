from __future__ import annotations

from typing import Any, Dict, Optional

from supabase import Client

from core.normalization import normalize_name


def create_person(client: Client, name: str, phone: Optional[str] = None, validation: str = "VALIDADO") -> Dict[str, Any]:
    normalized = normalize_name(name)
    if not normalized:
        raise ValueError("El nombre es obligatorio.")
    existing = client.table("personas").select("*").eq("nombre_normalizado", normalized).limit(1).execute().data or []
    if existing:
        raise ValueError("Ya existe una persona con el mismo nombre normalizado. Revísala antes de crear otra.")
    return client.table("personas").insert({
        "nombre_completo": name.strip(),
        "nombre_normalizado": normalized,
        "telefono": phone or None,
        "estado_validacion": validation,
    }).execute().data[0]


def update_person(client: Client, person_id: str, name: str, phone: Optional[str], validation: str) -> Dict[str, Any]:
    normalized = normalize_name(name)
    if not normalized:
        raise ValueError("El nombre es obligatorio.")
    return client.table("personas").update({
        "nombre_completo": name.strip(),
        "nombre_normalizado": normalized,
        "telefono": phone or None,
        "estado_validacion": validation,
    }).eq("id", person_id).execute().data[0]


def ensure_membership(client: Client, structure_id: str, person_id: str, parent_id: Optional[str]) -> None:
    if parent_id == person_id:
        raise ValueError("Una persona no puede depender de sí misma.")
    existing = client.table("estructura_miembros").select("id").eq("estructura_id", structure_id).eq("persona_id", person_id).eq("activo", True).limit(1).execute().data or []
    if existing:
        client.table("estructura_miembros").update({"superior_directo_id": parent_id}).eq("id", existing[0]["id"]).execute()
    else:
        client.table("estructura_miembros").insert({
            "estructura_id": structure_id,
            "persona_id": person_id,
            "superior_directo_id": parent_id,
        }).execute()


def ensure_role(client: Client, structure_id: str, person_id: str, role_id: int) -> None:
    existing = client.table("persona_roles_estructura").select("id").eq("estructura_id", structure_id).eq("persona_id", person_id).eq("rol_id", role_id).eq("activo", True).limit(1).execute().data or []
    if not existing:
        client.table("persona_roles_estructura").insert({
            "estructura_id": structure_id,
            "persona_id": person_id,
            "rol_id": role_id,
        }).execute()


def ensure_section_link(client: Client, person_id: str, section_id: int) -> None:
    existing = client.table("persona_secciones").select("id").eq("persona_id", person_id).eq("seccion_id", section_id).eq("tipo_vinculo", "REGISTRO_TERRITORIAL").eq("activo", True).limit(1).execute().data or []
    if not existing:
        client.table("persona_secciones").insert({
            "persona_id": person_id,
            "seccion_id": section_id,
            "tipo_vinculo": "REGISTRO_TERRITORIAL",
            "es_principal": True,
        }).execute()


def save_address(client: Client, person_id: str, municipality_id: Optional[int], street: Optional[str], exterior: Optional[str], neighborhood: Optional[str], locality: Optional[str], postal_code: Optional[str], references: Optional[str]) -> None:
    if not any([street, exterior, neighborhood, locality, postal_code, references]):
        return
    existing = client.table("persona_domicilios").select("id").eq("persona_id", person_id).eq("es_principal", True).eq("activo", True).limit(1).execute().data or []
    payload = {
        "calle": street or None,
        "numero_exterior": exterior or None,
        "colonia": neighborhood or None,
        "localidad": locality or None,
        "codigo_postal": postal_code or None,
        "referencias": references or None,
        "municipio_id": municipality_id,
        "estado": "SINALOA",
    }
    if existing:
        client.table("persona_domicilios").update(payload).eq("id", existing[0]["id"]).execute()
    else:
        client.table("persona_domicilios").insert({"persona_id": person_id, **payload, "es_principal": True}).execute()
