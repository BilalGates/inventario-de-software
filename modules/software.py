from __future__ import annotations

import re
from datetime import date
from typing import Any

from sqlalchemy import text


REVISION_FIELDS = {
    "fabricante",
    "version_referencia",
    "clasificacion_informacion",
    "en_guia_105",
    "observaciones_elena",
    "observaciones_toni",
    "fecha_ultima_actualizacion",
}


def _has_active_device_sql() -> str:
    return """
        EXISTS (
            SELECT 1
            FROM software_equipo swe_present
            JOIN equipos e_present ON e_present.id = swe_present.equipo_id
            WHERE swe_present.software_id = s.id
              AND swe_present.presente = TRUE
              AND e_present.activo = TRUE
        )
    """


def listar_departamentos(db) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT id, codigo, nombre, prefijo_id
            FROM departamentos
            ORDER BY id
            """
        )
    ).mappings().all()
    return [dict(row) for row in rows]


def obtener_departamento(db, departamento_id: int) -> dict | None:
    row = db.execute(
        text("SELECT id, codigo, nombre, prefijo_id FROM departamentos WHERE id = :id"),
        {"id": departamento_id},
    ).mappings().first()
    return dict(row) if row else None


def obtener_departamento_por_codigo(db, codigo: str) -> dict | None:
    row = db.execute(
        text("SELECT id, codigo, nombre, prefijo_id FROM departamentos WHERE codigo = :codigo"),
        {"codigo": codigo},
    ).mappings().first()
    return dict(row) if row else None


def listar_departamentos_con_estadisticas(db) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT
                d.id,
                d.codigo,
                d.nombre,
                d.prefijo_id,
                COALESCE(eq.n_equipos, 0) AS n_equipos,
                COALESCE(sw.n_software, 0) AS n_software
            FROM departamentos d
            LEFT JOIN (
                SELECT departamento_id, COUNT(*) AS n_equipos
                FROM equipos
                WHERE activo = TRUE
                GROUP BY departamento_id
            ) eq ON eq.departamento_id = d.id
            LEFT JOIN (
                SELECT departamento_id, COUNT(*) AS n_software
                FROM software s
                WHERE activo = TRUE
                  AND EXISTS (
                      SELECT 1
                      FROM software_equipo swe_present
                      WHERE swe_present.software_id = s.id
                        AND swe_present.presente = TRUE
                  )
                GROUP BY departamento_id
            ) sw ON sw.departamento_id = d.id
            ORDER BY d.id
            """
        )
    ).mappings().all()
    return [dict(row) for row in rows]


def generar_codigo_software(db, departamento_id: int) -> str:
    dept = obtener_departamento(db, departamento_id)
    if not dept:
        raise ValueError("Departamento no encontrado")
    prefix = dept["prefijo_id"]
    # FOR UPDATE bloquea las filas hasta que la transaccion termine.
    rows = db.execute(
        text(
            """
            SELECT codigo
            FROM software
            WHERE departamento_id = :departamento_id
              AND codigo LIKE :like_prefix
            FOR UPDATE
            """
        ),
        {"departamento_id": departamento_id, "like_prefix": f"{prefix}-%"},
    ).scalars().all()
    max_num = 0
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    for codigo in rows:
        match = pattern.match(codigo or "")
        if match:
            max_num = max(max_num, int(match.group(1)))
    return f"{prefix}-{max_num + 1:03d}"


def _guia_filter_sql(en_guia_105: bool | None | str, where: list[str], params: dict[str, Any]) -> None:
    if en_guia_105 == "todos":
        return
    if en_guia_105 is None:
        where.append("s.en_guia_105 IS NULL")
    else:
        where.append("s.en_guia_105 = :en_guia_105")
        params["en_guia_105"] = en_guia_105


