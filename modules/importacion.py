from __future__ import annotations

from datetime import date

from sqlalchemy import text

from modules.software import generar_codigo_software
from utils.normalizer import clean_version, normalize_nombre


def _program_key(program: dict) -> str:
    return normalize_nombre(program.get("nombre", ""))


def _load_context(db, equipo_id: int) -> tuple[dict, dict, dict]:
    equipo = db.execute(
        text(
            """
            SELECT e.*, d.prefijo_id
            FROM equipos e
            JOIN departamentos d ON d.id = e.departamento_id
            WHERE e.id = :equipo_id
            """
        ),
        {"equipo_id": equipo_id},
    ).mappings().first()
    if not equipo:
        raise ValueError("Equipo no encontrado")

    catalogo = {
        row["nombre_norm"]: dict(row)
        for row in db.execute(
            text(
                """
                SELECT *
                FROM software
                WHERE departamento_id = :departamento_id
                  AND activo = TRUE
                """
            ),
            {"departamento_id": equipo["departamento_id"]},
        ).mappings().all()
    }

    enlaces = {
        row["software_id"]: dict(row)
        for row in db.execute(
            text(
                """
                SELECT swe.*, s.nombre, s.nombre_norm, s.fabricante
                FROM software_equipo swe
                JOIN software s ON s.id = swe.software_id
                WHERE swe.equipo_id = :equipo_id
                  AND swe.presente = TRUE
                """
            ),
            {"equipo_id": equipo_id},
        ).mappings().all()
    }
    return dict(equipo), catalogo, enlaces


def calcular_diff(equipo_id, programas: list[dict], db) -> dict:
    equipo, catalogo, enlaces = _load_context(db, equipo_id)
    vistos_software_ids: set[int] = set()
    vistos_nombre_norm: set[str] = set()
    diff = {
        "nuevos": [],
        "actualizados": [],
        "cambios_version": [],
        "eliminados": [],
        "nuevos_en_catalogo": [],
    }

    for programa in programas:
        nombre_norm = _program_key(programa)
        if not nombre_norm or nombre_norm in vistos_nombre_norm:
            continue
        vistos_nombre_norm.add(nombre_norm)
        programa_norm = {**programa, "nombre_norm": nombre_norm, "version": clean_version(programa.get("version"))}
        software = catalogo.get(nombre_norm)

        if software:
            software_id = software["id"]
            vistos_software_ids.add(software_id)
            enlace = enlaces.get(software_id)
            if enlace:
                previous = clean_version(enlace.get("version_detectada"))
                current = programa_norm.get("version")
                item = {**programa_norm, "software_id": software_id, "software": software, "enlace": enlace}
                if previous == current:
                    diff["actualizados"].append(item)
                else:
                    diff["cambios_version"].append(
                        {**item, "version_anterior": previous, "version_nueva": current}
                    )
            else:
                diff["nuevos"].append({**programa_norm, "software_id": software_id, "software": software})
        else:
            item = {**programa_norm, "departamento_id": equipo["departamento_id"]}
            diff["nuevos"].append(item)
            diff["nuevos_en_catalogo"].append(item)

    for software_id, enlace in enlaces.items():
        if software_id not in vistos_software_ids:
            diff["eliminados"].append(enlace)
    return diff


def ultima_importacion_por_equipo(db, equipo_id: int) -> dict | None:
    row = db.execute(
        text(
            """
            SELECT
                id,
                equipo_id,
                fecha_importacion,
                metodo,
                n_total,
                n_nuevos,
                n_actualizados,
                n_eliminados,
                n_cambios_version,
                confirmada,
                notas
            FROM importaciones
            WHERE equipo_id = :equipo_id
              AND confirmada = TRUE
            ORDER BY fecha_importacion DESC, id DESC
            LIMIT 1
            """
        ),
        {"equipo_id": equipo_id},
    ).mappings().first()
    return dict(row) if row else None


