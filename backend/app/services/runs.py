"""Cola de ejecuciones (tabla inventory_runs) y factoría de conectores."""
from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.connectors.base import ConnectorError
from app.connectors.files import IntuneCsvConnector, PandaFileConnector
from app.connectors.graph import GraphClient
from app.connectors.intune import IntuneConnector
from app.core.config import get_settings
from app.db import utcnow
from app.models import InventoryRun, InventorySource
from app.services import audit
from app.services.sync import SyncEngine

ACTIVE = ("queued", "running")


def default_connector_factory(source: InventorySource, params: dict[str, Any]):
    if source.code == "intune":
        if params.get("content") is not None:
            return IntuneCsvConnector()
        s = get_settings()
        client = GraphClient(s.graph_tenant_id, s.graph_client_id, s.graph_client_secret, s.graph_certificate_path,
                             s.graph_certificate_thumbprint, s.graph_base_url, s.graph_max_retries)
        cfg = source.config or {}
        params.setdefault("software_strategy", cfg.get("software_strategy", "per_app"))
        return IntuneConnector(client, api_version=cfg.get("api_version", "v1.0"))
    if source.code == "panda":
        return PandaFileConnector()
    raise ConnectorError(f"No hay conector para la fuente '{source.code}'.", kind="config")


def source_by_code(db: Session, code: str) -> InventorySource:
    src = db.execute(select(InventorySource).where(InventorySource.code == code)).scalar_one_or_none()
    if src is None:
        raise ValueError(f"Fuente desconocida: {code}")
    return src


def enqueue(db: Session, source_code: str, trigger: str, actor: str, params: dict | None = None,
            period: str | None = None, retry_of: InventoryRun | None = None) -> InventoryRun:
    src = source_by_code(db, source_code)
    if not src.enabled:
        raise ValueError(f"La fuente {src.name} está desactivada.")
    params = params or {}
    batch_hash = hashlib.sha256(params["content"].encode()).hexdigest() if params.get("content") else None
    if params.get("content") is None:  # una sola ejecución API activa por fuente
        active = db.execute(select(InventoryRun).where(
            InventoryRun.source_id == src.id, InventoryRun.status.in_(ACTIVE),
            InventoryRun.batch_hash.is_(None),
        )).scalars().first()
        if active:
            return active
    run = InventoryRun(source_id=src.id, trigger=trigger, status="queued", requested_by=actor, params=params,
                       period=period or utcnow().strftime("%Y-%m"), batch_hash=batch_hash,
                       attempt=(retry_of.attempt + 1) if retry_of else 1,
                       retry_of_id=retry_of.id if retry_of else None)
    db.add(run)
    db.flush()
    audit.record(db, actor, "run.enqueue", "inventory_run", run.id, f"{source_code} ({trigger})",
                 after={"params": {k: v for k, v in params.items() if k != "content"}})
    return run


def retry(db: Session, run_id: int, actor: str) -> InventoryRun:
    old = db.get(InventoryRun, run_id)
    if old is None:
        raise ValueError("Ejecución no encontrada.")
    if old.status not in ("failed", "partial"):
        raise ValueError("Solo se pueden reintentar ejecuciones fallidas o parciales.")
    src = db.get(InventorySource, old.source_id)
    return enqueue(db, src.code, "retry", actor, dict(old.params or {}), old.period, retry_of=old)


def claim_next(db: Session) -> InventoryRun | None:
    """Reserva la siguiente ejecución en cola (seguro con varios workers en MySQL)."""
    query = select(InventoryRun).where(InventoryRun.status == "queued").order_by(InventoryRun.id).limit(1)
    if db.bind.dialect.name == "mysql":
        query = query.with_for_update(skip_locked=True)
    run = db.execute(query).scalar_one_or_none()
    if run is None:
        return None
    claimed = db.execute(
        update(InventoryRun).where(InventoryRun.id == run.id, InventoryRun.status == "queued")
        .values(status="running", started_at=utcnow())
    ).rowcount
    db.commit()
    return run if claimed else None


def execute_run(db: Session, run: InventoryRun, factory=default_connector_factory) -> InventoryRun:
    return SyncEngine(db, factory).execute(run)


def recover_stuck(db: Session, max_minutes: int = 120) -> int:
    """Ejecuciones que quedaron 'running' por una caída del worker se marcan fallidas."""
    from datetime import timedelta

    limit = utcnow() - timedelta(minutes=max_minutes)
    count = 0
    for run in db.execute(select(InventoryRun).where(InventoryRun.status == "running",
                                                     InventoryRun.started_at < limit)).scalars():
        run.status, run.error, run.finished_at = "failed", "[internal] Interrumpida (worker detenido)", utcnow()
        count += 1
    db.commit()
    return count