def listar_inventario(
    db,
    departamento_id: int,
    equipo_ids: list[int] | None = None,
    en_guia_105: bool | None | str = "todos",
    texto_libre: str | None = None,
) -> list[dict]:
    where = ["s.departamento_id = :departamento_id", "s.activo = TRUE", _has_active_device_sql()]
    params: dict[str, Any] = {"departamento_id": departamento_id}
    _guia_filter_sql(en_guia_105, where, params)

    if texto_libre:
        where.append("s.nombre LIKE :texto")
        params["texto"] = f"%{texto_libre.strip()}%"
    if equipo_ids:
        placeholders = []
        for idx, equipo_id in enumerate(equipo_ids):
            key = f"equipo_id_{idx}"
            placeholders.append(f":{key}")
            params[key] = equipo_id
        where.append(
            f"""
            EXISTS (
                SELECT 1
                FROM software_equipo swe_filter
                JOIN equipos e_filter ON e_filter.id = swe_filter.equipo_id
                WHERE swe_filter.software_id = s.id
                  AND swe_filter.presente = TRUE
                  AND e_filter.activo = TRUE
                  AND swe_filter.equipo_id IN ({', '.join(placeholders)})
            )
            """
        )

    rows = db.execute(
        text(
            f"""
            SELECT
                s.id,
                s.departamento_id,
                s.codigo,
                s.nombre,
                s.nombre_norm,
                s.fabricante,
                s.version_referencia,
                s.clasificacion_informacion,
                s.en_guia_105,
                s.observaciones_elena,
                s.observaciones_toni,
                TRIM(BOTH '\n' FROM CONCAT_WS('\n', NULLIF(s.observaciones_elena, ''), NULLIF(s.observaciones_toni, ''))) AS observaciones,
                COALESCE(s.fecha_ultima_actualizacion, MAX(swe.fecha_ultima_deteccion)) AS fecha_ultima_actualizacion,
                s.activo,
                s.fecha_alta,
                GROUP_CONCAT(DISTINCT e.nombre ORDER BY e.nombre SEPARATOR ', ') AS dispositivos
            FROM software s
            LEFT JOIN software_equipo swe
                ON swe.software_id = s.id
               AND swe.presente = TRUE
            LEFT JOIN equipos e
                ON e.id = swe.equipo_id
               AND e.activo = TRUE
            WHERE {' AND '.join(where)}
            GROUP BY s.id
            ORDER BY s.codigo IS NULL, s.codigo, s.nombre
            """
        ),
        params,
    ).mappings().all()
    return [dict(row) for row in rows]


def listar_inventario_empresa(
    db,
    departamento_ids: list[int] | None = None,
    equipo_ids: list[int] | None = None,
    solo_comun: bool = False,
    texto_libre: str | None = None,
) -> list[dict]:
    where = ["s.activo = TRUE", _has_active_device_sql()]
    params: dict[str, Any] = {}

    if departamento_ids:
        placeholders = []
        for idx, departamento_id in enumerate(departamento_ids):
            key = f"departamento_id_{idx}"
            placeholders.append(f":{key}")
            params[key] = departamento_id
        where.append(f"s.departamento_id IN ({', '.join(placeholders)})")
    if equipo_ids:
        placeholders = []
        for idx, equipo_id in enumerate(equipo_ids):
            key = f"equipo_id_{idx}"
            placeholders.append(f":{key}")
            params[key] = equipo_id
        where.append(
            f"""
            EXISTS (
                SELECT 1
                FROM software_equipo swe_filter
                JOIN equipos e_filter ON e_filter.id = swe_filter.equipo_id
                WHERE swe_filter.software_id = s.id
                  AND swe_filter.presente = TRUE
                  AND e_filter.activo = TRUE
                  AND swe_filter.equipo_id IN ({', '.join(placeholders)})
            )
            """
        )
    if texto_libre:
        where.append(
            """
            (
                s.nombre LIKE :texto
                OR COALESCE(s.fabricante, '') LIKE :texto
                OR COALESCE(s.version_referencia, '') LIKE :texto
                OR EXISTS (
                    SELECT 1
                    FROM software_equipo swe_search
                    JOIN equipos e_search ON e_search.id = swe_search.equipo_id
                    WHERE swe_search.software_id = s.id
                      AND swe_search.presente = TRUE
                      AND e_search.activo = TRUE
                      AND e_search.nombre LIKE :texto
                )
            )
            """
        )
        params["texto"] = f"%{texto_libre.strip()}%"

    having = "HAVING COUNT(DISTINCT s.departamento_id) >= 2" if solo_comun else ""
    rows = db.execute(
        text(
            f"""
            SELECT
                MIN(s.id) AS id,
                s.nombre_norm,
                MIN(s.nombre) AS nombre,
                GROUP_CONCAT(DISTINCT s.fabricante ORDER BY s.fabricante SEPARATOR ', ') AS fabricantes,
                GROUP_CONCAT(DISTINCT s.version_referencia ORDER BY s.version_referencia SEPARATOR ', ') AS versiones,
                GROUP_CONCAT(DISTINCT d.nombre ORDER BY d.nombre SEPARATOR ', ') AS departamentos,
                GROUP_CONCAT(DISTINCT e.nombre ORDER BY e.nombre SEPARATOR ', ') AS dispositivos,
                GROUP_CONCAT(DISTINCT s.clasificacion_informacion ORDER BY s.clasificacion_informacion SEPARATOR ', ') AS clasificaciones,
                CASE
                    WHEN SUM(s.en_guia_105 = TRUE) > 0 THEN TRUE
                    WHEN SUM(s.en_guia_105 = FALSE) > 0 THEN FALSE
                    ELSE NULL
                END AS en_guia_105,
                GROUP_CONCAT(DISTINCT s.observaciones_elena ORDER BY s.observaciones_elena SEPARATOR ' | ') AS observaciones_elena,
                GROUP_CONCAT(DISTINCT s.observaciones_toni ORDER BY s.observaciones_toni SEPARATOR ' | ') AS observaciones_toni,
                TRIM(BOTH '\n' FROM CONCAT_WS('\n', NULLIF(GROUP_CONCAT(DISTINCT s.observaciones_elena ORDER BY s.observaciones_elena SEPARATOR ' | '), ''), NULLIF(GROUP_CONCAT(DISTINCT s.observaciones_toni ORDER BY s.observaciones_toni SEPARATOR ' | '), ''))) AS observaciones,
                MAX(COALESCE(s.fecha_ultima_actualizacion, swe.fecha_ultima_deteccion)) AS fecha_ultima_actualizacion,
                COUNT(DISTINCT s.departamento_id) AS n_departamentos
            FROM software s
            JOIN departamentos d ON d.id = s.departamento_id
            LEFT JOIN software_equipo swe
                ON swe.software_id = s.id
               AND swe.presente = TRUE
            LEFT JOIN equipos e ON e.id = swe.equipo_id
              AND e.activo = TRUE
            WHERE {' AND '.join(where)}
            GROUP BY s.nombre_norm
            {having}
            ORDER BY n_departamentos DESC, nombre
            """
        ),
        params,
    ).mappings().all()
    return [dict(row) for row in rows]


