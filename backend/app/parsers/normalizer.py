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


def version_changed(old: str | None, new: str | None) -> bool:
    """
    Decide si la versión de referencia debe actualizarse a `new`.

    Las versiones SON TEXTO (VARCHAR): nunca se comparan numérica ni
    lexicográficamente (`"9.0" > "10.0"` daría un resultado incorrecto).
    Solo comparamos igualdad sobre el texto limpio:

    - si `new` no tiene una versión detectable -> no hay cambio (False);
    - si no había versión previa y ahora sí -> cambio (True);
    - en otro caso -> cambia si el texto difiere.
    """
    new_clean = clean_version(new)
    if new_clean is None:
        return False
    old_clean = clean_version(old)
    if old_clean is None:
        return True
    return old_clean != new_clean
