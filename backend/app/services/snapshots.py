"""Inventarios mensuales: generación (borrador), comparación y aprobación por IT."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models import (
    Device,
    InventoryRun,
    InventorySnapshot,
    InventorySnapshotItem,
    InventorySource,
    SoftwareInstallation,
    SoftwareProduct,
    SoftwareVersion,
)
from app.services import audit
from app.services.software import PolicyEvaluator


def coverage(db: Session, period: str) -> dict:
    """Estado de cada fuente activa en el periodo: ¿hay una ejecución completa posterior al último fallo?"""
    out = {}
    complete = True
    for src in db.execute(select(InventorySource).where(InventorySource.enabled.is_(True))).scalars():
        runs = db.execute(select(InventoryRun).where(InventoryRun.source_id == src.id, InventoryRun.period == period)
                          .order_by(InventoryRun.id)).scalars().all()
        last_complete = next((r for r in reversed(runs) if r.is_complete), None)
        failed_after = any(r.status in ("failed", "partial") and (last_complete is None or r.id > last_complete.id)
                           for r in runs)
        essential = src.kind == "api"
        ok = last_complete is not None and not failed_after
        if essential and not ok:
            complete = False
        out[src.code] = {
            "name": src.name, "essential": essential, "ok": ok, "runs": len(runs),
            "last_complete_run_id": last_complete.id if last_complete else None,
            "failed_after_last_complete": failed_after,
        }
    return {"sources": out, "complete": complete}


def generate(db: Session, period: str, actor: str) -> InventorySnapshot:
    cov = coverage(db, period)
    version = (db.execute(select(func.max(InventorySnapshot.version)).where(InventorySnapshot.period == period))
               .scalar() or 0) + 1
    snap = InventorySnapshot(period=period, version=version, status="draft", is_complete=cov["complete"],
                             coverage=cov, created_by=actor, created_at=utcnow())
    db.add(snap)
    db.flush()
    evaluator = PolicyEvaluator(db)
    devices = {d.id: d for d in db.execute(select(Device).where(Device.status != "retired")).scalars()}
    items = []
    for dev in devices.values():
        items.append(InventorySnapshotItem(snapshot_id=snap.id, device_id=dev.id, department_id=dev.department_id,
                                           product_id=None, version=""))
    rows = db.execute(
        select(SoftwareInstallation.device_id, SoftwareProduct, SoftwareVersion.version)
        .join(SoftwareProduct, SoftwareProduct.id == SoftwareInstallation.product_id)
        .join(SoftwareVersion, SoftwareVersion.id == SoftwareInstallation.version_id)
        .where(SoftwareInstallation.present.is_(True))
    ).all()
    seen = set()
    status_count: dict[str, int] = defaultdict(int)
    for device_id, product, version in rows:
        dev = devices.get(device_id)
        if dev is None or (device_id, product.id, version) in seen:
            continue
        seen.add((device_id, product.id, version))
        status, _ = evaluator.evaluate(product, dev)
        status_count[status] += 1
        items.append(InventorySnapshotItem(snapshot_id=snap.id, device_id=device_id, department_id=dev.department_id,
                                           product_id=product.id, version=version, authorization_status=status))
    db.add_all(items)
    snap.totals = {
        "devices": len(devices),
        "installations": len(seen),
        "products": len({p for _, p, _ in seen}),
        "by_status": dict(status_count),
    }
    audit.record(db, actor, "snapshot.generate", "inventory_snapshot", snap.id, f"Inventario {period} v{version}",
                 after={"totals": snap.totals, "complete": snap.is_complete})
    return snap


def review(db: Session, snapshot_id: int, actor: str, approve: bool, notes: str | None,
           accept_incomplete: bool = False) -> InventorySnapshot:
    snap = db.get(InventorySnapshot, snapshot_id)
    if snap is None:
        raise ValueError("Inventario no encontrado.")
    if snap.status != "draft":
        raise ValueError("El inventario ya fue revisado.")
    if approve and not snap.is_complete and not accept_incomplete:
        raise ValueError("El inventario está incompleto: alguna fuente esencial falló. Reintente la sincronización "
                         "o apruebe indicando expresamente que acepta un inventario incompleto.")
    if approve and not snap.is_complete and not (notes or "").strip():
        raise ValueError("Aprobar un inventario incompleto exige una justificación.")
    snap.status = "approved" if approve else "rejected"
    snap.reviewed_by, snap.reviewed_at, snap.review_notes = actor, utcnow(), notes
    audit.record(db, actor, f"snapshot.{snap.status}", "inventory_snapshot", snap.id,
                 f"Inventario {snap.period} v{snap.version} {snap.status}",
                 after={"notes": notes, "complete": snap.is_complete, "accept_incomplete": accept_incomplete})
    return snap


def _item_sets(db: Session, snapshot_id: int):
    devices, installs = set(), {}
    for it in db.execute(select(InventorySnapshotItem).where(InventorySnapshotItem.snapshot_id == snapshot_id)).scalars():
        if it.product_id is None:
            devices.add(it.device_id)
        else:
            installs.setdefault((it.device_id, it.product_id), set()).add(it.version)
    return devices, installs


def compare(db: Session, base_id: int, target_id: int) -> dict:
    """Diferencias entre dos inventarios (base = anterior, target = actual)."""
    base_dev, base_inst = _item_sets(db, base_id)
    tgt_dev, tgt_inst = _item_sets(db, target_id)
    added, removed, changed = [], [], []
    for key in tgt_inst.keys() - base_inst.keys():
        added.append({"device_id": key[0], "product_id": key[1], "versions": sorted(tgt_inst[key])})
    for key in base_inst.keys() - tgt_inst.keys():
        removed.append({"device_id": key[0], "product_id": key[1], "versions": sorted(base_inst[key])})
    for key in base_inst.keys() & tgt_inst.keys():
        if base_inst[key] != tgt_inst[key]:
            changed.append({"device_id": key[0], "product_id": key[1], "from": sorted(base_inst[key]),
                            "to": sorted(tgt_inst[key])})
    base_products = {k[1] for k in base_inst}
    tgt_products = {k[1] for k in tgt_inst}
    return {
        "devices_added": sorted(tgt_dev - base_dev),
        "devices_removed": sorted(base_dev - tgt_dev),
        "products_new": sorted(tgt_products - base_products),
        "products_gone": sorted(base_products - tgt_products),
        "installs_added": added,
        "installs_removed": removed,
        "versions_changed": changed,
    }


def previous_snapshot(db: Session, snap: InventorySnapshot) -> InventorySnapshot | None:
    return db.execute(select(InventorySnapshot).where(
        InventorySnapshot.period < snap.period, InventorySnapshot.status == "approved"
    ).order_by(InventorySnapshot.period.desc(), InventorySnapshot.version.desc()).limit(1)).scalar_one_or_none()


def period_of(dt: datetime) -> str:
    return dt.strftime("%Y-%m")
