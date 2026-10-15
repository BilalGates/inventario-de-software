from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
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

DEVICE_STATUSES = ("active", "in_stock", "repair", "retired", "lost")


class DeviceType(Base):
    __tablename__ = "device_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(80))


class Device(Base):
    """Activo inventariable con identidad persistente (uid), independiente del hostname."""

    __tablename__ = "devices"
    __table_args__ = (
        Index("ix_devices_status_dept", "status", "department_id"),
        Index("ix_devices_serial", "serial_number"),
        Index("ix_devices_hostname", "hostname_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uid: Mapped[str] = mapped_column(String(36), unique=True, default=lambda: str(uuid.uuid4()))
    hostname: Mapped[str | None] = mapped_column(String(150))
    hostname_key: Mapped[str | None] = mapped_column(String(150))
    serial_number: Mapped[str | None] = mapped_column(String(120))
    manufacturer: Mapped[str | None] = mapped_column(String(120))
    model: Mapped[str | None] = mapped_column(String(160))
    os_name: Mapped[str | None] = mapped_column(String(80))
    os_version: Mapped[str | None] = mapped_column(String(80))
    device_type_id: Mapped[int | None] = mapped_column(ForeignKey("device_types.id"))
    status: Mapped[str] = mapped_column(String(20), default="active")
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
    primary_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    location: Mapped[str | None] = mapped_column(String(150))
    notes: Mapped[str | None] = mapped_column(Text)

    processor: Mapped[str | None] = mapped_column(String(200))
    ram_bytes: Mapped[int | None] = mapped_column(BigInteger)
    storage_total_bytes: Mapped[int | None] = mapped_column(BigInteger)
    storage_free_bytes: Mapped[int | None] = mapped_column(BigInteger)
    mac_wifi: Mapped[str | None] = mapped_column(String(40))
    mac_ethernet: Mapped[str | None] = mapped_column(String(40))
    encrypted: Mapped[bool | None] = mapped_column(Boolean)  # None = desconocido
    compliance_state: Mapped[str | None] = mapped_column(String(40))
    management_state: Mapped[str | None] = mapped_column(String(40))
    ownership: Mapped[str | None] = mapped_column(String(30))
    enrolled_at: Mapped[datetime | None] = mapped_column(DateTime)
    source_last_sync_at: Mapped[datetime | None] = mapped_column(DateTime)  # último check-in según la fuente

    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime)  # última vez visto en una sync completa
    last_seen_source: Mapped[str | None] = mapped_column(String(30))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime)
    purchase_date: Mapped[datetime | None] = mapped_column(DateTime)
    cost: Mapped[str | None] = mapped_column(String(30))
    legacy_equipo_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    # Procedencia por atributo: {"serial_number": {"source": "intune", "at": "..."}}
    field_sources: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    device_type: Mapped[DeviceType | None] = relationship()
    department = relationship("Department")
    primary_user = relationship("User")
    external_ids: Mapped[list["DeviceExternalId"]] = relationship(back_populates="device", cascade="all, delete-orphan")

    @property
    def display_name(self) -> str:
        return self.hostname or self.serial_number or self.uid[:8]


class DeviceExternalId(Base):
    """Identificadores de las fuentes. Un valor solo puede pertenecer a un dispositivo."""

    __tablename__ = "device_external_ids"
    __table_args__ = (UniqueConstraint("source", "id_type", "value", name="uq_device_external_ids_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(30))  # intune | panda | legacy | manual
    id_type: Mapped[str] = mapped_column(String(40))  # intune_device_id | entra_device_id | hostname | ...
    value: Mapped[str] = mapped_column(String(190))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    device: Mapped[Device] = relationship(back_populates="external_ids")


class DeviceAssignment(Base):
    """Historial de asignaciones (departamento / usuario). La vigente tiene ended_at NULL."""

    __tablename__ = "device_assignments"
    __table_args__ = (Index("ix_device_assignments_device_open", "device_id", "ended_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"))
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)
    reason: Mapped[str | None] = mapped_column(String(500))
    actor: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(30), default="manual")

    department = relationship("Department")
    user = relationship("User")
