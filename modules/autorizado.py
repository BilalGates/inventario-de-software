from __future__ import annotations

import re

from sqlalchemy import text


_VERSION_TOKEN_RE = re.compile(
    r"""
    (?:
        v?\d+(?:\.\d+){1,5}[A-Za-z0-9.-]*
        |
        20\d{2}(?:\.\d+){1,4}
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)
_PAREN_RE = re.compile(r"\(([^()]*)\)")


def _clean_join(values: set[str], separator: str = ", ") -> str | None:
    cleaned = sorted({str(value).strip() for value in values if str(value or "").strip()}, key=str.casefold)
    return separator.join(cleaned) if cleaned else None


def _normalizar_autorizado_nombre(nombre: str | None) -> tuple[str, str, list[str]]:
    raw = str(nombre or "").strip()
    if not raw:
        return "", "", []

    versiones: list[str] = []

    def remove_parenthetical(match: re.Match) -> str:
        content = match.group(1).strip()
        if _VERSION_TOKEN_RE.fullmatch(content):
            versiones.append(content)
            return " "
        return match.group(0)

    base = _PAREN_RE.sub(remove_parenthetical, raw)

    while True:
        match = re.search(rf"(?:\s+|^)(?P<version>{_VERSION_TOKEN_RE.pattern})\s*$", base, re.IGNORECASE | re.VERBOSE)
        if not match:
            break
        versiones.append(match.group("version").strip())
        base = base[: match.start()].strip()

    base = re.sub(r"\s+", " ", base).strip(" -_.,")
    if not base:
        base = raw
    grupo = base.casefold()
    return grupo, base, versiones


def _listar_autorizado_rows(db) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT
                sa.*,
                COALESCE(s.nombre, sa.nombre) AS nombre_visible,
                COALESCE(s.fabricante, sa.fabricante) AS fabricante_visible,
                COALESCE(sa.version, s.version_referencia) AS version_visible,
                d.nombre AS departamento_nombre,
                e.id AS equipo_activo_id,
                e.nombre AS equipo_nombre
            FROM software_autorizado sa
            LEFT JOIN software s ON s.id = sa.software_id
            LEFT JOIN departamentos d ON d.id = COALESCE(sa.departamento_id, s.departamento_id)
            LEFT JOIN equipos e ON e.id = sa.equipo_id AND e.activo = TRUE
            WHERE COALESCE(sa.activo, TRUE) = TRUE
              AND (
                  sa.software_id IS NULL
                  OR (
                      SELECT COUNT(DISTINCT swe_chk.equipo_id)
                      FROM software_equipo swe_chk
                      JOIN equipos e_chk ON e_chk.id = swe_chk.equipo_id
                      WHERE swe_chk.software_id = sa.software_id
                        AND swe_chk.presente = TRUE
                        AND e_chk.activo = TRUE
                  ) < 2
              )
            ORDER BY departamento_nombre, nombre_visible, version_visible
            """
        )
    ).mappings().all()
    return [dict(row) for row in rows]


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
    grupos: dict[str, dict] = {}
    for row in _listar_autorizado_rows(db):
        grupo, nombre_base, versiones_nombre = _normalizar_autorizado_nombre(row.get("nombre_visible"))
        if not grupo:
            continue
        item = grupos.setdefault(
            grupo,
            {
                "grupo": grupo,
                "nombres": set(),
                "fabricantes_set": set(),
                "versiones_set": set(),
                "departamentos_set": set(),
                "equipos_usuarios_set": set(),
                "observaciones_set": set(),
                "fecha_reciente": None,
                "equipo_ids": set(),
                "usuario_texto_ids": set(),
                "registros": 0,
            },
        )
        item["nombres"].add(nombre_base)
        item["fabricantes_set"].add(row.get("fabricante_visible"))
        item["versiones_set"].add(row.get("version_visible"))
        item["versiones_set"].update(versiones_nombre)
        item["departamentos_set"].add(row.get("departamento_nombre") or "Sin departamento")
        equipo_usuario = row.get("equipo_nombre") or row.get("usuario_texto")
        item["equipos_usuarios_set"].add(equipo_usuario)
        item["observaciones_set"].add(row.get("observaciones"))
        fecha = row.get("fecha_autorizacion") or row.get("fecha_alta")
        if fecha and (item["fecha_reciente"] is None or fecha > item["fecha_reciente"]):
            item["fecha_reciente"] = fecha
        if row.get("equipo_activo_id") is not None:
            item["equipo_ids"].add(row["equipo_activo_id"])
        elif row.get("usuario_texto"):
            item["usuario_texto_ids"].add(row["id"])
        item["registros"] += 1

    result = []
    for item in grupos.values():
        nombres = sorted(item["nombres"], key=lambda value: (len(value), value.casefold()))
        n_dispositivos_vinculados = len(item["equipo_ids"])
        n_usuarios_texto = len(item["usuario_texto_ids"])
        result.append(
            {
                "grupo": item["grupo"],
                "nombre": nombres[0] if nombres else item["grupo"],
                "fabricantes": _clean_join(item["fabricantes_set"]),
                "versiones": _clean_join(item["versiones_set"]),
                "departamentos": _clean_join(item["departamentos_set"]),
                "equipos_usuarios": _clean_join(item["equipos_usuarios_set"]),
                "observaciones": _clean_join(item["observaciones_set"], " | "),
                "fecha_reciente": item["fecha_reciente"],
                "n_dispositivos_vinculados": n_dispositivos_vinculados,
                "n_usuarios_texto": n_usuarios_texto,
                "n_dispositivos": n_dispositivos_vinculados + n_usuarios_texto,
                "registros": item["registros"],
            }
        )
    return sorted(result, key=lambda row: str(row["nombre"]).casefold())


