from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from supabase import Client

from core.normalization import clean_text, normalize_float, normalize_int, normalize_municipality, normalize_section

ALIASES = {
    "seccion": ["SECCION", "SECCIÓN", "SECC", "SECCION ELECTORAL"],
    "municipio": ["MUNICIPIO", "NOMBRE MUNICIPIO", "MUNICIPIO_NOMBRE"],
    "distrito_local": ["DISTRITO LOCAL", "DISTRITO_LOCAL", "DIST LOCAL", "DISTRITO"],
    "distrito_federal": ["DISTRITO FEDERAL", "DISTRITO_FEDERAL", "DIST FEDERAL"],
    "tipo_seccion": ["TIPO SECCION", "TIPO_SECCION", "TIPO DE SECCION", "TIPO"],
    "latitud": ["LATITUD", "LAT", "CENTROIDE_LAT"],
    "longitud": ["LONGITUD", "LON", "LNG", "CENTROIDE_LON"],
}


def _head(x: Any) -> str:
    return (clean_text(x) or "").upper()


def detect_catalog_columns(columns) -> Dict[str, Optional[str]]:
    lookup = {_head(c): str(c) for c in columns}
    return {k: next((lookup[a] for a in aliases if a in lookup), None) for k, aliases in ALIASES.items()}


def read_catalog(data: bytes, sheet_name: Optional[str] = None) -> Tuple[pd.DataFrame, List[str]]:
    excel = pd.ExcelFile(BytesIO(data))
    selected = sheet_name or excel.sheet_names[0]
    return pd.read_excel(BytesIO(data), sheet_name=selected, dtype=object).dropna(how="all"), excel.sheet_names


def import_catalog(client: Client, df: pd.DataFrame, source_name: str, vigencia: Optional[str] = None) -> Dict[str, Any]:
    mapping = detect_catalog_columns(df.columns)
    if not mapping.get("seccion") or not mapping.get("municipio"):
        raise ValueError("El catálogo requiere al menos columnas de SECCIÓN y MUNICIPIO.")

    municipalities = client.table("municipios").select("id,nombre_normalizado").execute().data or []
    municipality_ids = {m["nombre_normalizado"]: m["id"] for m in municipalities}
    districts = client.table("distritos_locales").select("id,numero").execute().data or []
    district_ids = {int(d["numero"]): d["id"] for d in districts}
    try:
        federal_rows = client.table("distritos_federales").select("id,numero").execute().data or []
        federal_ids = {int(d["numero"]): d["id"] for d in federal_rows}
    except Exception:
        federal_ids = {}

    imported = 0
    rejected: List[Dict[str, Any]] = []
    for idx, row in df.iterrows():
        section = normalize_section(row.get(mapping["seccion"]))
        municipality = normalize_municipality(row.get(mapping["municipio"]))
        district = normalize_int(row.get(mapping["distrito_local"])) if mapping.get("distrito_local") else None
        federal = normalize_int(row.get(mapping["distrito_federal"])) if mapping.get("distrito_federal") else None
        tipo_seccion = clean_text(row.get(mapping["tipo_seccion"])) if mapping.get("tipo_seccion") else None
        lat = normalize_float(row.get(mapping["latitud"])) if mapping.get("latitud") else None
        lon = normalize_float(row.get(mapping["longitud"])) if mapping.get("longitud") else None
        if not section or not municipality or municipality not in municipality_ids:
            rejected.append({"fila": idx + 2, "seccion": section, "municipio": municipality, "motivo": "Sección o municipio inválido/no catalogado"})
            continue
        payload = {
            "entidad": 25,
            "numero": section,
            "municipio_id": municipality_ids[municipality],
            "distrito_local_id": district_ids.get(district) if district else None,
            "distrito_federal_id": federal_ids.get(federal) if federal else None,
            "tipo_seccion": tipo_seccion,
            "fuente_catalogo": source_name,
            "vigencia": vigencia,
            "estado_catalogo": "OFICIAL",
            "centroide_lat": lat,
            "centroide_lon": lon,
            "activo": True,
        }
        client.table("secciones_electorales").upsert(payload, on_conflict="entidad,numero").execute()
        imported += 1
    return {"importadas": imported, "rechazadas": len(rejected), "detalle_rechazadas": rejected, "mapeo": mapping}
