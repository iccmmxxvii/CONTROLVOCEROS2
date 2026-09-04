from __future__ import annotations

import gzip
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data" / "cartografia"
CATALOG_PATH = DATA_DIR / "secciones_catalogo.csv"
GEOJSON_GZ_PATH = DATA_DIR / "secciones_sinaloa.geojson.gz"
SOURCE_META_PATH = DATA_DIR / "fuente_cartografia.json"


@lru_cache(maxsize=1)
def load_section_catalog() -> pd.DataFrame:
    if not CATALOG_PATH.exists():
        return pd.DataFrame()
    df = pd.read_csv(CATALOG_PATH)
    if "seccion" in df:
        df["seccion"] = pd.to_numeric(df["seccion"], errors="coerce").astype("Int64")
    for col in ("distrito_local", "distrito_federal", "municipio_clave", "tipo_codigo"):
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    return df


@lru_cache(maxsize=1)
def section_lookup() -> Dict[int, Dict[str, Any]]:
    df = load_section_catalog()
    if df.empty:
        return {}
    out: Dict[int, Dict[str, Any]] = {}
    for _, row in df.iterrows():
        if pd.isna(row.get("seccion")):
            continue
        sec = int(row["seccion"])
        out[sec] = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
    return out


@lru_cache(maxsize=1)
def load_base_geojson() -> Dict[str, Any]:
    if not GEOJSON_GZ_PATH.exists():
        return {"type": "FeatureCollection", "features": []}
    with gzip.open(GEOJSON_GZ_PATH, "rt", encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def source_metadata() -> Dict[str, Any]:
    if not SOURCE_META_PATH.exists():
        return {}
    try:
        return json.loads(SOURCE_META_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _norm_text(value: Any) -> Optional[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip().upper()
    return text or None


def enrich_normalized_with_cartography(normalized: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Enriquece registros usando SECCION como llave maestra y conserva trazabilidad.

    Nunca inventa datos. Si la sección no existe en el catálogo, conserva lo capturado y
    genera una incidencia. Si el municipio capturado contradice la cartografía, el valor
    efectivo será el cartográfico y el capturado queda preservado en municipio_excel.
    """
    if normalized.empty:
        return normalized.copy(), pd.DataFrame()

    lookup = section_lookup()
    out = normalized.copy()
    incidents: List[Dict[str, Any]] = []

    # Preservar dato capturado antes de derivar.
    if "municipio_excel" not in out.columns:
        out["municipio_excel"] = out.get("municipio")

    derived_cols = [
        "municipio_cartografia", "municipio_origen", "distrito_local",
        "distrito_federal", "tipo_seccion", "centroide_lat", "centroide_lon",
        "estado_catalogo", "fuente_territorial"
    ]
    for col in derived_cols:
        if col not in out.columns:
            out[col] = None

    for idx, row in out.iterrows():
        sec_raw = row.get("seccion")
        try:
            sec = int(float(sec_raw)) if sec_raw is not None and str(sec_raw).strip() else None
        except Exception:
            sec = None
        excel_muni = _norm_text(row.get("municipio_excel"))
        meta = lookup.get(sec) if sec is not None else None

        if not meta:
            out.at[idx, "municipio"] = excel_muni
            out.at[idx, "municipio_origen"] = "EXCEL" if excel_muni else "NO_DISPONIBLE"
            out.at[idx, "estado_catalogo"] = "NO_LOCALIZADA"
            out.at[idx, "fuente_territorial"] = "SIN_CORRESPONDENCIA_CARTOGRAFICA"
            incidents.append({
                "fila_excel": row.get("fila_excel"),
                "severidad": "ADVERTENCIA",
                "tipo": "SECCION_NO_CARTOGRAFIA",
                "campo": "seccion",
                "valor": sec_raw,
                "mensaje": "La sección no se localizó en la cartografía precargada; no se derivaron municipio/distritos.",
                "archivo_origen": row.get("archivo_origen"),
                "estructura_origen": row.get("estructura_origen"),
                "fecha_importacion": row.get("fecha_importacion"),
                "importacion_id": row.get("importacion_id"),
            })
            continue

        cart_muni = _norm_text(meta.get("municipio"))
        out.at[idx, "municipio_cartografia"] = cart_muni
        out.at[idx, "municipio"] = cart_muni
        out.at[idx, "municipio_origen"] = "CARTOGRAFIA_SECCION"
        out.at[idx, "distrito_local"] = meta.get("distrito_local")
        out.at[idx, "distrito_federal"] = meta.get("distrito_federal")
        out.at[idx, "tipo_seccion"] = meta.get("tipo_seccion")
        out.at[idx, "centroide_lat"] = meta.get("centroide_lat")
        out.at[idx, "centroide_lon"] = meta.get("centroide_lon")
        out.at[idx, "estado_catalogo"] = "CARTOGRAFIA_PRECARGADA"
        out.at[idx, "fuente_territorial"] = "SECCION→CARTOGRAFIA_SINALOA"

        if excel_muni and cart_muni and excel_muni != cart_muni:
            if str(out.at[idx, "estado_validacion"]) != "BLOQUEADO":
                out.at[idx, "estado_validacion"] = "REVISAR"
            incidents.append({
                "fila_excel": row.get("fila_excel"),
                "severidad": "ADVERTENCIA",
                "tipo": "MUNICIPIO_CONFLICTO_CARTOGRAFIA",
                "campo": "municipio",
                "valor": excel_muni,
                "mensaje": f"El Excel indica {excel_muni}, pero la sección {sec} corresponde a {cart_muni} en la cartografía precargada.",
                "archivo_origen": row.get("archivo_origen"),
                "estructura_origen": row.get("estructura_origen"),
                "fecha_importacion": row.get("fecha_importacion"),
                "importacion_id": row.get("importacion_id"),
            })

    return out, pd.DataFrame(incidents)


def master_sections_dataframe() -> pd.DataFrame:
    df = load_section_catalog().copy()
    if df.empty:
        return df
    return df.rename(columns={"seccion": "numero"})




def _geojson_safe_value(value: Any):
    """Convierte valores de DataFrame en propiedades GeoJSON seguras.

    Evita evaluar ``pd.isna`` sobre listas/diccionarios, que devuelve arreglos
    booleanos y puede provocar ``ValueError: truth value is ambiguous``.
    """
    if value is None:
        return None
    if isinstance(value, dict):
        return {str(k): _geojson_safe_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_geojson_safe_value(v) for v in value]
    try:
        missing = pd.isna(value)
        if isinstance(missing, bool) and missing:
            return None
    except Exception:
        pass
    # Convertir escalares numpy/pandas cuando sea posible.
    try:
        return value.item()
    except Exception:
        return value


def build_geojson_with_metrics(
    metrics: Optional[pd.DataFrame] = None,
    section_numbers: Optional[Iterable[Any]] = None,
) -> Dict[str, Any]:
    """Devuelve GeoJSON completo o filtrado, agregando métricas operativas por sección."""
    base = load_base_geojson()
    allowed = None
    if section_numbers is not None:
        allowed = {str(int(float(x))) for x in section_numbers if x is not None and str(x).strip()}

    metric_map: Dict[str, Dict[str, Any]] = {}
    if isinstance(metrics, pd.DataFrame) and not metrics.empty and "numero" in metrics.columns:
        for _, row in metrics.iterrows():
            try:
                key = str(int(float(row.get("numero"))))
            except Exception:
                continue
            metric_map[key] = {k: _geojson_safe_value(v) for k, v in row.to_dict().items()}

    features = []
    for feat in base.get("features", []):
        props = dict(feat.get("properties") or {})
        key = str(props.get("seccion"))
        if allowed is not None and key not in allowed:
            continue
        op = metric_map.get(key, {})
        # Preservar atributos operativos derivados de la tabla de métricas para
        # que páginas como el mapa puedan enriquecer el tooltip con desgloses.
        props.update({k: _geojson_safe_value(v) for k, v in op.items()})
        props.update({
            "promovidos": int(op.get("promovidos") or 0),
            "coordinadores": int(op.get("coordinadores") or 0),
            "casillas_catalogadas": int(op.get("casillas_catalogadas") or 0),
            "casillas_con_promovidos": int(op.get("casillas_con_promovidos") or 0),
            "promovidos_sin_casilla": int(op.get("promovidos_sin_casilla") or 0),
            "coordinador_mayor_estructura": op.get("coordinador_mayor_estructura") or "SIN REGISTROS",
            "responsable_formal": op.get("responsable_formal") or "SIN ASIGNAR",
            "presencia": "CON REGISTROS" if int(op.get("promovidos") or 0) > 0 else "SIN REGISTROS",
        })
        features.append({"type": "Feature", "properties": props, "geometry": feat.get("geometry")})
    return {"type": "FeatureCollection", "features": features}
