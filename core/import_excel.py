from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

from core.normalization import (
    clean_text,
    normalize_municipality,
    normalize_name,
    normalize_phone,
    normalize_section,
    infer_surnames_from_full_name,
)

EXPECTED_ALIASES = {
    "promovido": ["PROMOVIDO", "PROMOVIDOS", "VOCERO", "VOCEROS", "NOMBRE"],
    "telefono": ["CELULAR", "TELEFONO", "TELÉFONO", "MOVIL", "MÓVIL"],
    "grupo_0": ["COORDINADOR", "GRUPO 0", "GRUPO0", "LIDER 0", "LÍDER 0"],
    "grupo_1": ["GRUPO 1", "GRUPO1"],
    "grupo_2": ["GRUPO 2", "GRUPO2"],
    "grupo_3": ["GRUPO 3", "GRUPO3"],
    "grupo_4": ["GRUPO 4", "GRUPO4"],
    "grupo_5": ["GRUPO 5", "GRUPO5"],
    "grupo_6": ["GRUPO 6", "GRUPO6"],
    "grupo_7": ["GRUPO 7", "GRUPO7"],
    "seccion": ["SECCION", "SECCIÓN", "SECCIONESFORM"],
    "municipio": ["MUNICIPIO", "MUNICIPIOFORM"],
    "calle": ["CALLE", "DOMICILIO", "DIRECCION", "DIRECCIÓN"],
    "numero_exterior": ["NUMERO", "NÚMERO", "NO EXT", "NUM EXT", "NUMERO EXTERIOR"],
    "numero_interior": ["NUM INT", "NUMERO INTERIOR", "NÚMERO INTERIOR"],
    "colonia": ["COLONIA"],
    "localidad": ["LOCALIDAD"],
    "codigo_postal": ["CP", "C.P.", "CODIGO POSTAL", "CÓDIGO POSTAL"],
    "referencias": ["REFERENCIAS", "REFERENCIA"],
    "apellido_paterno": ["APELLIDO PATERNO", "PRIMER APELLIDO", "PATERNO"],
    "apellido_materno": ["APELLIDO MATERNO", "SEGUNDO APELLIDO", "MATERNO"],
    "casilla": ["CASILLA", "CLAVE CASILLA", "CASILLA ASIGNADA"],
}



def _canonical_header(value: Any) -> str:
    return (clean_text(value) or "").upper()


def detect_columns(columns: Iterable[Any]) -> Dict[str, Optional[str]]:
    by_upper = {_canonical_header(c): str(c) for c in columns}
    result: Dict[str, Optional[str]] = {}
    for field, aliases in EXPECTED_ALIASES.items():
        result[field] = next((by_upper[a] for a in aliases if a in by_upper), None)
    return result


def read_excel_bytes(data: bytes, sheet_name: Optional[str] = None) -> Tuple[pd.DataFrame, List[str]]:
    excel = pd.ExcelFile(BytesIO(data))
    sheets = excel.sheet_names
    selected = sheet_name or sheets[0]
    df = pd.read_excel(BytesIO(data), sheet_name=selected, dtype=object)
    df = df.dropna(how="all").reset_index(drop=True)
    return df, sheets


def _value(row: pd.Series, column: Optional[str]) -> Any:
    return row.get(column) if column else None


def hierarchy_path_from_row(row: pd.Series, mapping: Dict[str, Optional[str]]) -> List[str]:
    path: List[str] = []
    for field in ("grupo_0", "grupo_1", "grupo_2", "grupo_3", "grupo_4", "grupo_5", "grupo_6", "grupo_7"):
        name = normalize_name(_value(row, mapping.get(field)))
        if name and (not path or path[-1] != name):
            path.append(name)
    return path