def actualizar_software_revision(db, software_id: int, values: dict) -> None:
    filtered = {key: value for key, value in values.items() if key in REVISION_FIELDS}
    filtered["fecha_ultima_actualizacion"] = filtered.get("fecha_ultima_actualizacion") or date.today()
    if not filtered:
        return
    assignments = ", ".join(f"{key} = :{key}" for key in filtered)
    filtered["software_id"] = software_id
    db.execute(
        text(f"UPDATE software SET {assignments} WHERE id = :software_id"),
        filtered,
    )


def eliminar_software_inventario(db, software_id: int) -> None:
    db.execute(
        text(
            """
            UPDATE software
            SET activo = FALSE
            WHERE id = :software_id
            """
        ),
        {"software_id": software_id},
    )


def ocultar_software_sin_dispositivos(db, departamento_id: int | None = None) -> int:
    where = ["s.activo = TRUE", f"NOT {_has_active_device_sql()}"]
    params: dict[str, Any] = {}
    if departamento_id is not None:
        where.append("s.departamento_id = :departamento_id")
        params["departamento_id"] = departamento_id
    result = db.execute(
        text(
            f"""
            UPDATE software s
            SET s.activo = FALSE
            WHERE {' AND '.join(where)}
            """
        ),
        params,
    )
    return int(result.rowcount or 0)


def contar_software_sin_dispositivos(db) -> list[dict]:
    rows = db.execute(
        text(
            f"""
            SELECT d.id AS departamento_id, d.nombre AS departamento, COUNT(*) AS total
            FROM software s
            JOIN departamentos d ON d.id = s.departamento_id
            WHERE s.activo = TRUE
              AND NOT {_has_active_device_sql()}
            GROUP BY d.id, d.nombre
            ORDER BY d.nombre
            """
        )
    ).mappings().all()
    return [dict(row) for row in rows]