def promover_multidevice_a_inventario(db) -> int:
    """
    Marca como inactivos los registros de software_autorizado cuyo software
    vinculado ya esta instalado en 2 o mas dispositivos activos.

    El software sigue apareciendo en el inventario del departamento; solo deja
    de figurar como autorizacion individual.
    """
    result = db.execute(
        text(
            """
            UPDATE software_autorizado sa
            SET sa.activo = FALSE
            WHERE COALESCE(sa.activo, TRUE) = TRUE
              AND sa.software_id IS NOT NULL
              AND (
                  SELECT COUNT(DISTINCT swe_chk.equipo_id)
                  FROM software_equipo swe_chk
                  JOIN equipos e_chk ON e_chk.id = swe_chk.equipo_id
                  WHERE swe_chk.software_id = sa.software_id
                    AND swe_chk.presente = TRUE
                    AND e_chk.activo = TRUE
              ) >= 2
            """
        )
    )
    return int(result.rowcount or 0)


def promover_antiguos_a_inventario(db, dias: int = 90) -> int:
    """
    Marca como inactivos los registros de software_autorizado cuyo software
    lleva mas de `dias` dias instalado en el dispositivo.

    Usa fecha_instalacion si esta disponible; si no, fecha_ultima_deteccion.
    El software sigue apareciendo en el inventario del departamento.
    """
    result = db.execute(
        text(
            """
            UPDATE software_autorizado sa
            SET sa.activo = FALSE
            WHERE COALESCE(sa.activo, TRUE) = TRUE
              AND sa.software_id IS NOT NULL
              AND EXISTS (
                  SELECT 1
                  FROM software_equipo swe
                  JOIN equipos e ON e.id = swe.equipo_id
                  WHERE swe.software_id = sa.software_id
                    AND swe.presente = TRUE
                    AND e.activo = TRUE
                    AND COALESCE(swe.fecha_instalacion, swe.fecha_ultima_deteccion)
                        <= DATE_SUB(CURRENT_DATE, INTERVAL :dias DAY)
              )
            """
        ),
        {"dias": dias},
    )
    return int(result.rowcount or 0)


def contar_pendientes_promocion(db, dias: int = 90) -> int:
    """
    Cuenta registros de software_autorizado que pasarian al inventario porque
    estan en 2+ dispositivos o llevan mas de `dias` dias instalados.
    """
    result = db.execute(
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
                            <= DATE_SUB(CURRENT_DATE, INTERVAL :dias DAY)
                  )
              )
            """
        ),
        {"dias": dias},
    ).scalar()
    return int(result or 0)


def promover_todos_los_pendientes(db, dias: int = 90) -> dict:
    """
    Ejecuta los dos tipos de promocion en una sola llamada.
    Devuelve los conteos de cada motivo.
    """
    por_multidevice = promover_multidevice_a_inventario(db)
    por_antiguedad = promover_antiguos_a_inventario(db, dias=dias)
    return {
        "por_multidevice": por_multidevice,
        "por_antiguedad": por_antiguedad,
        "total": por_multidevice + por_antiguedad,
    }


def listar_autorizado_detalle_grupo(db, grupo: str) -> list[dict]:
    rows = [
        row
        for row in _listar_autorizado_rows(db)
        if _normalizar_autorizado_nombre(row.get("nombre_visible"))[0] == grupo
    ]
    return sorted(
        rows,
        key=lambda row: (
            str(row.get("departamento_nombre") or "").casefold(),
            str(row.get("nombre_visible") or "").casefold(),
            str(row.get("version_visible") or "").casefold(),
        ),
    )


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
    ids = [
        row["id"]
        for row in _listar_autorizado_rows(db)
        if _normalizar_autorizado_nombre(row.get("nombre_visible"))[0] == grupo
    ]
    if not ids:
        return 0
    params = {f"id_{idx}": autorizado_id for idx, autorizado_id in enumerate(ids)}
    placeholders = ", ".join(f":{key}" for key in params)
    result = db.execute(
        text(
            f"""
            UPDATE software_autorizado
            SET activo = FALSE
            WHERE id IN ({placeholders})
            """
        ),
        params,
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
