"""Registro de auditoría encadenado por hash."""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models import AuditEvent

GENESIS = "0" * 64


def _jsonable(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    return value


def _digest(event: AuditEvent) -> str:
    body = json.dumps(
        {
            "prev": event.prev_hash,
            "at": event.occurred_at.isoformat(timespec="microseconds"),
            "actor": event.actor,
            "action": event.action,
            "type": event.entity_type,
            "id": event.entity_id,
            "summary": event.summary,
            "before": event.before,
            "after": event.after,
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def record(
    db: Session,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: Any = None,
    summary: str | None = None,
    before: dict | None = None,
    after: dict | None = None,
) -> AuditEvent:
    """Añade un evento en la transacción actual (se confirma junto con el cambio auditado)."""
    last = db.execute(
        select(AuditEvent.hash).order_by(AuditEvent.id.desc()).limit(1).with_for_update()
    ).scalar_one_or_none()
    event = AuditEvent(
        occurred_at=utcnow(),
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=None if entity_id is None else str(entity_id),
        summary=(summary or "")[:500] or None,
        before=_jsonable(before) if before else None,
        after=_jsonable(after) if after else None,
        prev_hash=last or GENESIS,
    )
    event.hash = _digest(event)
    db.add(event)
    db.flush()
    return event


def verify_chain(db: Session) -> dict:
    """Recalcula la cadena completa. Devuelve el primer evento roto, si lo hay."""
    prev = GENESIS
    count = 0
    for event in db.execute(select(AuditEvent).order_by(AuditEvent.id)).scalars():
        count += 1
        if event.prev_hash != prev or _digest(event) != event.hash:
            return {"valid": False, "checked": count, "broken_event_id": event.id}
        prev = event.hash
    return {"valid": True, "checked": count, "broken_event_id": None}


def snapshot(obj: Any, fields: list[str]) -> dict:
    return {f: _jsonable(getattr(obj, f)) for f in fields}
