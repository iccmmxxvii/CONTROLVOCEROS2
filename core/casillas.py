from __future__ import annotations

import json
import re
import unicodedata
from io import BytesIO
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd


def _clean(value: Any) -> Optional[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


def _key(value: Any) -> Optional[str]:
    text = _clean(value)
    if not text:
        return None
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"\s+", " ", text.upper()).strip()
    return text or None


def normalize_booth_type(value: Any) -> Optional[str]:
    v = _key(value)
    if not v:
        return None
    if v == "B" or v.startswith("BASICA") or v.startswith("BASICO"):
        return "B"
    if v.startswith("C") or "CONTIG" in v:
        m = re.search(r"(\d+)", v)
        return f"C{m.group(1)}" if m else "C1"
    if v.startswith("E") or "EXTRA" in v:
        m = re.search(r"(\d+)", v)
        return f"E{m.group(1)}" if m else "E1"
    if v.startswith("S") or "ESPEC" in v:
        m = re.search(r"(\d+)", v)
        return f"S{m.group(1)}" if m else "S1"
    return v


BOOTH_ALIASES = {
    "seccion": ["SECCION", "SECCIÓN"],
    "municipio": ["MUNICIPIO"],
    "tipo": ["TIPO CASILLA", "TIPO", "CASILLA TIPO", "TIPO_CASILLA"],
    "numero": ["NUMERO CASILLA", "NÚMERO CASILLA", "NUM CASILLA", "NUMERO", "NÚMERO"],
    "clave": ["CLAVE CASILLA", "CASILLA", "CLAVE"],
    "apellido_desde": ["APELLIDO DESDE", "INICIAL DESDE", "RANGO DESDE", "DESDE"],
    "apellido_hasta": ["APELLIDO HASTA", "INICIAL HASTA", "RANGO HASTA", "HASTA"],
    "localidad": ["LOCALIDAD"],
    "domicilio": ["DOMICILIO", "DIRECCION", "DIRECCIÓN", "UBICACION", "UBICACIÓN"],
    "distrito_local": ["DISTRITO LOCAL", "DISTRITO_LOCAL", "DTTO LOCAL", "DTO LOCAL"],
    "distrito_federal": ["DISTRITO FEDERAL", "DISTRITO_FEDERAL", "DTTO FEDERAL", "DTO FEDERAL"],
    "lista_nominal": ["LISTA NOMINAL", "LISTA_NOMINAL", "LN"],
    "padron_electoral": ["PADRON ELECTORAL", "PADRÓN ELECTORAL", "PADRON", "PE"],
}


def detect_booth_columns(columns: Iterable[Any]) -> Dict[str, Optional[str]]:
    by = {_key(c): str(c) for c in columns}
    out: Dict[str, Optional[str]] = {}
    for field, aliases in BOOTH_ALIASES.items():
        out[field] = next((by.get(_key(a)) for a in aliases if by.get(_key(a))), None)
    return out


def read_booth_catalog(data: bytes, sheet_name: Optional[str] = None) -> Tuple[pd.DataFrame, List[str]]:
    excel = pd.ExcelFile(BytesIO(data))
    sheets = excel.sheet_names
    selected = sheet_name or sheets[0]
    df = pd.read_excel(BytesIO(data), sheet_name=selected, dtype=object).dropna(how="all").reset_index(drop=True)
    return df, sheets


