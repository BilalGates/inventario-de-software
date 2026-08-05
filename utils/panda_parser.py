from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from utils.normalizer import clean_version, normalize_nombre


FIELD_COUNT = 5


@dataclass(frozen=True)
class ParseIssue:
    line_number: int
    message: str
    raw: str


@dataclass(frozen=True)
class PandaParseResult:
    rows: list[dict[str, Any]]
    errors: list[ParseIssue]
    raw_hash: str
    mode: str

    @property
    def ok(self) -> bool:
        return bool(self.rows) and not self.errors


def _clean_text(raw: Any) -> str | None:
    if raw is None:
        return None
    val = str(raw).strip()
    return val if val not in ("", "-", "–", "nan", "NaN", "None") else None


def _parse_date(raw: Any) -> date | None:
    val = _clean_text(raw)
    if val is None:
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    return None


def _is_header(values: list[str]) -> bool:
    joined = " ".join(normalize_nombre(v) for v in values)
    return "NOMBRE" in joined and ("EDITOR" in joined or "FABRICANTE" in joined) and "VERSION" in joined


def _row_to_program(values: list[str], line_number: int, raw: str) -> dict | None:
    nombre = _clean_text(values[0])
    if not nombre:
        return None
    fabricante = _clean_text(values[1])
    return {
        "row_number": line_number,
        "nombre": nombre,
        "nombre_norm": normalize_nombre(nombre),
        "fabricante": fabricante,
        "fabricante_norm": normalize_nombre(fabricante) if fabricante else None,
        "fecha_instalacion": _parse_date(values[2]),
        "tamano": _clean_text(values[3]),
        "version": clean_version(values[4]),
        "raw_line": raw,
    }


def _parse_tabbed(lines: list[tuple[int, str]]) -> tuple[list[dict], list[ParseIssue]]:
    rows: list[dict] = []
    errors: list[ParseIssue] = []
    first_data_seen = False
    for line_number, raw_line in lines:
        values = raw_line.split("\t")
        if not first_data_seen and _is_header(values):
            first_data_seen = True
            continue
        first_data_seen = True
        if len(values) != FIELD_COUNT:
            errors.append(ParseIssue(line_number, f"Se esperaban {FIELD_COUNT} columnas y llegaron {len(values)}.", raw_line))
            continue
        item = _row_to_program(values, line_number, raw_line)
        if item:
            rows.append(item)
    return rows, errors


def _parse_vertical(lines: list[tuple[int, str]]) -> tuple[list[dict], list[ParseIssue]]:
    rows: list[dict] = []
    errors: list[ParseIssue] = []
    values = [(line_number, raw_line.strip()) for line_number, raw_line in lines if raw_line.strip()]
    if len(values) % FIELD_COUNT != 0:
        errors.append(
            ParseIssue(
                values[-1][0] if values else 0,
                f"El pegado vertical debe traer bloques de {FIELD_COUNT} lineas: nombre, editor, fecha, tamano y version.",
                values[-1][1] if values else "",
            )
        )
    usable_count = len(values) - (len(values) % FIELD_COUNT)
    for offset in range(0, usable_count, FIELD_COUNT):
        block = values[offset : offset + FIELD_COUNT]
        raw_values = [item[1] for item in block]
        if offset == 0 and _is_header(raw_values):
            continue
        raw_line = "\t".join(raw_values)
        item = _row_to_program(raw_values, block[0][0], raw_line)
        if item:
            rows.append(item)
    return rows, errors


def parse_panda_text(text: str | None) -> PandaParseResult:
    raw_text = text or ""
    raw_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    lines = [(i, line.rstrip("\n")) for i, line in enumerate(raw_text.splitlines(), start=1) if line.strip()]
    if not lines:
        return PandaParseResult([], [ParseIssue(0, "No se detectaron programas.", "")], raw_hash, "empty")

    mode = "tabbed" if any("\t" in line for _, line in lines) else "vertical"
    if mode == "tabbed":
        rows, errors = _parse_tabbed(lines)
    else:
        rows, errors = _parse_vertical(lines)

    if not rows and not errors:
        errors.append(ParseIssue(0, "No se detectaron filas validas.", ""))
    return PandaParseResult(rows=rows, errors=errors, raw_hash=raw_hash, mode=mode)
