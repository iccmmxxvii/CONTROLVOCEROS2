from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, Optional, Tuple

import pandas as pd
import requests

from core.casillas import normalize_booth_catalog

IEES_2024_DETAIL_URL = "https://www.ieesinaloa.mx/wp-content/uploads/Transparencia/Organizacion/2024/3-Padron-Electoral-y-Lista-Nominal-Casillas-Sinaloa-2024-IEES.xlsx"
IEES_2024_APPROVED_URL = "https://www.ieesinaloa.mx/wp-content/uploads/Transparencia/Organizacion/2024/Casillas-APROBADAS-PEL-Sinaloa-2024.xlsx"


def _canon(value: Any) -> str:
    return str(value or "").strip().upper().replace("Á", "A").replace("É", "E").replace("Í", "I").replace("Ó", "O").replace("Ú", "U")


def _best_header_row(data: bytes, sheet: str) -> int:
    raw = pd.read_excel(BytesIO(data), sheet_name=sheet, header=None, nrows=30, dtype=object)
    best_idx = 0
    best_score = -1
    tokens = ("SECCION", "CASILLA", "MUNICIPIO", "DISTRITO", "LISTA NOMINAL", "PADRON")
    for idx, row in raw.iterrows():
        vals = [_canon(x) for x in row.tolist() if pd.notna(x)]
        joined = " | ".join(vals)
        score = sum(2 if t in {v for v in vals} else 1 for t in tokens if t in joined)
        if "SECCION" in joined and "CASILLA" in joined:
            score += 5
        if score > best_score:
            best_score = score
            best_idx = int(idx)
    return best_idx


def read_iees_historical_excel(data: bytes) -> pd.DataFrame:
    book = pd.ExcelFile(BytesIO(data))
    candidates = []
    for sheet in book.sheet_names:
        try:
            header = _best_header_row(data, sheet)
            df = pd.read_excel(BytesIO(data), sheet_name=sheet, header=header, dtype=object).dropna(how="all")
            score = sum(1 for c in df.columns if any(t in _canon(c) for t in ("SECCION", "CASILLA", "MUNICIPIO", "DISTRITO", "LISTA")))
            candidates.append((score, len(df), sheet, df))
        except Exception:
            continue
    if not candidates:
        raise ValueError("No fue posible identificar una tabla dentro del Excel histórico.")
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return candidates[0][3].reset_index(drop=True)


def fetch_iees_historical_2024(timeout: int = 15) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    headers = {"User-Agent": "Mozilla/5.0 ICC-Control-Territorial/3.0"}
    errors = []
    for url in (IEES_2024_DETAIL_URL, IEES_2024_APPROVED_URL):
        try:
            response = requests.get(url, timeout=timeout, headers=headers)
            response.raise_for_status()
            raw = read_iees_historical_excel(response.content)
            booths, mapping = normalize_booth_catalog(raw)
            if booths.empty:
                raise ValueError("El archivo se descargó, pero no se detectaron registros de casillas.")
            booths["fuente_catalogo"] = "IEES Sinaloa"
            booths["proceso_electoral"] = "PEL Sinaloa 2023-2024"
            booths["estatus_catalogo"] = "HISTORICO_REFERENCIA"
            meta = {
                "proceso": "PEL Sinaloa 2023-2024",
                "anio": 2024,
                "estatus": "HISTORICO_REFERENCIA",
                "vigente": False,
                "fuente": "IEES Sinaloa",
                "url_fuente": url,
                "registros": len(booths),
                "secciones": int(booths["seccion"].nunique()),
                "rangos_alfabeticos": int((booths.get("apellido_desde", pd.Series(index=booths.index, dtype=object)).notna() | booths.get("apellido_hasta", pd.Series(index=booths.index, dtype=object)).notna()).sum()),
                "motor_casilla": "EXACTA_SUGERIDA_PENDIENTE_V3.2",
                "nota": "Catálogo histórico de referencia. Si no publica rangos de apellidos, V3.2 puede generar sugerencias operativas claramente diferenciadas de una asignación exacta.",
                "mapeo_detectado": mapping,
            }
            return booths, meta
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    raise RuntimeError("No fue posible descargar el catálogo histórico 2024. " + " | ".join(errors))
