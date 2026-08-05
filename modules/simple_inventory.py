from __future__ import annotations

import re
from datetime import date
from io import BytesIO
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from sqlalchemy import text

from utils.panda_parser import parse_panda_text


PERIODO_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def current_period(today: date | None = None) -> str:
    value = today or date.today()
    return f"{value.year:04d}-{value.month:02d}"


def validate_periodo(periodo: str) -> str:
    value = str(periodo or "").strip()
    if not PERIODO_RE.fullmatch(value):
        raise ValueError("El periodo debe tener formato YYYY-MM.")
    return value


def _engine():
    from database.connection import get_engine

    return get_engine()


def confirm_software_import(equipo_id: int, periodo: str, rows: list[dict], raw_text: str, db=None) -> int:
    if db is None:
        with _engine().begin() as conn:
            return confirm_software_import(equipo_id, periodo, rows, raw_text, db=conn)
    periodo = validate_periodo(periodo)
    if not rows:
        raise ValueError("No hay programas validos para guardar.")

    equipo = db.execute(
        text(
            """
            SELECT id, departamento_id
            FROM equipos
            WHERE id = :equipo_id
              AND activo = TRUE
            """
        ),
        {"equipo_id": equipo_id},
    ).mappings().first()
    if not equipo:
        raise ValueError("Equipo activo no encontrado.")

    parsed = parse_panda_text(raw_text)
    departamento_id = int(equipo["departamento_id"])
    db.execute(
        text(
            """
            UPDATE software_importaciones
            SET estado = 'superseded'
            WHERE equipo_id = :equipo_id
              AND periodo = :periodo
              AND estado = 'confirmed'
            """
        ),
        {"equipo_id": equipo_id, "periodo": periodo},
    )
    result = db.execute(
        text(
            """
            INSERT INTO software_importaciones (
                equipo_id, departamento_id, periodo, fecha_importacion,
                raw_hash, raw_text, estado, n_programas, n_errores, origen
            )
            VALUES (
                :equipo_id, :departamento_id, :periodo, NOW(),
                :raw_hash, :raw_text, 'confirmed', :n_programas, 0, :origen
            )
            """
        ),
        {
            "equipo_id": equipo_id,
            "departamento_id": departamento_id,
            "periodo": periodo,
            "raw_hash": parsed.raw_hash,
            "raw_text": raw_text,
            "n_programas": len(rows),
            "origen": parsed.mode,
        },
    )
    importacion_id = int(result.lastrowid)
    for row in rows:
        db.execute(
            text(
                """
                INSERT INTO software_instalado (
                    importacion_id, equipo_id, departamento_id, periodo, source_row,
                    nombre, nombre_norm, fabricante, fabricante_norm,
                    fecha_instalacion, tamano, version, raw_line
                )
                VALUES (
                    :importacion_id, :equipo_id, :departamento_id, :periodo, :source_row,
                    :nombre, :nombre_norm, :fabricante, :fabricante_norm,
                    :fecha_instalacion, :tamano, :version, :raw_line
                )
                """
            ),
            {
                "importacion_id": importacion_id,
                "equipo_id": equipo_id,
                "departamento_id": departamento_id,
                "periodo": periodo,
                "source_row": row.get("row_number"),
                "nombre": row.get("nombre"),
                "nombre_norm": row.get("nombre_norm"),
                "fabricante": row.get("fabricante"),
                "fabricante_norm": row.get("fabricante_norm"),
                "fecha_instalacion": row.get("fecha_instalacion"),
                "tamano": row.get("tamano"),
                "version": row.get("version"),
                "raw_line": row.get("raw_line"),
            },
        )
    return importacion_id


def software_por_departamento(periodo: str, departamento_id: int, db=None) -> list[dict]:
    if db is None:
        with _engine().connect() as conn:
            return software_por_departamento(periodo, departamento_id, db=conn)
    periodo = validate_periodo(periodo)
    rows = db.execute(
        text(
            """
            SELECT
                MIN(si.nombre) AS nombre,
                si.nombre_norm,
                GROUP_CONCAT(DISTINCT NULLIF(si.fabricante, '') ORDER BY si.fabricante SEPARATOR ', ') AS fabricantes,
                GROUP_CONCAT(DISTINCT NULLIF(si.version, '') ORDER BY si.version SEPARATOR ', ') AS versiones,
                COUNT(DISTINCT si.equipo_id) AS n_equipos,
                GROUP_CONCAT(DISTINCT e.nombre ORDER BY e.nombre SEPARATOR ', ') AS equipos
            FROM software_instalado si
            JOIN software_importaciones imp ON imp.id = si.importacion_id
            JOIN equipos e ON e.id = si.equipo_id
            WHERE imp.estado = 'confirmed'
              AND imp.periodo = :periodo
              AND imp.departamento_id = :departamento_id
            GROUP BY si.nombre_norm
            ORDER BY n_equipos DESC, nombre
            """
        ),
        {"periodo": periodo, "departamento_id": departamento_id},
    ).mappings().all()
    return [dict(row) for row in rows]


