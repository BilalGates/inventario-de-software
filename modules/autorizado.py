from __future__ import annotations

from sqlalchemy import text


def listar_autorizado(db) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT
                sa.*,
                s.nombre AS software_nombre,
                d.nombre AS departamento_nombre,
                e.nombre AS equipo_nombre
            FROM software_autorizado sa
            LEFT JOIN software s ON s.id = sa.software_id
            LEFT JOIN departamentos d ON d.id = sa.departamento_id
            LEFT JOIN equipos e ON e.id = sa.equipo_id
            WHERE COALESCE(sa.activo, TRUE) = TRUE
            ORDER BY sa.fecha_alta DESC, sa.nombre ASC
            """
        )
    ).mappings().all()
    return [dict(row) for row in rows]


def listar_autorizado_agrupado(db) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT
                LOWER(TRIM(COALESCE(s.nombre, sa.nombre))) AS grupo,
                MIN(COALESCE(s.nombre, sa.nombre)) AS nombre,
                GROUP_CONCAT(DISTINCT NULLIF(COALESCE(s.fabricante, sa.fabricante), '') ORDER BY COALESCE(s.fabricante, sa.fabricante) SEPARATOR ', ') AS fabricantes,
                GROUP_CONCAT(DISTINCT NULLIF(COALESCE(sa.version, s.version_referencia), '') ORDER BY COALESCE(sa.version, s.version_referencia) SEPARATOR ', ') AS versiones,
                GROUP_CONCAT(DISTINCT COALESCE(d.nombre, 'Sin departamento') ORDER BY d.nombre SEPARATOR ', ') AS departamentos,
                GROUP_CONCAT(DISTINCT NULLIF(COALESCE(e.nombre, sa.usuario_texto), '') ORDER BY COALESCE(e.nombre, sa.usuario_texto) SEPARATOR ', ') AS equipos_usuarios,
                GROUP_CONCAT(DISTINCT NULLIF(sa.observaciones, '') ORDER BY sa.observaciones SEPARATOR ' | ') AS observaciones,
                MAX(COALESCE(sa.fecha_autorizacion, sa.fecha_alta)) AS fecha_reciente,
                COUNT(*) AS registros
            FROM software_autorizado sa
            LEFT JOIN software s ON s.id = sa.software_id
            LEFT JOIN departamentos d ON d.id = COALESCE(sa.departamento_id, s.departamento_id)
            LEFT JOIN equipos e ON e.id = sa.equipo_id AND e.activo = TRUE
            WHERE COALESCE(sa.activo, TRUE) = TRUE
            GROUP BY LOWER(TRIM(COALESCE(s.nombre, sa.nombre)))
            ORDER BY nombre
            """
        )
    ).mappings().all()
    return [dict(row) for row in rows]