def ultimas_importaciones_por_equipo(db, equipo_id: int, limit: int = 5) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT
                id,
                equipo_id,
                fecha_importacion,
                metodo,
                n_total,
                n_nuevos,
                n_actualizados,
                n_eliminados,
                n_cambios_version,
                confirmada,
                notas
            FROM importaciones
            WHERE equipo_id = :equipo_id
              AND confirmada = TRUE
            ORDER BY fecha_importacion DESC, id DESC
            LIMIT :limit
            """
        ),
        {"equipo_id": equipo_id, "limit": limit},
    ).mappings().all()
    return [dict(row) for row in rows]


def ultima_importacion_por_equipos(db, equipo_ids: list[int]) -> dict[int, dict]:
    if not equipo_ids:
        return {}
    placeholders = []
    params = {}
    for idx, equipo_id in enumerate(equipo_ids):
        key = f"equipo_id_{idx}"
        placeholders.append(f":{key}")
        params[key] = equipo_id
    rows = db.execute(
        text(
            f"""
            SELECT
                i.id,
                i.equipo_id,
                i.fecha_importacion,
                i.metodo,
                i.n_total,
                i.n_nuevos,
                i.n_actualizados,
                i.n_eliminados,
                i.n_cambios_version,
                i.confirmada,
                i.notas
            FROM importaciones i
            JOIN (
                SELECT equipo_id, MAX(fecha_importacion) AS max_fecha
                FROM importaciones
                WHERE confirmada = TRUE
                  AND equipo_id IN ({', '.join(placeholders)})
                GROUP BY equipo_id
            ) latest
              ON latest.equipo_id = i.equipo_id
             AND latest.max_fecha = i.fecha_importacion
            WHERE i.confirmada = TRUE
            """
        ),
        params,
    ).mappings().all()
    latest_by_equipo: dict[int, dict] = {}
    for row in rows:
        item = dict(row)
        current = latest_by_equipo.get(item["equipo_id"])
        if current is None or item["id"] > current["id"]:
            latest_by_equipo[item["equipo_id"]] = item
    return latest_by_equipo


def _registrar_reactivacion_pendiente(db, software_id: int, equipo_id: int) -> None:
    db.execute(
        text(
            """
            INSERT INTO software_reactivacion_pendiente (software_id, equipo_id)
            SELECT :software_id, :equipo_id
            WHERE NOT EXISTS (
                SELECT 1
                FROM software_reactivacion_pendiente
                WHERE software_id = :software_id
                  AND equipo_id = :equipo_id
                  AND revisado = FALSE
            )
            """
        ),
        {"software_id": software_id, "equipo_id": equipo_id},
    )


def contar_reactivaciones_pendientes(db, departamento_id: int | None = None) -> int:
    where = ["srp.revisado = FALSE"]
    params = {}
    if departamento_id is not None:
        where.append("s.departamento_id = :departamento_id")
        params["departamento_id"] = departamento_id
    return int(
        db.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM software_reactivacion_pendiente srp
                JOIN software s ON s.id = srp.software_id
                WHERE {' AND '.join(where)}
                """
            ),
            params,
        ).scalar()
        or 0
    )


def listar_reactivaciones_pendientes(db, departamento_id: int | None = None) -> list[dict]:
    where = ["srp.revisado = FALSE"]
    params = {}
    if departamento_id is not None:
        where.append("s.departamento_id = :departamento_id")
        params["departamento_id"] = departamento_id
    rows = db.execute(
        text(
            f"""
            SELECT
                srp.id,
                srp.software_id,
                srp.equipo_id,
                srp.fecha_deteccion,
                s.nombre AS software_nombre,
                s.version_referencia,
                s.fabricante,
                d.nombre AS departamento,
                e.nombre AS equipo
            FROM software_reactivacion_pendiente srp
            JOIN software s ON s.id = srp.software_id
            JOIN departamentos d ON d.id = s.departamento_id
            JOIN equipos e ON e.id = srp.equipo_id
            WHERE {' AND '.join(where)}
            ORDER BY srp.fecha_deteccion DESC, s.nombre
            """
        ),
        params,
    ).mappings().all()
    return [dict(row) for row in rows]


