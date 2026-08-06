from __future__ import annotations

import hashlib
import re
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


_DATE_RE = re.compile(r"^\d{1,2}[/-]\d{1,2}[/-]\d{4}$")
_SIZE_RE = re.compile(r"^\d[\d.,]*\s*(KB|MB|GB|TB)$", re.IGNORECASE)
_VERSION_RE = re.compile(r"^\d+(\.\d+)+.*$")
# Algunos drivers traen la version como "11/14/2019 1.0.2.9": fecha,
# espacio y numero de version.
_DATED_VERSION_RE = re.compile(r"^\d{1,2}[/-]\d{1,2}[/-]\d{4}\s+\d+(\.\d+)+.*$")


_NOISE_TOKENS = {"-", "–", "—", "|", "·", ""}


def _is_date_token(val: str) -> bool:
    return bool(_DATE_RE.match(val.strip()))


def _is_noise_token(val: str) -> bool:
    """Separadores y celdas vacias que deja un pegado con formato."""
    return val.strip() in _NOISE_TOKENS


def _is_size_token(val: str) -> bool:
    val = val.strip()
    return val in ("-", "–") or bool(_SIZE_RE.match(val))


def _is_version_token(val: str) -> bool:
    val = val.strip()
    return val in ("-", "–") or bool(_VERSION_RE.match(val)) or bool(_DATED_VERSION_RE.match(val))


def _parse_loose(lines: list[tuple[int, str]]) -> tuple[list[dict], list[ParseIssue]]:
    """
    Reconstruye filas de un pegado que perdio los tabuladores y en el que
    algunos campos (tamano, version) pueden faltar por completo.

    En vez de exigir bloques de FIELD_COUNT lineas, usa la fecha de
    instalacion como ancla: nombre y editor son lo que hay antes de la
    fecha, y tamano/version lo que hay despues (cada uno opcional, se
    reconoce por su forma).
    """
    values = [(n, raw.strip()) for n, raw in lines if raw.strip()]
    if values and _is_header([v for _, v in values[:FIELD_COUNT]]):
        values = values[FIELD_COUNT:]

    # Solo anclamos en fechas que ocupan la linea entera. Una fecha dentro
    # de otro texto (p.ej. la version "11/14/2019 1.0.2.9" de los Windows
    # Driver Package) no separa filas.
    date_positions = [i for i, (_, val) in enumerate(values) if _is_date_token(val)]
    if not date_positions:
        return [], [ParseIssue(values[0][0] if values else 0, "No se detectaron fechas de instalacion para separar las filas.", "")]

    rows: list[dict] = []
    errors: list[ParseIssue] = []
    start = 0
    for idx, date_pos in enumerate(date_positions):
        next_date = date_positions[idx + 1] if idx + 1 < len(date_positions) else len(values)
        # Los separadores ("-", "|", celdas vacias) que deja un pegado con
        # formato no forman parte ni del nombre ni del editor.
        head = [(n, v) for n, v in values[start:date_pos] if not _is_noise_token(v)]
        tail = values[date_pos + 1 : next_date]

        if not head:
            errors.append(
                ParseIssue(
                    values[date_pos][0],
                    "Falta el nombre o el editor antes de la fecha de instalacion.",
                    " | ".join(v for _, v in values[start:date_pos]) or values[date_pos][1],
                )
            )
            start = next_date
            continue

        # El editor es la ultima linea antes de la fecha; el nombre puede
        # haberse partido en varias lineas y se vuelve a unir. Si solo hay
        # una linea, es el nombre y el editor queda desconocido.
        if len(head) == 1:
            nombre = head[0][1]
            editor = ""
        else:
            nombre = " ".join(v for _, v in head[:-1])
            editor = head[-1][1]

        # tail lleva, en orden, un tamano opcional y una version opcional.
        tamano = ""
        version = ""
        rest = [v for _, v in tail]
        if rest and _is_size_token(rest[0]):
            tamano = rest.pop(0)
        if rest and _is_version_token(rest[0]):
            version = rest.pop(0)
        if rest:
            # Sobra texto que no encaja: el siguiente nombre empezo aqui.
            # Lo devolvemos al inicio de la fila siguiente.
            next_date = next_date - len(rest)

        raw_values = [nombre, editor, values[date_pos][1], tamano, version]
        item = _row_to_program(raw_values, head[0][0], "\t".join(raw_values))
        if item:
            rows.append(item)
        start = next_date

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

    if any("\t" in line for _, line in lines):
        mode = "tabbed"
        rows, errors = _parse_tabbed(lines)
    elif len([1 for _, line in lines if line.strip()]) % FIELD_COUNT == 0:
        mode = "vertical"
        rows, errors = _parse_vertical(lines)
        if errors:
            # Cuadraba el multiplo por casualidad pero los bloques no eran
            # coherentes: reintentamos anclando por fecha.
            loose_rows, loose_errors = _parse_loose(lines)
            if loose_rows and len(loose_errors) < len(errors):
                mode, rows, errors = "loose", loose_rows, loose_errors
    else:
        mode = "loose"
        rows, errors = _parse_loose(lines)

    if not rows and not errors:
        errors.append(ParseIssue(0, "No se detectaron filas validas.", ""))
    return PandaParseResult(rows=rows, errors=errors, raw_hash=raw_hash, mode=mode)