def listar_autorizado_detalle_grupo(db, grupo: str) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT
                sa.*,
                COALESCE(s.nombre, sa.nombre) AS nombre_visible,
                COALESCE(s.fabricante, sa.fabricante) AS fabricante_visible,
                COALESCE(sa.version, s.version_referencia) AS version_visible,
                d.nombre AS departamento_nombre,
                e.nombre AS equipo_nombre
            FROM software_autorizado sa
            LEFT JOIN software s ON s.id = sa.software_id
            LEFT JOIN departamentos d ON d.id = COALESCE(sa.departamento_id, s.departamento_id)
            LEFT JOIN equipos e ON e.id = sa.equipo_id AND e.activo = TRUE
            WHERE COALESCE(sa.activo, TRUE) = TRUE
              AND LOWER(TRIM(COALESCE(s.nombre, sa.nombre))) = :grupo
            ORDER BY departamento_nombre, nombre_visible, version_visible
            """
        ),
        {"grupo": grupo},
    ).mappings().all()
    return [dict(row) for row in rows]


def crear_autorizado(db, values: dict) -> int:
    result = db.execute(
        text(
            """
            INSERT INTO software_autorizado (
                software_id, departamento_id, nombre, fabricante, tipo, version,
                equipo_id, usuario_texto, observaciones, motivo, fecha_autorizacion, activo
            )
            VALUES (
                :software_id, :departamento_id, :nombre, :fabricante, :tipo, :version,
                :equipo_id, :usuario_texto, :observaciones, :motivo, COALESCE(:fecha_autorizacion, NOW()), TRUE
            )
            """
        ),
        {
            "software_id": values.get("software_id"),
            "departamento_id": values.get("departamento_id"),
            "nombre": values["nombre"],
            "fabricante": values.get("fabricante"),
            "tipo": values.get("tipo"),
            "version": values.get("version"),
            "equipo_id": values.get("equipo_id"),
            "usuario_texto": values.get("usuario_texto"),
            "observaciones": values.get("observaciones"),
            "motivo": values.get("motivo"),
            "fecha_autorizacion": values.get("fecha_autorizacion"),
        },
    )
    return int(result.lastrowid)


def eliminar_autorizado(db, autorizado_id: int) -> None:
    db.execute(
        text("UPDATE software_autorizado SET activo = FALSE WHERE id = :id"),
        {"id": autorizado_id},
    )


def actualizar_autorizado(db, autorizado_id: int, values: dict) -> None:
    allowed = {"nombre", "fabricante", "tipo", "version", "observaciones"}
    filtered = {key: value for key, value in values.items() if key in allowed}
    if not filtered:
        return
    assignments = ", ".join(f"{key} = :{key}" for key in filtered)
    filtered["id"] = autorizado_id
    db.execute(text(f"UPDATE software_autorizado SET {assignments} WHERE id = :id"), filtered)


def eliminar_autorizado_grupo(db, grupo: str) -> int:
    result = db.execute(
        text(
            """
            UPDATE software_autorizado sa
            LEFT JOIN software s ON s.id = sa.software_id
            SET sa.activo = FALSE
            WHERE COALESCE(sa.activo, TRUE) = TRUE
              AND LOWER(TRIM(COALESCE(s.nombre, sa.nombre))) = :grupo
            """
        ),
        {"grupo": grupo},
    )
    return int(result.rowcount or 0)


def detectar_software_exclusivo(db, departamento_id: int | None = None) -> list[dict]:
    where = ["s.activo = TRUE"]
    params = {}
    if departamento_id is not None:
        where.append("s.departamento_id = :departamento_id")
        params["departamento_id"] = departamento_id
    rows = db.execute(
        text(
            f"""
            SELECT
                s.id,
                s.nombre,
                s.version_referencia,
                s.fabricante,
                MIN(e.nombre) AS equipo
            FROM software s
            JOIN software_equipo swe
              ON swe.software_id = s.id
             AND swe.presente = TRUE
            JOIN equipos e ON e.id = swe.equipo_id
            WHERE {' AND '.join(where)}
              AND NOT EXISTS (
                  SELECT 1
                  FROM software_autorizado sa
                  WHERE sa.software_id = s.id
                    AND COALESCE(sa.activo, TRUE) = TRUE
              )
            GROUP BY s.id, s.nombre, s.version_referencia, s.fabricante
            HAVING COUNT(DISTINCT swe.equipo_id) = 1
            ORDER BY s.nombre
            """
        ),
        params,
    ).mappings().all()
    return [dict(row) for row in rows]


def autorizar_softwares(db, software_ids: list[int], motivo: str) -> int:
    if not software_ids:
        return 0
    inserted = 0
    for software_id in software_ids:
        result = db.execute(
            text(
                """
                INSERT INTO software_autorizado (
                    software_id, departamento_id, nombre, fabricante, version,
                    equipo_id, motivo, fecha_autorizacion, activo
                )
                SELECT
                    s.id,
                    s.departamento_id,
                    s.nombre,
                    s.fabricante,
                    s.version_referencia,
                    MIN(swe.equipo_id),
                    :motivo,
                    NOW(),
                    TRUE
                FROM software s
                LEFT JOIN software_equipo swe
                  ON swe.software_id = s.id
                 AND swe.presente = TRUE
                WHERE s.id = :software_id
                  AND NOT EXISTS (
                      SELECT 1
                      FROM software_autorizado sa
                      WHERE sa.software_id = s.id
                        AND COALESCE(sa.activo, TRUE) = TRUE
                  )
                GROUP BY s.id, s.departamento_id, s.nombre, s.fabricante, s.version_referencia
                """
            ),
            {"software_id": software_id, "motivo": motivo},
        )
        inserted += int(result.rowcount or 0)
    return inserted


def autorizar_exclusivos_automaticamente(db, departamento_id: int | None = None) -> int:
    candidatos = detectar_software_exclusivo(db, departamento_id)
    return autorizar_softwares(
        db,
        [item["id"] for item in candidatos],
        "Detectado automaticamente: instalado en un unico dispositivo",
    )


def detectar_autorizados_para_promocion(
    db,
    departamento_id: int | None = None,
    min_equipos: int = 3,
) -> list[dict]:
    where = ["s.activo = TRUE", "sa.id IS NOT NULL", "sa.equipo_id IS NOT NULL"]
    params = {"min_equipos": min_equipos}
    if departamento_id is not None:
        where.append("s.departamento_id = :departamento_id")
        params["departamento_id"] = departamento_id
    rows = db.execute(
        text(
            f"""
            SELECT
                s.id,
                s.nombre,
                s.version_referencia,
                s.fabricante,
                d.nombre AS departamento,
                COUNT(DISTINCT swe.equipo_id) AS n_equipos,
                GROUP_CONCAT(DISTINCT e.nombre ORDER BY e.nombre SEPARATOR ', ') AS equipos
            FROM software s
            JOIN departamentos d ON d.id = s.departamento_id
            JOIN software_autorizado sa
              ON sa.software_id = s.id
             AND COALESCE(sa.activo, TRUE) = TRUE
            JOIN software_equipo swe
              ON swe.software_id = s.id
             AND swe.presente = TRUE
            JOIN equipos e
              ON e.id = swe.equipo_id
             AND e.activo = TRUE
            WHERE {' AND '.join(where)}
              AND NOT EXISTS (
                  SELECT 1
                  FROM software_autorizado sa_general
                  WHERE sa_general.software_id = s.id
                    AND sa_general.equipo_id IS NULL
                    AND sa_general.usuario_texto IS NULL
                    AND COALESCE(sa_general.activo, TRUE) = TRUE
              )
            GROUP BY s.id, s.nombre, s.version_referencia, s.fabricante, d.nombre
            HAVING COUNT(DISTINCT swe.equipo_id) >= :min_equipos
            ORDER BY n_equipos DESC, s.nombre
            """
        ),
        params,
    ).mappings().all()
    return [dict(row) for row in rows]


def promocionar_autorizaciones_generales(db, software_ids: list[int], motivo: str) -> int:
    if not software_ids:
        return 0
    updated = 0
    for software_id in software_ids:
        result = db.execute(
            text(
                """
                UPDATE software_autorizado
                SET equipo_id = NULL,
                    usuario_texto = NULL,
                    motivo = :motivo,
                    fecha_autorizacion = NOW()
                WHERE software_id = :software_id
                  AND COALESCE(activo, TRUE) = TRUE
                """
            ),
            {"software_id": software_id, "motivo": motivo},
        )
        updated += int(result.rowcount or 0)
    return updated