def normalize_booth_catalog(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Optional[str]]]:
    mapping = detect_booth_columns(df.columns)
    rows: List[Dict[str, Any]] = []
    for _, r in df.iterrows():
        section_raw = r.get(mapping.get("seccion")) if mapping.get("seccion") else None
        try:
            section = int(float(section_raw)) if section_raw is not None and str(section_raw).strip() else None
        except Exception:
            section = None
        booth_type = normalize_booth_type(r.get(mapping.get("tipo")) if mapping.get("tipo") else None)
        num_raw = r.get(mapping.get("numero")) if mapping.get("numero") else None
        try:
            number = int(float(num_raw)) if num_raw is not None and str(num_raw).strip() else None
        except Exception:
            number = None
        explicit_key = _clean(r.get(mapping.get("clave")) if mapping.get("clave") else None)
        if not booth_type and explicit_key:
            booth_type = normalize_booth_type(explicit_key)
        if booth_type and booth_type[0] in {"C", "E", "S"} and len(booth_type) > 1 and number is None:
            try:
                number = int(booth_type[1:])
            except Exception:
                pass
        if section and booth_type:
            ex_key = _key(explicit_key) if explicit_key else None
            label = explicit_key if ex_key and str(section) in ex_key else f"{section} {booth_type}"
        else:
            label = explicit_key
        rows.append({
            "seccion": section,
            "municipio": _key(r.get(mapping.get("municipio")) if mapping.get("municipio") else None),
            "tipo_casilla": booth_type,
            "numero_casilla": number,
            "clave_casilla": label,
            "apellido_desde": _key(r.get(mapping.get("apellido_desde")) if mapping.get("apellido_desde") else None),
            "apellido_hasta": _key(r.get(mapping.get("apellido_hasta")) if mapping.get("apellido_hasta") else None),
            "localidad": _key(r.get(mapping.get("localidad")) if mapping.get("localidad") else None),
            "domicilio": _clean(r.get(mapping.get("domicilio")) if mapping.get("domicilio") else None),
            "distrito_local": _clean(r.get(mapping.get("distrito_local")) if mapping.get("distrito_local") else None),
            "distrito_federal": _clean(r.get(mapping.get("distrito_federal")) if mapping.get("distrito_federal") else None),
            "lista_nominal": _clean(r.get(mapping.get("lista_nominal")) if mapping.get("lista_nominal") else None),
            "padron_electoral": _clean(r.get(mapping.get("padron_electoral")) if mapping.get("padron_electoral") else None),
        })
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out[out["seccion"].notna() & out["tipo_casilla"].notna()].copy()
        out["casilla_id"] = out.apply(lambda x: f"local-cas-{int(x['seccion'])}-{x['tipo_casilla']}", axis=1)
    return out.reset_index(drop=True), mapping


def _surname_in_range(surname: str, start: Optional[str], end: Optional[str]) -> bool:
    s = _key(surname)
    if not s:
        return False
    lo = _key(start) or "A"
    hi = _key(end) or "ZZZZZZZZ"
    return lo <= s <= hi




EXACT_ASSIGNMENT_STATUSES = {"CONFIRMADA", "AUTOMATICA"}
SUGGESTED_ASSIGNMENT_STATUSES = {"SUGERIDA"}


def is_exact_assignment_status(value: Any) -> bool:
    return str(value or "").upper() in EXACT_ASSIGNMENT_STATUSES


def is_suggested_assignment_status(value: Any) -> bool:
    return str(value or "").upper() in SUGGESTED_ASSIGNMENT_STATUSES


def _booth_sort_key(row: pd.Series) -> Tuple[int, int]:
    t = str(row.get("tipo_casilla") or "").upper()
    if t == "B":
        return (0, 0)
    if t.startswith("C"):
        m = re.search(r"(\d+)", t)
        return (1, int(m.group(1)) if m else 1)
    return (9, 999)


def _numeric_weight(value: Any) -> Optional[float]:
    text = _clean(value)
    if not text:
        return None
    text = re.sub(r"[^0-9.]", "", text.replace(",", ""))
    try:
        number = float(text)
        return number if number > 0 else None
    except Exception:
        return None


def _surname_fraction(value: Any) -> Optional[float]:
    """Posición alfabética estable [0,1) para una sugerencia operativa, no oficial."""
    text = _key(value)
    if not text:
        return None
    letters = re.sub(r"[^A-Z]", "", text)[:4]
    if not letters:
        return None
    # Base 27 con 1..26; permite ordenar PEREZ por algo más que la inicial.
    score = 0.0
    scale = 1.0
    for ch in letters:
        scale *= 27.0
        score += (ord(ch) - 64) / scale
    return min(max(score, 0.0), 0.999999)