def normalize_dataframe(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Optional[str]]]:
    mapping = detect_columns(df.columns)
    rows: List[Dict[str, Any]] = []
    incidents: List[Dict[str, Any]] = []

    for field in ("promovido", "seccion", "municipio"):
        if not mapping.get(field):
            incidents.append({
                "fila_excel": None,
                "severidad": "ERROR",
                "tipo": "COLUMNA_FALTANTE",
                "campo": field,
                "valor": None,
                "mensaje": f"No se detectó una columna para {field}.",
            })

    for idx, row in df.iterrows():
        excel_row = idx + 2
        promoted_original = clean_text(_value(row, mapping.get("promovido")))
        if promoted_original and promoted_original.upper().startswith("TOTAL"):
            incidents.append({
                "fila_excel": excel_row,
                "severidad": "INFO",
                "tipo": "FILA_RESUMEN_IGNORADA",
                "campo": "promovido",
                "valor": promoted_original,
                "mensaje": "Fila de resumen detectada; se conserva en RAW y no se importa como persona.",
            })
            continue

        promoted = normalize_name(promoted_original)
        phone = normalize_phone(_value(row, mapping.get("telefono")))
        section = normalize_section(_value(row, mapping.get("seccion")))
        municipality = normalize_municipality(_value(row, mapping.get("municipio")))
        hierarchy = hierarchy_path_from_row(row, mapping)

        while promoted and hierarchy and hierarchy[-1] == promoted:
            hierarchy.pop()
        direct_parent = hierarchy[-1] if hierarchy else None

        apellido_paterno_excel = normalize_name(_value(row, mapping.get("apellido_paterno")))
        apellido_materno_excel = normalize_name(_value(row, mapping.get("apellido_materno")))
        if apellido_paterno_excel:
            apellido_paterno = apellido_paterno_excel
            apellido_materno = apellido_materno_excel
            apellido_origen = "EXCEL"
            apellido_confianza = "ALTA"
        else:
            apellido_paterno, apellido_materno_inferido, apellido_confianza = infer_surnames_from_full_name(promoted)
            apellido_materno = apellido_materno_excel or apellido_materno_inferido
            apellido_origen = "DERIVADO_NOMBRE" if apellido_paterno else "NO_DISPONIBLE"

        normalized = {
            "fila_excel": excel_row,
            "promovido_original": promoted_original,
            "promovido_normalizado": promoted,
            "telefono": phone,
            "seccion": section,
            "municipio": municipality,
            "superior_directo": direct_parent,
            "ruta_jerarquica": " > ".join(hierarchy) if hierarchy else None,
            "nivel_desde_raiz": len(hierarchy),
            "grupo_0": normalize_name(_value(row, mapping.get("grupo_0"))) or (hierarchy[0] if hierarchy else None),
            "grupo_1": normalize_name(_value(row, mapping.get("grupo_1"))),
            "grupo_2": normalize_name(_value(row, mapping.get("grupo_2"))),
            "grupo_3": normalize_name(_value(row, mapping.get("grupo_3"))),
            "grupo_4": normalize_name(_value(row, mapping.get("grupo_4"))),
            "grupo_5": normalize_name(_value(row, mapping.get("grupo_5"))),
            "grupo_6": normalize_name(_value(row, mapping.get("grupo_6"))),
            "grupo_7": normalize_name(_value(row, mapping.get("grupo_7"))),
            "calle": clean_text(_value(row, mapping.get("calle"))),
            "numero_exterior": clean_text(_value(row, mapping.get("numero_exterior"))),
            "numero_interior": clean_text(_value(row, mapping.get("numero_interior"))),
            "colonia": clean_text(_value(row, mapping.get("colonia"))),
            "localidad": clean_text(_value(row, mapping.get("localidad"))),
            "codigo_postal": clean_text(_value(row, mapping.get("codigo_postal"))),
            "referencias": clean_text(_value(row, mapping.get("referencias"))),
            "apellido_paterno": apellido_paterno,
            "apellido_materno": apellido_materno,
            "apellido_origen": apellido_origen,
            "apellido_confianza": apellido_confianza,
            "casilla_original": clean_text(_value(row, mapping.get("casilla"))),
            "estado_validacion": "LISTO",
        }

        if not promoted:
            normalized["estado_validacion"] = "BLOQUEADO"
            incidents.append({"fila_excel": excel_row, "severidad": "ERROR", "tipo": "SIN_NOMBRE", "campo": "promovido", "valor": None, "mensaje": "Registro sin nombre de promovido."})
        if not section:
            normalized["estado_validacion"] = "BLOQUEADO"
            incidents.append({"fila_excel": excel_row, "severidad": "ERROR", "tipo": "SECCION_INVALIDA", "campo": "seccion", "valor": clean_text(_value(row, mapping.get("seccion"))), "mensaje": "No fue posible interpretar la sección electoral."})
        if not municipality:
            normalized["estado_validacion"] = "BLOQUEADO"
            incidents.append({"fila_excel": excel_row, "severidad": "ERROR", "tipo": "SIN_MUNICIPIO", "campo": "municipio", "valor": None, "mensaje": "Registro sin municipio."})
        if phone and len(phone) != 10:
            if normalized["estado_validacion"] == "LISTO":
                normalized["estado_validacion"] = "REVISAR"
            incidents.append({"fila_excel": excel_row, "severidad": "ADVERTENCIA", "tipo": "TELEFONO_LONGITUD", "campo": "telefono", "valor": phone, "mensaje": "El teléfono no tiene 10 dígitos nacionales."})

        rows.append(normalized)

    normalized_df = pd.DataFrame(rows)
    if normalized_df.empty:
        return normalized_df, pd.DataFrame(incidents), mapping

    normalized_df["posible_duplicado_nombre"] = False
    normalized_df["posible_duplicado_telefono"] = False

    names = normalized_df["promovido_normalizado"].dropna()
    if not names.empty:
        dups = names[names.duplicated(keep=False)].index
        normalized_df.loc[dups, "posible_duplicado_nombre"] = True
    phones = normalized_df["telefono"].dropna()
    if not phones.empty:
        dups = phones[phones.duplicated(keep=False)].index
        normalized_df.loc[dups, "posible_duplicado_telefono"] = True

    duplicate_mask = normalized_df["posible_duplicado_nombre"] | normalized_df["posible_duplicado_telefono"]
    normalized_df.loc[duplicate_mask & (normalized_df["estado_validacion"] == "LISTO"), "estado_validacion"] = "REVISAR"

    # Los duplicados son incidencias informativas, no se fusionan automáticamente.
    for _, r in normalized_df[duplicate_mask].iterrows():
        incidents.append({
            "fila_excel": int(r["fila_excel"]),
            "severidad": "ADVERTENCIA",
            "tipo": "POSIBLE_DUPLICADO",
            "campo": "persona",
            "valor": r.get("promovido_original"),
            "mensaje": "Coincidencia de nombre o teléfono dentro del archivo. Se conserva para revisión; no se fusiona automáticamente.",
        })

    return normalized_df, pd.DataFrame(incidents), mapping


def build_raw_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    result = []
    for idx, row in df.iterrows():
        raw: Dict[str, Any] = {}
        for col in df.columns:
            value = row.get(col)
            if pd.isna(value):
                value = None
            elif hasattr(value, "item"):
                try:
                    value = value.item()
                except Exception:
                    pass
            raw[str(col)] = value
        result.append({"row_number": idx + 2, "raw_data": raw})
    return result


def normalized_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    if df.empty:
        return records
    for _, row in df.iterrows():
        data = {}
        for key, value in row.to_dict().items():
            if pd.isna(value):
                value = None
            elif hasattr(value, "item"):
                try:
                    value = value.item()
                except Exception:
                    pass
            data[key] = value
        records.append({
            "row_number": int(data["fila_excel"]),
            "normalized_data": data,
            "validation_status": data.get("estado_validacion") or "LISTO",
        })
    return records
