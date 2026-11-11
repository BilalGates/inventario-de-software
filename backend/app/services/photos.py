"""Fotos de perfil de Microsoft 365 para los usuarios del inventario (ProfilePhoto.Read.All).

Se descargan en pequeño (96x96) y se guardan en la base de datos: las pantallas nunca llaman a Graph.
Cada foto se revisa como mucho una vez por semana; quien no tiene foto se marca igualmente como revisado.
Sin permiso, se deja constancia y no se reintenta hasta el día siguiente (se siguen viendo las iniciales).
"""
from __future__ import annotations

import base64
import logging
from datetime import datetime, timedelta
from urllib.parse import quote

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, undefer

from app.connectors.base import ConnectorError
from app.db import utcnow
from app.models import AppSetting, User

log = logging.getLogger(__name__)
STATUS_KEY = "photos.status"
REFRESH_EVERY = timedelta(days=7)
RETRY_DENIED_AFTER = timedelta(days=1)
MAX_BYTES = 200_000


def _status(db: Session) -> dict:
    row = db.get(AppSetting, STATUS_KEY)
    return dict(row.value or {}) if row else {}


def _set_status(db: Session, value: dict) -> None:
    row = db.get(AppSetting, STATUS_KEY) or AppSetting(key=STATUS_KEY)
    row.value, row.updated_by = value, "system:photos"
    db.add(row)


def due(db: Session, limit: int) -> list[User]:
    limit_date = utcnow() - REFRESH_EVERY
    return list(db.execute(select(User).where(User.active.is_(True), User.upn.contains("@"),
                                              or_(User.photo_checked_at.is_(None), User.photo_checked_at < limit_date))
                           .order_by(User.photo_checked_at.is_not(None), User.photo_checked_at).limit(limit)).scalars())


def refresh(db: Session, client, limit: int = 40) -> dict:
    """Descarga las fotos pendientes (hasta `limit` por pasada)."""
    denied_at = _status(db).get("denied_at")
    if denied_at and utcnow() < datetime.fromisoformat(denied_at) + RETRY_DENIED_AFTER:
        return {"skipped": "permission"}
    done = found = 0
    for user in due(db, limit):
        try:
            got = client.get_bytes(f"/v1.0/users/{quote(user.upn)}/photos/96x96/$value")
        except ConnectorError as exc:
            if exc.kind in ("permission", "auth", "config"):
                _set_status(db, {"denied_at": utcnow().isoformat(timespec="seconds"), "error": str(exc)})
                log.info("Sin permiso para leer fotos de perfil: %s", exc)
                return {"updated": done, "found": found, "skipped": "permission"}
            log.warning("No se pudo leer la foto de %s: %s", user.upn, exc)
            continue
        if got and len(got[0]) <= MAX_BYTES and got[1].startswith("image/"):
            user.photo, user.photo_type = got
            found += 1
        else:
            user.photo, user.photo_type = None, None
        user.photo_checked_at = utcnow()
        done += 1
    _set_status(db, {"checked_at": utcnow().isoformat(timespec="seconds"), "updated": done})
    db.flush()
    return {"updated": done, "found": found}


def all_photos(db: Session) -> dict[str, str]:
    """{upn: data URI} de todos los usuarios con foto (decenas: cabe en una respuesta)."""
    rows = db.execute(select(User).options(undefer(User.photo)).where(User.photo.is_not(None))).scalars()
    return {u.upn.lower(): f"data:{u.photo_type or 'image/jpeg'};base64,{base64.b64encode(u.photo).decode()}"
            for u in rows}
