from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd

from core.historical_booths import fetch_iees_historical_2024
from core.local_store import activate_repo_dataset, has_local_data
from core.normalization import infer_surnames_from_full_name, normalize_phone

BASE_DIR = Path(__file__).resolve().parents[1]
SEED_PATH = BASE_DIR / "data" / "base" / "icc_estructura_12211.csv.gz"
CACHED_BOOTHS_PATH = BASE_DIR / "data" / "base" / "casillas_iees_2024.csv.gz"
SEED_FILENAME = "general con seccion 03 09 26  12211sec.xlsx"


def _clean_phone(value: Any) -> Optional[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return normalize_phone(text)


@lru_cache(maxsize=1)
def load_repo_seed() -> pd.DataFrame:
    if not SEED_PATH.exists():
        return pd.DataFrame()
    src = pd.read_csv(SEED_PATH, compression="gzip", dtype={"celular": "string"})
    out = pd.DataFrame(index=src.index)
    out["registro_id"] = src.get("registro_id")
    out["fila_excel"] = pd.to_numeric(src.get("fila_excel"), errors="coerce").astype("Int64")
    out["promovido_original"] = src.get("promovido")
    out["promovido_normalizado"] = src.get("promovido_normalizado")
    out["telefono"] = src.get("celular", pd.Series(index=src.index, dtype=object)).map(_clean_phone)
    out["seccion"] = pd.to_numeric(src.get("seccion"), errors="coerce").astype("Int64")
    out["municipio"] = src.get("municipio_origen")
    out["municipio_excel"] = src.get("municipio_origen")

    for level in range(8):
        col = f"grupo_{level}"
        out[col] = src.get(col)
    out["ruta_jerarquica"] = src.get("ruta_jerarquica")
    out["nivel_desde_raiz"] = pd.to_numeric(src.get("nivel_profundidad"), errors="coerce").fillna(0).astype(int)
    out["superior_directo"] = out["ruta_jerarquica"].fillna("").map(
        lambda x: str(x).split(">")[-1].strip() if str(x).strip() else None
    )

    inferred = out["promovido_normalizado"].map(infer_surnames_from_full_name)
    out["apellido_paterno"] = inferred.map(lambda x: x[0])
    out["apellido_materno"] = inferred.map(lambda x: x[1])
    out["apellido_confianza"] = inferred.map(lambda x: x[2])
    out["apellido_origen"] = out["apellido_paterno"].map(lambda x: "DERIVADO_NOMBRE" if x else "NO_DISPONIBLE")

    out["casilla_original"] = src.get("casilla")
    out["localidad"] = None
    out["calle"] = None
    out["colonia"] = None
    out["numero_exterior"] = None
    out["numero_interior"] = None
    out["codigo_postal"] = None
    out["referencias"] = None

    for optional in ["genero", "correo", "edad", "kit", "observaciones", "comentario", "fecha_origen"]:
        out[optional] = src.get(optional)

    out["archivo_origen"] = src.get("archivo_origen").fillna(SEED_FILENAME) if "archivo_origen" in src else SEED_FILENAME
    out["estado_validacion"] = "LISTO"
    out.loc[out["promovido_normalizado"].isna(), "estado_validacion"] = "BLOQUEADO"
    out.loc[out["seccion"].isna(), "estado_validacion"] = "BLOQUEADO"
    return out


@lru_cache(maxsize=1)
def load_cached_booths() -> Tuple[pd.DataFrame, Dict[str, Any]]:
    if not CACHED_BOOTHS_PATH.exists():
        return pd.DataFrame(), {}
    booths = pd.read_csv(CACHED_BOOTHS_PATH, compression="gzip")
    meta = {
        "proceso": "PEL Sinaloa 2023-2024",
        "anio": 2024,
        "estatus": "HISTORICO_REFERENCIA",
        "vigente": False,
        "fuente": "IEES Sinaloa",
        "registros": len(booths),
        "secciones": int(booths["seccion"].nunique()) if "seccion" in booths else 0,
        "origen_carga": "REPOSITORIO",
    }
    return booths, meta


@lru_cache(maxsize=1)
def _load_booths_automatic() -> Tuple[pd.DataFrame, Dict[str, Any]]:
    cached, meta = load_cached_booths()
    if not cached.empty:
        return cached, meta
    try:
        booths, meta = fetch_iees_historical_2024(timeout=8)
        meta = dict(meta)
        meta["origen_carga"] = "DESCARGA_AUTOMATICA_IEES"
        return booths, meta
    except Exception as exc:
        return pd.DataFrame(), {
            "proceso": "PEL Sinaloa 2023-2024",
            "estatus": "NO_DISPONIBLE_AUTOMATICAMENTE",
            "fuente": "IEES Sinaloa",
            "error": str(exc),
            "nota": "La base territorial sí se cargó; la asignación individual de casilla se recalculará cuando el catálogo esté disponible.",
        }


def bootstrap_repo_seed(auto_booths: bool = True) -> bool:
    """Carga automáticamente la base incluida en el repositorio una vez por sesión."""
    if has_local_data():
        return False
    normalized = load_repo_seed().copy()
    if normalized.empty:
        return False
    booths, booth_meta = _load_booths_automatic() if auto_booths else (pd.DataFrame(), {})
    activate_repo_dataset(
        normalized=normalized,
        filename=SEED_FILENAME,
        booths=booths,
        booth_meta=booth_meta,
    )
    return True