def _suggest_ordinary_booth(surname: Any, ordinary: pd.DataFrame) -> Tuple[Optional[pd.Series], str]:
    """Sugiere B/C por proyección alfabética cuando el catálogo no publica rangos.

    La sugerencia NUNCA se considera asignación exacta. Si existe lista nominal por
    casilla, la usa como ponderador; de lo contrario reparte el alfabeto en partes
    iguales entre B/C.
    """
    if ordinary.empty or len(ordinary) < 2:
        return None, "SIN_BASE_PARA_SUGERENCIA"
    pos = _surname_fraction(surname)
    if pos is None:
        return None, "NOMBRE_SIN_APELLIDO_DETERMINABLE"
    ordered = ordinary.copy()
    ordered["_sort"] = ordered.apply(_booth_sort_key, axis=1)
    ordered = ordered.sort_values("_sort").drop(columns=["_sort"])
    weights = ordered.get("lista_nominal", pd.Series(index=ordered.index, dtype=object)).map(_numeric_weight)
    uses_ln = bool(weights.notna().all() and (weights > 0).all())
    if not uses_ln:
        weights = pd.Series([1.0] * len(ordered), index=ordered.index)
    total = float(weights.sum())
    cumulative = 0.0
    for idx, weight in weights.items():
        cumulative += float(weight) / total
        if pos < cumulative + 1e-12:
            return ordered.loc[idx], "PROYECCION_ALFABETICA_LISTA_NOMINAL" if uses_ln else "PROYECCION_ALFABETICA_EQUITATIVA"
    return ordered.iloc[-1], "PROYECCION_ALFABETICA_LISTA_NOMINAL" if uses_ln else "PROYECCION_ALFABETICA_EQUITATIVA"



def _booth_dict_sort_key(row: Dict[str, Any]) -> Tuple[int, int]:
    t = str(row.get("tipo_casilla") or "").upper()
    if t == "B":
        return (0, 0)
    if t.startswith("C"):
        m = re.search(r"(\d+)", t)
        return (1, int(m.group(1)) if m else 1)
    return (9, 999)


def _suggest_ordinary_booth_rows(surname: Any, ordinary: List[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], str]:
    if len(ordinary) < 2:
        return None, "SIN_BASE_PARA_SUGERENCIA"
    pos = _surname_fraction(surname)
    if pos is None:
        return None, "NOMBRE_SIN_APELLIDO_DETERMINABLE"
    ordered = sorted(ordinary, key=_booth_dict_sort_key)
    raw_weights = [_numeric_weight(x.get("lista_nominal")) for x in ordered]
    uses_ln = all(x is not None and x > 0 for x in raw_weights)
    weights = raw_weights if uses_ln else [1.0] * len(ordered)
    total = float(sum(weights))
    cumulative = 0.0
    for row, weight in zip(ordered, weights):
        cumulative += float(weight) / total
        if pos < cumulative + 1e-12:
            return row, "PROYECCION_ALFABETICA_LISTA_NOMINAL" if uses_ln else "PROYECCION_ALFABETICA_EQUITATIVA"
    return ordered[-1], "PROYECCION_ALFABETICA_LISTA_NOMINAL" if uses_ln else "PROYECCION_ALFABETICA_EQUITATIVA"


def assignment_reason_label(code: Any) -> str:
    labels = {
        "SECCION_SIN_CASILLAS_CATALOGO_ACTIVO": "Sección sin casillas en catálogo activo",
        "CASILLA_EXPLICITA_EN_EXCEL": "Casilla indicada en Excel",
        "CASILLA_EXPLICITA_NO_COINCIDE_CATALOGO": "Casilla indicada no coincide con catálogo",
        "UNICA_CASILLA_EN_SECCION": "Única casilla en la sección",
        "LOCALIDAD_COINCIDE_EXTRAORDINARIA": "Localidad coincide con casilla extraordinaria",
        "RANGO_ALFABETICO_APELLIDO_EXPLICITO": "Asignación por rango alfabético y apellido capturado",
        "RANGO_ALFABETICO_APELLIDO_DERIVADO": "Asignación por rango alfabético y apellido derivado del nombre",
        "RANGO_ALFABETICO_AMBIGUO": "Rango alfabético ambiguo",
        "CATALOGO_SIN_RANGOS_ALFABETICOS": "Catálogo sin rangos alfabéticos suficientes",
        "NOMBRE_SIN_APELLIDO_DETERMINABLE": "Nombre sin apellido determinable",
        "APELLIDO_FUERA_RANGOS_CATALOGO": "Apellido sin correspondencia única en rangos",
        "FALTAN_DATOS_PARA_DETERMINAR_CASILLA": "Faltan datos para determinar casilla",
        "PROYECCION_ALFABETICA_LISTA_NOMINAL": "Sugerencia operativa por orden alfabético ponderado con lista nominal",
        "PROYECCION_ALFABETICA_EQUITATIVA": "Sugerencia operativa por orden alfabético entre casillas B/C",
        "EXTRAORDINARIA_SIN_LOCALIDAD": "Sección con casilla extraordinaria; falta localidad para asignar con certeza",
        "SIN_BASE_PARA_SUGERENCIA": "Sin base suficiente para sugerir casilla",
        "SIN_CATALOGO": "Sin catálogo de casillas activo",
    }
    return labels.get(str(code), str(code or "Pendiente de validar").replace("_", " ").title())