def equipos_estado_mensual(periodo: str, departamento_id: int, db=None) -> list[dict]:
    if db is None:
        with _engine().connect() as conn:
            return equipos_estado_mensual(periodo, departamento_id, db=conn)
    periodo = validate_periodo(periodo)
    rows = db.execute(
        text(
            """
            SELECT
                e.id,
                e.nombre,
                e.notas AS usuario,
                e.activo,
                d.nombre AS departamento,
                imp.id AS importacion_id,
                imp.fecha_importacion,
                imp.n_programas
            FROM equipos e
            JOIN departamentos d ON d.id = e.departamento_id
            LEFT JOIN software_importaciones imp
              ON imp.equipo_id = e.id
             AND imp.periodo = :periodo
             AND imp.estado = 'confirmed'
            WHERE e.departamento_id = :departamento_id
              AND e.activo = TRUE
            ORDER BY imp.id IS NULL DESC, e.nombre
            """
        ),
        {"periodo": periodo, "departamento_id": departamento_id},
    ).mappings().all()
    result = []
    for row in rows:
        item = dict(row)
        item["estado_importacion"] = "Importado" if item.get("importacion_id") else "Pendiente"
        item["fecha_importacion_str"] = str(item.get("fecha_importacion") or "")[:19]
        item["n_programas"] = item.get("n_programas") or 0
        item["usuario"] = item.get("usuario") or ""
        result.append(item)
    return result


def dashboard_simple(periodo: str, db=None) -> dict:
    if db is None:
        with _engine().connect() as conn:
            return dashboard_simple(periodo, db=conn)
    periodo = validate_periodo(periodo)
    row = db.execute(
        text(
            """
            SELECT
                (SELECT COUNT(*) FROM equipos WHERE activo = TRUE) AS equipos,
                (SELECT COUNT(*) FROM departamentos) AS departamentos,
                (SELECT COUNT(*) FROM software_importaciones WHERE periodo = :periodo AND estado = 'confirmed') AS importaciones,
                (
                    SELECT COUNT(DISTINCT nombre_norm)
                    FROM software_instalado si
                    JOIN software_importaciones imp ON imp.id = si.importacion_id
                    WHERE imp.periodo = :periodo
                      AND imp.estado = 'confirmed'
                ) AS software
            """
        ),
        {"periodo": periodo},
    ).mappings().first()
    return dict(row) if row else {}


def resumen_departamentos(periodo: str, db=None) -> list[dict]:
    if db is None:
        with _engine().connect() as conn:
            return resumen_departamentos(periodo, db=conn)
    periodo = validate_periodo(periodo)
    rows = db.execute(
        text(
            """
            SELECT
                d.id,
                d.nombre,
                COALESCE(eq.total, 0) AS equipos,
                COALESCE(imp.total, 0) AS importados,
                COALESCE(sw.total, 0) AS software
            FROM departamentos d
            LEFT JOIN (
                SELECT departamento_id, COUNT(*) AS total
                FROM equipos
                WHERE activo = TRUE
                GROUP BY departamento_id
            ) eq ON eq.departamento_id = d.id
            LEFT JOIN (
                SELECT departamento_id, COUNT(*) AS total
                FROM software_importaciones
                WHERE periodo = :periodo AND estado = 'confirmed'
                GROUP BY departamento_id
            ) imp ON imp.departamento_id = d.id
            LEFT JOIN (
                SELECT imp.departamento_id, COUNT(DISTINCT si.nombre_norm) AS total
                FROM software_instalado si
                JOIN software_importaciones imp ON imp.id = si.importacion_id
                WHERE imp.periodo = :periodo AND imp.estado = 'confirmed'
                GROUP BY imp.departamento_id
            ) sw ON sw.departamento_id = d.id
            ORDER BY d.id
            """
        ),
        {"periodo": periodo},
    ).mappings().all()
    result = []
    for row in rows:
        item = dict(row)
        item["estado"] = f"{item['importados']} / {item['equipos']}"
        result.append(item)
    return result


def _cell_value(value: Any):
    if isinstance(value, bool):
        return "Si" if value else "No"
    return value


def _safe_sheet_name(name: str) -> str:
    invalid = "[]:*?/\\"
    cleaned = "".join("_" if c in invalid else c for c in str(name or "Hoja"))
    return cleaned[:31] or "Hoja"


def _write_rows(ws, headers: list[str], rows: list[list]) -> None:
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="366092")
    for row in rows:
        ws.append(row)
    for column in ws.columns:
        width = min(max(len(str(cell.value or "")) for cell in column) + 2, 70)
        ws.column_dimensions[column[0].column_letter].width = width
    ws.freeze_panes = "A2"


def exportar_inventario_excel(periodo: str, db=None) -> bytes:
    if db is None:
        with _engine().connect() as conn:
            return exportar_inventario_excel(periodo, db=conn)
    from modules.equipos import listar_equipos
    from modules.software import listar_departamentos

    periodo = validate_periodo(periodo)
    wb = Workbook()
    wb.remove(wb.active)

    equipos = listar_equipos(db, solo_activos=False)
    ws_eq = wb.create_sheet("Equipos")
    _write_rows(
        ws_eq,
        ["Departamento", "Equipo", "Usuario", "Activo"],
        [[e.get("departamento_nombre"), e.get("nombre"), e.get("notas"), _cell_value(e.get("activo"))] for e in equipos],
    )

    for dept in listar_departamentos(db):
        rows = software_por_departamento(periodo, dept["id"], db=db)
        ws = wb.create_sheet(_safe_sheet_name(dept["nombre"]))
        _write_rows(
            ws,
            ["Programa", "Editor/Fabricante", "Versiones", "N equipos", "Equipos"],
            [
                [
                    row.get("nombre"),
                    row.get("fabricantes"),
                    row.get("versiones"),
                    row.get("n_equipos"),
                    row.get("equipos"),
                ]
                for row in rows
            ],
        )

    output = BytesIO()
    wb.save(output)
    return output.getvalue()
