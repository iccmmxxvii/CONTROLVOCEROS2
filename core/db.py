from __future__ import annotations

import hashlib
from typing import Any, Dict, Iterable, List, Optional

from supabase import Client, create_client


class DatabaseNotConfigured(RuntimeError):
    pass


def get_client(url: Optional[str], key: Optional[str]) -> Client:
    if not url or not key:
        raise DatabaseNotConfigured("Supabase no está configurado.")
    return create_client(url, key)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_all(client: Client, table: str, select: str = "*", filters: Optional[Dict[str, Any]] = None, order: Optional[str] = None, ascending: bool = True, page_size: int = 1000) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    start = 0
    while True:
        query = client.table(table).select(select)
        for key, value in (filters or {}).items():
            query = query.eq(key, value)
        if order:
            query = query.order(order, desc=not ascending)
        response = query.range(start, start + page_size - 1).execute()
        batch = response.data or []
        result.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size
    return result


def find_import_by_hash(client: Client, file_hash: str) -> List[Dict[str, Any]]:
    return client.table("importaciones_excel").select("id,filename,status,created_at,confirmed_at").eq("file_sha256", file_hash).order("created_at", desc=True).execute().data or []


def create_import(client: Client, filename: str, data: bytes, sheet_name: str, total_rows: int, structure_name: Optional[str] = None) -> str:
    payload = {
        "filename": filename,
        "file_sha256": sha256_bytes(data),
        "sheet_name": sheet_name,
        "total_rows": total_rows,
        "status": "STAGING",
        "source_type": "EXCEL",
        "structure_name": structure_name,
    }
    response = client.table("importaciones_excel").insert(payload).execute()
    return response.data[0]["id"]


def _insert_batches(client: Client, table: str, payload: List[Dict[str, Any]], batch_size: int = 250) -> None:
    for i in range(0, len(payload), batch_size):
        client.table(table).insert(payload[i:i + batch_size]).execute()


def insert_raw_records(client: Client, import_id: str, records: Iterable[Dict[str, Any]]) -> None:
    payload = [{"import_id": import_id, **record} for record in records]
    _insert_batches(client, "importacion_registros_raw", payload)


def insert_normalized_records(client: Client, import_id: str, records: Iterable[Dict[str, Any]]) -> None:
    payload = [{"import_id": import_id, **record} for record in records]
    _insert_batches(client, "importacion_registros_normalizados", payload)


def insert_incidents(client: Client, import_id: str, incidents: List[Dict[str, Any]]) -> None:
    if not incidents:
        return
    payload = [{
        "import_id": import_id,
        "row_number": item.get("fila_excel"),
        "severity": item.get("severidad") or "INFO",
        "incident_type": item.get("tipo") or "OTRO",
        "field_name": item.get("campo"),
        "original_value": None if item.get("valor") is None else str(item.get("valor")),
        "message": item.get("mensaje") or "",
    } for item in incidents]
    _insert_batches(client, "importacion_incidencias", payload)


def add_incident(client: Client, import_id: str, severity: str, incident_type: str, message: str, row_number: Optional[int] = None, field_name: Optional[str] = None, original_value: Optional[str] = None) -> None:
    client.table("importacion_incidencias").insert({
        "import_id": import_id,
        "row_number": row_number,
        "severity": severity,
        "incident_type": incident_type,
        "field_name": field_name,
        "original_value": original_value,
        "message": message,
    }).execute()


def update_import_status(client: Client, import_id: str, status: str, extra: Optional[Dict[str, Any]] = None) -> None:
    payload = {"status": status, **(extra or {})}
    client.table("importaciones_excel").update(payload).eq("id", import_id).execute()


def get_import_normalized(client: Client, import_id: str) -> List[Dict[str, Any]]:
    rows = fetch_all(client, "importacion_registros_normalizados", filters={"import_id": import_id}, order="row_number")
    return [r["normalized_data"] for r in rows]


def get_import(client: Client, import_id: str) -> Optional[Dict[str, Any]]:
    rows = client.table("importaciones_excel").select("*").eq("id", import_id).limit(1).execute().data or []
    return rows[0] if rows else None