def assign_records_to_booths(normalized: pd.DataFrame, booths: pd.DataFrame) -> pd.DataFrame:
    if normalized.empty:
        return pd.DataFrame()
    rows: List[Dict[str, Any]] = []

    # Catálogo indexado en memoria por sección. Esto mantiene el cálculo viable
    # con bases de 10k+ personas y evita filtros DataFrame repetidos por registro.
    booth_by_section: Dict[str, List[Dict[str, Any]]] = {}
    if isinstance(booths, pd.DataFrame) and not booths.empty and "seccion" in booths.columns:
        for booth in booths.to_dict("records"):
            raw_sec = booth.get("seccion")
            try:
                key = str(int(float(raw_sec))) if raw_sec is not None and str(raw_sec).strip() else None
            except Exception:
                key = None
            if key:
                booth_by_section.setdefault(key, []).append(booth)

    for idx, rec in normalized.iterrows():
        section = rec.get("seccion")
        municipality = _key(rec.get("municipio"))
        promoted = rec.get("promovido_normalizado")
        parent = rec.get("superior_directo")
        explicit = _clean(rec.get("casilla_original")) if "casilla_original" in normalized.columns else None
        surname = rec.get("apellido_paterno") if "apellido_paterno" in normalized.columns else None
        surname_origin = rec.get("apellido_origen") if "apellido_origen" in normalized.columns else None
        surname_confidence = rec.get("apellido_confianza") if "apellido_confianza" in normalized.columns else None
        locality = _key(rec.get("localidad"))
        try:
            section_key = str(int(float(section))) if section is not None and str(section).strip() else None
        except Exception:
            section_key = None
        candidates = list(booth_by_section.get(section_key, [])) if section_key else []
        if municipality and candidates:
            matching = [b for b in candidates if not _key(b.get("municipio")) or _key(b.get("municipio")) == municipality]
            if matching:
                candidates = matching

        assigned: Optional[Dict[str, Any]] = None
        status = "PENDIENTE"
        reason = "SIN_CATALOGO"
        if not candidates:
            reason = "SECCION_SIN_CASILLAS_CATALOGO_ACTIVO"
        elif explicit:
            ex = _key(explicit)
            matches = [b for b in candidates if _key(b.get("clave_casilla")) == ex]
            if len(matches) == 1:
                assigned = matches[0]
                status, reason = "CONFIRMADA", "CASILLA_EXPLICITA_EN_EXCEL"
            else:
                reason = "CASILLA_EXPLICITA_NO_COINCIDE_CATALOGO"
        elif len(candidates) == 1:
            assigned = candidates[0]
            status, reason = "AUTOMATICA", "UNICA_CASILLA_EN_SECCION"
        else:
            extra = [b for b in candidates if str(b.get("tipo_casilla") or "").startswith("E")]
            if locality and extra:
                matches = [b for b in extra if _key(b.get("localidad")) == locality]
                if len(matches) == 1:
                    assigned = matches[0]
                    status, reason = "AUTOMATICA", "LOCALIDAD_COINCIDE_EXTRAORDINARIA"

            if assigned is None and surname:
                ordinary = [b for b in candidates if not str(b.get("tipo_casilla") or "").startswith("E") and not str(b.get("tipo_casilla") or "").startswith("S")]
                ranged = [b for b in ordinary if _clean(b.get("apellido_desde")) or _clean(b.get("apellido_hasta"))]
                if not ranged:
                    confidence = str(surname_confidence or "").upper()
                    if extra and not locality:
                        reason = "EXTRAORDINARIA_SIN_LOCALIDAD"
                    elif confidence in {"ALTA", "MEDIA"} or surname_origin == "EXCEL":
                        suggestion, suggestion_reason = _suggest_ordinary_booth_rows(surname, ordinary)
                        if suggestion is not None:
                            assigned = suggestion
                            status, reason = "SUGERIDA", suggestion_reason
                        else:
                            reason = "CATALOGO_SIN_RANGOS_ALFABETICOS"
                    else:
                        reason = "CATALOGO_SIN_RANGOS_ALFABETICOS"
                else:
                    matches = [b for b in ranged if _surname_in_range(surname, b.get("apellido_desde"), b.get("apellido_hasta"))]
                    if len(matches) == 1:
                        assigned = matches[0]
                        if surname_origin == "EXCEL":
                            status, reason = "AUTOMATICA", "RANGO_ALFABETICO_APELLIDO_EXPLICITO"
                        elif str(surname_confidence).upper() == "ALTA":
                            status, reason = "AUTOMATICA", "RANGO_ALFABETICO_APELLIDO_DERIVADO"
                        else:
                            status, reason = "SUGERIDA", "RANGO_ALFABETICO_APELLIDO_DERIVADO"
                    elif len(matches) > 1:
                        reason = "RANGO_ALFABETICO_AMBIGUO"
                    else:
                        reason = "APELLIDO_FUERA_RANGOS_CATALOGO"
            elif assigned is None:
                reason = "NOMBRE_SIN_APELLIDO_DETERMINABLE"

        rows.append({
            "registro_idx": idx,
            "fila_excel": rec.get("fila_excel"),
            "archivo_origen": rec.get("archivo_origen"),
            "estructura_origen": rec.get("estructura_origen"),
            "fecha_importacion": rec.get("fecha_importacion"),
            "importacion_id": rec.get("importacion_id"),
            "promovido": promoted,
            "coordinador_directo": parent,
            "seccion": section,
            "municipio": municipality,
            "apellido_usado": surname,
            "apellido_origen": surname_origin,
            "apellido_confianza": surname_confidence,
            "casilla_id": None if assigned is None else assigned.get("casilla_id"),
            "clave_casilla": None if assigned is None else assigned.get("clave_casilla"),
            "tipo_casilla": None if assigned is None else assigned.get("tipo_casilla"),
            "estado_asignacion": status,
            "es_asignacion_exacta": is_exact_assignment_status(status),
            "es_asignacion_sugerida": is_suggested_assignment_status(status),
            "criterio_asignacion": reason,
            "criterio_descripcion": assignment_reason_label(reason),
        })
    return pd.DataFrame(rows)