def dashboard_metricas(db) -> dict:
    return {
        "equipos_activos": int(db.execute(text("SELECT COUNT(*) FROM equipos WHERE activo = TRUE")).scalar() or 0),
        "software_activo": int(db.execute(text("SELECT COUNT(*) FROM software WHERE activo = TRUE")).scalar() or 0),
        "importaciones_mes": int(
            db.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM importaciones
                    WHERE YEAR(fecha_importacion) = YEAR(CURRENT_DATE)
                      AND MONTH(fecha_importacion) = MONTH(CURRENT_DATE)
                      AND confirmada = TRUE
                    """
                )
            ).scalar()
            or 0
        ),
        "software_sin_dispositivo": int(
            db.execute(
                text(
                    f"""
                    SELECT COUNT(*)
                    FROM software s
                    WHERE s.activo = TRUE
                      AND NOT {_has_active_device_sql()}
                    """
                )
            ).scalar()
            or 0
        ),
        "autorizado_pendiente_promocion": int(
            db.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM software_autorizado sa
                    WHERE COALESCE(sa.activo, TRUE) = TRUE
                      AND sa.software_id IS NOT NULL
                      AND (
                          (
                              SELECT COUNT(DISTINCT swe_chk.equipo_id)
                              FROM software_equipo swe_chk
                              JOIN equipos e_chk ON e_chk.id = swe_chk.equipo_id
                              WHERE swe_chk.software_id = sa.software_id
                                AND swe_chk.presente = TRUE
                                AND e_chk.activo = TRUE
                          ) >= 2
                          OR EXISTS (
                              SELECT 1
                              FROM software_equipo swe
                              JOIN equipos e ON e.id = swe.equipo_id
                              WHERE swe.software_id = sa.software_id
                                AND swe.presente = TRUE
                                AND e.activo = TRUE
                                AND COALESCE(swe.fecha_instalacion, swe.fecha_ultima_deteccion)
                                    <= DATE_SUB(CURRENT_DATE, INTERVAL 90 DAY)
                          )
                      )
                    """
                )
            ).scalar()
            or 0
        ),
    }


def estado_departamentos(db) -> list[dict]:
    rows = db.execute(
        text(
            f"""
            SELECT
                d.id,
                d.nombre AS departamento,
                COALESCE(eq.equipos_activos, 0) AS equipos_activos,
                COALESCE(sw.software_visible, 0) AS software_visible,
                imp.ultima_importacion
            FROM departamentos d
            LEFT JOIN (
                SELECT departamento_id, COUNT(*) AS equipos_activos
                FROM equipos
                WHERE activo = TRUE
                GROUP BY departamento_id
            ) eq ON eq.departamento_id = d.id
            LEFT JOIN (
                SELECT s.departamento_id, COUNT(*) AS software_visible
                FROM software s
                WHERE s.activo = TRUE
                  AND {_has_active_device_sql()}
                GROUP BY s.departamento_id
            ) sw ON sw.departamento_id = d.id
            LEFT JOIN (
                SELECT e.departamento_id, MAX(i.fecha_importacion) AS ultima_importacion
                FROM importaciones i
                JOIN equipos e ON e.id = i.equipo_id
                WHERE i.confirmada = TRUE
                GROUP BY e.departamento_id
            ) imp ON imp.departamento_id = d.id
            ORDER BY d.id
            """
        )
    ).mappings().all()
    return [dict(row) for row in rows]


def versiones_sospechosas(db) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT id, nombre, version_referencia, fabricante
            FROM software
            WHERE activo = TRUE
              AND (
                  version_referencia IS NULL
                  OR CHAR_LENGTH(version_referencia) < 2
                  OR CHAR_LENGTH(version_referencia) > 50
                  OR version_referencia REGEXP '[^0-9A-Za-z ._()+/:;,-]'
              )
            ORDER BY nombre
            """
        )
    ).mappings().all()
    return [dict(row) for row in rows]


def fabricantes_vacios(db) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT id, nombre, version_referencia, fabricante
            FROM software
            WHERE activo = TRUE
              AND (fabricante IS NULL OR fabricante = '')
            ORDER BY nombre
            """
        )
    ).mappings().all()
    return [dict(row) for row in rows]


def actualizar_fabricante(db, software_id: int, fabricante: str | None) -> None:
    db.execute(
        text("UPDATE software SET fabricante = :fabricante WHERE id = :software_id"),
        {"software_id": software_id, "fabricante": fabricante or None},
    )


def software_comun_no_autorizado(db) -> list[dict]:
    rows = db.execute(
        text(
            f"""
            SELECT
                MIN(s.id) AS software_id,
                MIN(s.nombre) AS nombre,
                COUNT(DISTINCT s.departamento_id) AS n_departamentos
            FROM software s
            WHERE s.activo = TRUE
              AND {_has_active_device_sql()}
              AND NOT EXISTS (
                  SELECT 1
                  FROM software_autorizado sa
                  JOIN software s_auth ON s_auth.id = sa.software_id
                  WHERE s_auth.nombre_norm = s.nombre_norm
                    AND COALESCE(sa.activo, TRUE) = TRUE
              )
            GROUP BY s.nombre_norm
            HAVING COUNT(DISTINCT s.departamento_id) > 3
            ORDER BY n_departamentos DESC, nombre
            """
        )
    ).mappings().all()
    return [dict(row) for row in rows]
