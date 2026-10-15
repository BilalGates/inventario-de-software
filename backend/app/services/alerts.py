"""Alertas idempotentes (dedup_key) y reevaluaciones globales."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models import Alert, Device, InventorySource, SoftwareInstallation, SoftwareProduct
from app.services.software import PolicyEvaluator


def open_alert(
    db: Session,
    dedup_key: str,
    alert_type: str,
    severity: str,
    title: str,
    detail: str | None = None,
    device_id: int | None = None,
    product_id: int | None = None,
    run_id: int | None = None,
) -> tuple[Alert, bool]:
    """Abre la alerta si no hay una abierta/reconocida con la misma clave. Devuelve (alerta, creada)."""
    existing = db.execute(
        select(Alert).where(Alert.dedup_key == dedup_key, Alert.status != "resolved")
    ).scalars().first()
    now = utcnow()
    if existing:
        existing.last_seen_at = now
        existing.detail = detail or existing.detail
        return existing, False
    alert = Alert(dedup_key=dedup_key, alert_type=alert_type, severity=severity, title=title[:300], detail=detail,
                  device_id=device_id, product_id=product_id, run_id=run_id, created_at=now, last_seen_at=now)
    db.add(alert)
    db.flush()
    return alert, True


def resolve_alerts(db: Session, dedup_keys: set[str] | None = None, prefix: str | None = None,
                   by: str = "system", resolution: str = "Condición desaparecida") -> int:
    query = select(Alert).where(Alert.status != "resolved")
    if prefix:
        query = query.where(Alert.dedup_key.startswith(prefix))
    count = 0
    now = utcnow()
    for alert in db.execute(query).scalars():
        if dedup_keys is not None and alert.dedup_key not in dedup_keys:
            continue
        alert.status, alert.resolved_at, alert.resolved_by, alert.resolution = "resolved", now, by, resolution
        count += 1
    return count


def evaluate_unauthorized(db: Session, run_id: int | None = None) -> dict:
    """Abre una alerta por cada instalación presente no autorizada y cierra las que ya no aplican."""
    evaluator = PolicyEvaluator(db)
    rows = db.execute(
        select(SoftwareInstallation.device_id, SoftwareInstallation.product_id)
        .where(SoftwareInstallation.present.is_(True)).distinct()
    ).all()
    devices = {d.id: d for d in db.execute(select(Device).where(Device.status != "retired")).scalars()}
    products: dict[int, SoftwareProduct] = {}
    live: set[str] = set()
    opened = 0
    for device_id, product_id in rows:
        device = devices.get(device_id)
        if device is None:
            continue
        product = products.get(product_id) or db.get(SoftwareProduct, product_id)
        products[product_id] = product
        status, _ = evaluator.evaluate(product, device)
        if status != "unauthorized":
            continue
        key = f"unauthorized:{device_id}:{product_id}"
        live.add(key)
        _, created = open_alert(db, key, "unauthorized_software", "critical",
                                f"Software no autorizado: {product.name} en {device.display_name}",
                                device_id=device_id, product_id=product_id, run_id=run_id)
        opened += created
    stale = {a.dedup_key for a in db.execute(
        select(Alert).where(Alert.alert_type == "unauthorized_software", Alert.status != "resolved")
    ).scalars()} - live
    resolved = resolve_alerts(db, stale, resolution="Ya no está instalado o ya está autorizado") if stale else 0
    return {"opened": opened, "resolved": resolved, "active": len(live)}


def check_stale_sources(db: Session, max_age_days: int) -> int:
    """Alerta si una fuente activa lleva demasiado sin una ejecución completa."""
    now = utcnow()
    opened = 0
    for src in db.execute(select(InventorySource).where(InventorySource.enabled.is_(True),
                                                        InventorySource.kind == "api")).scalars():
        key = f"stale_source:{src.code}"
        if src.last_success_at and now - src.last_success_at < timedelta(days=max_age_days):
            resolve_alerts(db, {key}, resolution="Sincronización reciente correcta")
            continue
        when = src.last_success_at.strftime("%Y-%m-%d") if src.last_success_at else "nunca"
        _, created = open_alert(db, key, "stale_source", "warning",
                                f"{src.name}: sin sincronización completa desde {when}")
        opened += created
    return opened