def booth_summary(assignments: pd.DataFrame, responsibilities: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    if assignments.empty:
        return pd.DataFrame()
    a = assignments[assignments["casilla_id"].notna()].copy()
    if a.empty:
        return pd.DataFrame()
    grouped = a.groupby(["casilla_id", "clave_casilla", "seccion", "municipio"], dropna=False)
    rows: List[Dict[str, Any]] = []
    for keys, g in grouped:
        casilla_id, clave, section, muni = keys
        counts = g["coordinador_directo"].dropna().value_counts()
        top_coord = counts.index[0] if not counts.empty else None
        top_count = int(counts.iloc[0]) if not counts.empty else 0
        formal = None
        if isinstance(responsibilities, pd.DataFrame) and not responsibilities.empty:
            m = responsibilities[(responsibilities["tipo_territorio"] == "CASILLA") & (responsibilities["territorio_id"] == casilla_id) & (responsibilities["activo"] == True)]
            if not m.empty:
                formal = m.iloc[-1].get("responsable_nombre")
        exact_n = int(g.get("es_asignacion_exacta", pd.Series(False, index=g.index)).fillna(False).astype(bool).sum())
        suggested_n = int(g.get("es_asignacion_sugerida", pd.Series(False, index=g.index)).fillna(False).astype(bool).sum())
        rows.append({
            "casilla_id": casilla_id,
            "clave_casilla": clave,
            "seccion": section,
            "municipio": muni,
            "promovidos": int(len(g)),
            "promovidos_exactos": exact_n,
            "promovidos_sugeridos": suggested_n,
            "promovidos_unicos": int(g["promovido"].nunique()),
            "coordinadores_con_promovidos": int(g["coordinador_directo"].dropna().nunique()),
            "coordinador_mayor_estructura": top_coord,
            "promovidos_coordinador_top": top_count,
            "responsable_formal": formal,
            "coincide_responsable_top": None if not formal or not top_coord else formal == top_coord,
        })
    return pd.DataFrame(rows).sort_values(["municipio", "seccion", "clave_casilla"], na_position="last")


def parse_geojson(data: bytes) -> Dict[str, Any]:
    return json.loads(data.decode("utf-8"))
