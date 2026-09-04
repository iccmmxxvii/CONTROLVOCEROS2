from __future__ import annotations

import math
import re
import unicodedata
from typing import Any, Optional


def clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        if isinstance(value, float) and math.isnan(value):
            return None
    except Exception:
        pass
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "nat"}:
        return None
    return re.sub(r"\s+", " ", text)


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def normalize_name(value: Any) -> Optional[str]:
    text = clean_text(value)
    if not text:
        return None
    text = strip_accents(text).upper().strip()
    text = re.sub(r"[^A-ZÑ0-9 .'-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()




def infer_surnames_from_full_name(value: Any):
    """Infiere apellidos desde un nombre completo sin alterar el valor original.

    Devuelve (apellido_paterno, apellido_materno, confianza). La inferencia es
    deliberadamente conservadora: sirve como apoyo operativo, pero conserva
    trazabilidad para distinguirla de un apellido capturado explícitamente.
    """
    name = normalize_name(value)
    if not name:
        return None, None, "BAJA"
    tokens = [t for t in name.split() if t]
    if len(tokens) >= 4:
        return tokens[-2], tokens[-1], "ALTA"
    if len(tokens) == 3:
        return tokens[-2], tokens[-1], "MEDIA"
    if len(tokens) == 2:
        return tokens[-1], None, "MEDIA"
    return None, None, "BAJA"


def normalize_municipality(value: Any) -> Optional[str]:
    text = normalize_name(value)
    if not text:
        return None
    aliases = {
        "CULIACAN ROSALES": "CULIACAN",
        "MAZATLAN SINALOA": "MAZATLAN",
        "EL ROSARIO": "ROSARIO",
        "JUAN JOSE RIOS": "JUAN JOSE RIOS",
    }
    return aliases.get(text, text)


def normalize_phone(value: Any) -> Optional[str]:
    text = clean_text(value)
    if not text:
        return None
    digits = re.sub(r"\D", "", text)
    if digits.startswith("52") and len(digits) == 12:
        digits = digits[2:]
    if len(digits) > 10:
        digits = digits[-10:]
    return digits or None


def normalize_section(value: Any) -> Optional[int]:
    text = clean_text(value)
    if not text:
        return None
    match = re.search(r"\d+", text.replace(",", ""))
    if not match:
        return None
    number = int(match.group())
    if number <= 0:
        return None
    return number


def normalize_int(value: Any) -> Optional[int]:
    text = clean_text(value)
    if not text:
        return None
    match = re.search(r"-?\d+", text.replace(",", ""))
    return int(match.group()) if match else None


def normalize_float(value: Any) -> Optional[float]:
    text = clean_text(value)
    if not text:
        return None
    text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None
