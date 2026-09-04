from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
from supabase import Client

from core.db import fetch_all


def dashboard_metrics(client: Client) -> Dict[str, int]:
    people = fetch_all(client, "personas", select="id,estado_validacion", filters={"activo": True})
    sections = fetch_all(client, "secciones_electorales", select="id,estado_catalogo", filters={"activo": True})
    links = fetch_all(client, "persona_secciones", select="id,seccion_id", filters={"activo": True})
    imports = fetch_all(client, "importaciones_excel", select="id,status")
    unique_sections = len({r["seccion_id"] for r in links})
    return {
        "personas": len(people),
        "personas_revisar": sum(1 for p in people if p.get("estado_validacion") == "REVISAR"),
        "secciones_catalogo": len(sections),
        "secciones_con_registros": unique_sections,
        "secciones_provisionales": sum(1 for s in sections if s.get("estado_catalogo") == "PROVISIONAL"),
        "importaciones": len(imports),
        "importaciones_confirmadas": sum(1 for x in imports if x.get("status") == "CONFIRMED"),
    }


def people_dataframe(client: Client) -> pd.DataFrame:
    rows = fetch_all(client, "vw_personas_detalle")
    return pd.DataFrame(rows)


def tree_dataframe(client: Client, structure_id: Optional[str] = None) -> pd.DataFrame:
    filters = {"estructura_id": structure_id} if structure_id else None
    rows = fetch_all(client, "vw_estructura_arbol", filters=filters, order="nivel")
    return pd.DataFrame(rows)


def sections_dataframe(client: Client) -> pd.DataFrame:
    return pd.DataFrame(fetch_all(client, "vw_secciones_resumen", order="numero"))


def imports_dataframe(client: Client) -> pd.DataFrame:
    return pd.DataFrame(fetch_all(client, "importaciones_excel", order="created_at", ascending=False))


def incidents_dataframe(client: Client, import_id: str) -> pd.DataFrame:
    return pd.DataFrame(fetch_all(client, "importacion_incidencias", filters={"import_id": import_id}, order="row_number"))


def booths_dataframe(client: Client) -> pd.DataFrame:
    return pd.DataFrame(fetch_all(client, "vw_casillas_resumen", order="seccion"))


def responsibilities_dataframe(client: Client) -> pd.DataFrame:
    return pd.DataFrame(fetch_all(client, "responsabilidades_territoriales", filters={"activo": True}))
