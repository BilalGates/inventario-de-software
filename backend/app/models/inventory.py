from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, utcnow

RUN_STATUSES = ("queued", "running", "succeeded", "partial", "failed", "cancelled")


class InventorySource(Base):
    __tablename__ = "inventory_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)  # intune | panda | intune_csv | manual
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(20))  # api | file
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Prioridad para resolver conflictos de atributos: menor número = más fiable.
    priority: Mapped[int] = mapped_column(Integer, default=100)
    config: Mapped[dict | None] = mapped_column(JSON)  # nunca secretos
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(Text)


class InventoryRun(Base):
    """Ejecución de un conector (o importación de fichero). Es también la cola del worker."""

    __tablename__ = "inventory_runs"
    __table_args__ = (
        Index("ix_inventory_runs_status", "status", "requested_at"),
        Index("ix_inventory_runs_source_hash", "source_id", "batch_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("inventory_sources.id"))
    trigger: Mapped[str] = mapped_column(String(20))  # manual | schedule | watcher | upload | retry
    status: Mapped[str] = mapped_column(String(20), default="queued")
    requested_by: Mapped[str | None] = mapped_column(String(255))
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    # complete = todas las consultas esenciales terminaron bien; solo entonces se infieren bajas.
    is_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    retry_of_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_runs.id"))
    period: Mapped[str | None] = mapped_column(String(7))
    batch_hash: Mapped[str | None] = mapped_column(String(64))
    params: Mapped[dict | None] = mapped_column(JSON)  # p.ej. {"device_id": 3} para un fichero Panda
    stats: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    log: Mapped[list | None] = mapped_column(JSON)

    source: Mapped[InventorySource] = relationship()


class InventoryObservation(Base):
    """Dato original tal como lo entregó la fuente (para auditoría y reprocesado)."""

    __tablename__ = "inventory_observations"
    __table_args__ = (
        UniqueConstraint("run_id", "entity", "external_key", name="uq_inventory_observations_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("inventory_runs.id"), index=True)
    entity: Mapped[str] = mapped_column(String(20))  # device | software | install
    external_key: Mapped[str] = mapped_column(String(190))
    payload: Mapped[dict] = mapped_column(JSON)
    payload_hash: Mapped[str] = mapped_column(String(64))
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class InventoryChange(Base):
    __tablename__ = "inventory_changes"
    __table_args__ = (
        Index("ix_inventory_changes_detected", "detected_at"),
        Index("ix_inventory_changes_device", "device_id"),
        Index("ix_inventory_changes_product", "product_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_runs.id"))
    change_type: Mapped[str] = mapped_column(String(40))
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id"))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("software_products.id"))
    field: Mapped[str | None] = mapped_column(String(60))
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(30))
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    device = relationship("Device")
    product = relationship("SoftwareProduct")


class InventorySnapshot(Base):
    """Fotografía mensual. Generarla (draft) y aprobarla (approved) son pasos separados."""

    __tablename__ = "inventory_snapshots"
    __table_args__ = (UniqueConstraint("period", "version", name="uq_inventory_snapshots_pv"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    period: Mapped[str] = mapped_column(String(7))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | approved | rejected
    is_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    coverage: Mapped[dict | None] = mapped_column(JSON)  # fuentes, runs, completitud
    totals: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    created_by: Mapped[str | None] = mapped_column(String(255))
    reviewed_by: Mapped[str | None] = mapped_column(String(255))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    review_notes: Mapped[str | None] = mapped_column(Text)


class InventorySnapshotItem(Base):
    __tablename__ = "inventory_snapshot_items"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "device_id", "product_id", "version", name="uq_inventory_snapshot_items_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("inventory_snapshots.id", ondelete="CASCADE"), index=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"))
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("software_products.id"))  # NULL = fila del dispositivo
    version: Mapped[str] = mapped_column(String(150), default="")
    authorization_status: Mapped[str | None] = mapped_column(String(20))


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alerts_status", "status", "severity"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # dedup_key evita duplicar la misma incidencia abierta en reejecuciones.
    dedup_key: Mapped[str] = mapped_column(String(190), index=True)
    alert_type: Mapped[str] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(10))  # info | warning | critical
    status: Mapped[str] = mapped_column(String(15), default="open")  # open | acknowledged | resolved
    title: Mapped[str] = mapped_column(String(300))
    detail: Mapped[str | None] = mapped_column(Text)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id"))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("software_products.id"))
    run_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_runs.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    resolved_by: Mapped[str | None] = mapped_column(String(255))
    resolution: Mapped[str | None] = mapped_column(Text)

    device = relationship("Device")
    product = relationship("SoftwareProduct")


class ReviewCase(Base):
    """Caso de conciliación ambiguo: no se fusiona nada automáticamente."""

    __tablename__ = "review_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_type: Mapped[str] = mapped_column(String(40))  # device_match | software_merge
    status: Mapped[str] = mapped_column(String(15), default="open")  # open | resolved | dismissed
    dedup_key: Mapped[str] = mapped_column(String(190), index=True)
    summary: Mapped[str] = mapped_column(String(400))
    data: Mapped[dict | None] = mapped_column(JSON)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_runs.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    resolved_by: Mapped[str | None] = mapped_column(String(255))
    resolution: Mapped[str | None] = mapped_column(Text)
