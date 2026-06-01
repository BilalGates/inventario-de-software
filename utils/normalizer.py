from __future__ import annotations

import math
import re
import unicodedata
from typing import Any


def normalize_nombre(nombre: str) -> str:
    val = unicodedata.normalize("NFC", str(nombre or ""))
    val = val.strip().upper()
    return re.sub(r"\s+", " ", val)


def normalize_equipo_nombre(nombre: str) -> str:
    return normalize_nombre(nombre)


def clean_version(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, float) and math.isnan(raw):
        return None
    if isinstance(raw, (int, float)):
        return str(int(raw))
    val = str(raw).strip()
    return val if val not in ("", "-", "–", "nan", "NaN", "None") else None