def resolver_reactivacion(db, reactivacion_id: int, accion: str) -> None:
    row = db.execute(
        text(
            """
            SELECT software_id, equipo_id
            FROM software_reactivacion_pendiente
            WHERE id = :id
              AND revisado = FALSE
            """
        ),
        {"id": reactivacion_id},
    ).mappings().first()
    if not row:
        return
    if accion == "reactivar":
        db.execute(
            text(
                """
                UPDATE software
                SET activo = TRUE,
                    fecha_ultima_actualizacion = CURRENT_DATE
                WHERE id = :software_id
                """
            ),
            {"software_id": row["software_id"]},
        )
        db.execute(
            text(
                """
                UPDATE software_equipo
                SET presente = TRUE,
                    fecha_ultima_deteccion = CURRENT_DATE
                WHERE software_id = :software_id
                  AND equipo_id = :equipo_id
                """
            ),
            {"software_id": row["software_id"], "equipo_id": row["equipo_id"]},
        )
    db.execute(
        text(
            """
            UPDATE software_reactivacion_pendiente
            SET revisado = TRUE,
                accion = :accion
            WHERE id = :id
            """
        ),
        {"id": reactivacion_id, "accion": accion},
    )


def _get_or_create_software(db, departamento_id: int, equipo_id: int, programa: dict) -> int | None:
    nombre_norm = _program_key(programa)
    existing = db.execute(
        text(
            """
            SELECT id, activo
            FROM software
            WHERE departamento_id = :departamento_id
              AND nombre_norm = :nombre_norm
            LIMIT 1
            """
        ),
        {"departamento_id": departamento_id, "nombre_norm": nombre_norm},
    ).mappings().first()
    if existing:
        if not existing["activo"]:
            _registrar_reactivacion_pendiente(db, int(existing["id"]), equipo_id)
            return None
        return int(existing["id"])

    codigo = generar_codigo_software(db, departamento_id)
    result = db.execute(
        text(
            """
            INSERT INTO software (
                departamento_id, codigo, nombre, nombre_norm, fabricante,
                version_referencia, fecha_ultima_actualizacion
            )
            VALUES (
                :departamento_id, :codigo, :nombre, :nombre_norm, :fabricante,
                :version_referencia, :fecha_ultima_actualizacion
            )
            """
        ),
        {
            "departamento_id": departamento_id,
            "codigo": codigo,
            "nombre": programa["nombre"],
            "nombre_norm": nombre_norm,
            "fabricante": programa.get("fabricante"),
            "version_referencia": clean_version(programa.get("version")),
            "fecha_ultima_actualizacion": date.today(),
        },
    )
    return int(result.lastrowid)


def _upsert_software_equipo(db, software_id: int, equipo_id: int, programa: dict, today: date) -> None:
    db.execute(
        text(
            """
            INSERT INTO software_equipo (
                software_id, equipo_id, version_detectada, fecha_instalacion,
                tamano, fecha_ultima_deteccion, presente
            )
            VALUES (
                :software_id, :equipo_id, :version_detectada, :fecha_instalacion,
                :tamano, :fecha_ultima_deteccion, TRUE
            )
            ON DUPLICATE KEY UPDATE
                version_detectada = VALUES(version_detectada),
                fecha_instalacion = VALUES(fecha_instalacion),
                tamano = VALUES(tamano),
                fecha_ultima_deteccion = VALUES(fecha_ultima_deteccion),
                presente = TRUE
            """
        ),
        {
            "software_id": software_id,
            "equipo_id": equipo_id,
            "version_detectada": clean_version(programa.get("version")),
            "fecha_instalacion": programa.get("fecha_instalacion"),
            "tamano": programa.get("tamano"),
            "fecha_ultima_deteccion": today,
        },
    )


def aplicar_diff(equipo_id, programas, diff, db, metodo) -> int:
    equipo = db.execute(
        text("SELECT departamento_id FROM equipos WHERE id = :equipo_id"),
        {"equipo_id": equipo_id},
    ).mappings().first()
    if not equipo:
        raise ValueError("Equipo no encontrado")
    departamento_id = equipo["departamento_id"]
    today = date.today()

    software_by_norm: dict[str, int] = {}
    for programa in programas:
        nombre_norm = _program_key(programa)
        if not nombre_norm or nombre_norm in software_by_norm:
            continue
        software_id = _get_or_create_software(db, departamento_id, equipo_id, programa)
        if software_id is not None:
            software_by_norm[nombre_norm] = software_id

    for programa in diff["nuevos"]:
        software_id = programa.get("software_id") or software_by_norm.get(_program_key(programa))
        if software_id is None:
            continue
        _upsert_software_equipo(db, software_id, equipo_id, programa, today)
        db.execute(
            text("UPDATE software SET fecha_ultima_actualizacion = :today WHERE id = :software_id"),
            {"today": today, "software_id": software_id},
        )

    for programa in diff["actualizados"]:
        db.execute(
            text(
                """
                UPDATE software_equipo
                SET fecha_ultima_deteccion = :today
                WHERE software_id = :software_id
                  AND equipo_id = :equipo_id
                """
            ),
            {"today": today, "software_id": programa["software_id"], "equipo_id": equipo_id},
        )
        db.execute(
            text("UPDATE software SET fecha_ultima_actualizacion = :today WHERE id = :software_id"),
            {"today": today, "software_id": programa["software_id"]},
        )

    for programa in diff["cambios_version"]:
        nueva = clean_version(programa.get("version_nueva"))
        db.execute(
            text(
                """
                UPDATE software_equipo
                SET version_detectada = :version_detectada,
                    fecha_instalacion = :fecha_instalacion,
                    tamano = :tamano,
                    fecha_ultima_deteccion = :today
                WHERE software_id = :software_id
                  AND equipo_id = :equipo_id
                """
            ),
            {
                "version_detectada": nueva,
                "fecha_instalacion": programa.get("fecha_instalacion"),
                "tamano": programa.get("tamano"),
                "today": today,
                "software_id": programa["software_id"],
                "equipo_id": equipo_id,
            },
        )
        current_ref = programa.get("software", {}).get("version_referencia")
        if nueva and (not current_ref or str(nueva) > str(current_ref)):
            db.execute(
                text(
                    """
                    UPDATE software
                    SET version_referencia = :version,
                        fecha_ultima_actualizacion = :today
                    WHERE id = :software_id
                    """
                ),
                {"version": nueva, "today": today, "software_id": programa["software_id"]},
            )
        else:
            db.execute(
                text("UPDATE software SET fecha_ultima_actualizacion = :today WHERE id = :software_id"),
                {"today": today, "software_id": programa["software_id"]},
            )

    for enlace in diff["eliminados"]:
        db.execute(
            text(
                """
                UPDATE software_equipo
                SET presente = FALSE,
                    fecha_ultima_deteccion = :today
                WHERE software_id = :software_id
                  AND equipo_id = :equipo_id
                """
            ),
            {"today": today, "software_id": enlace["software_id"], "equipo_id": equipo_id},
        )

    result = db.execute(
        text(
            """
            INSERT INTO importaciones (
                equipo_id, metodo, n_total, n_nuevos, n_actualizados,
                n_eliminados, n_cambios_version, confirmada
            )
            VALUES (
                :equipo_id, :metodo, :n_total, :n_nuevos, :n_actualizados,
                :n_eliminados, :n_cambios_version, TRUE
            )
            """
        ),
        {
            "equipo_id": equipo_id,
            "metodo": metodo,
            "n_total": len(programas),
            "n_nuevos": len(diff["nuevos"]),
            "n_actualizados": len(diff["actualizados"]),
            "n_eliminados": len(diff["eliminados"]),
            "n_cambios_version": len(diff["cambios_version"]),
        },
    )
    return int(result.lastrowid)
