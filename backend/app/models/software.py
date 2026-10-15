from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
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

SOFTWARE_CATEGORIES = ("application", "system_component", "driver", "runtime", "update", "unknown")
AUTH_STATUSES = ("authorized", "unauthorized", "pending_review", "exception", "unclassified")


class SoftwareProduct(Base):
    """Producto del catálogo global: existe una sola vez aunque esté en muchos equipos."""

    __tablename__ = "software_products"
    __table_args__ = (
        UniqueConstraint("name_key", "publisher_key", name="uq_software_products_identity"),
        Index("ix_software_products_auth", "authorization_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(300))
    publisher: Mapped[str | None] = mapped_column(String(200))
    name_key: Mapped[str] = mapped_column(String(190))
    publisher_key: Mapped[str] = mapped_column(String(120), default="")
    category: Mapped[str] = mapped_column(String(30), default="unknown")
    is_relevant: Mapped[bool] = mapped_column(Boolean, default=True)
    # Estado global; las políticas por departamento/dispositivo lo refinan.
    authorization_status: Mapped[str] = mapped_column(String(20), default="unclassified")
    ens_classification: Mapped[str | None] = mapped_column(String(80))
    notes: Mapped[str | None] = mapped_column(Text)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime)
    merged_into_id: Mapped[int | None] = mapped_column(ForeignKey("software_products.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    aliases: Mapped[list["SoftwareAlias"]] = relationship(back_populates="product", foreign_keys="SoftwareAlias.product_id")


class SoftwareAlias(Base):
    """Nombre/editor tal como llega de una fuente -> producto canónico.

    Las reglas `auto` las crea el normalizador; las `manual` las crea IT y prevalecen.
    """

    __tablename__ = "software_aliases"
    __table_args__ = (UniqueConstraint("raw_name_key", "raw_publisher_key", name="uq_software_aliases_raw"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("software_products.id"), index=True)
    raw_name: Mapped[str] = mapped_column(String(300))
    raw_name_key: Mapped[str] = mapped_column(String(190))
    raw_publisher_key: Mapped[str] = mapped_column(String(120), default="")
    origin: Mapped[str] = mapped_column(String(10), default="auto")  # auto | manual
    created_by: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    product: Mapped[SoftwareProduct] = relationship(back_populates="aliases", foreign_keys=[product_id])


class SoftwareVersion(Base):
    __tablename__ = "software_versions"
    __table_args__ = (UniqueConstraint("product_id", "version", name="uq_software_versions_pv"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("software_products.id"), index=True)
    version: Mapped[str] = mapped_column(String(150))  # texto, nunca numérico ('' = desconocida)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SoftwareInstallation(Base):
    """Estado operativo: producto+versión presente en un dispositivo según una fuente."""

    __tablename__ = "software_installations"
    __table_args__ = (
        UniqueConstraint("device_id", "product_id", "version_id", "source", name="uq_software_installations_key"),
        Index("ix_software_installations_product_present", "product_id", "present"),
        Index("ix_software_installations_device_present", "device_id", "present"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("software_products.id"))
    version_id: Mapped[int] = mapped_column(ForeignKey("software_versions.id"))
    source: Mapped[str] = mapped_column(String(30))
    present: Mapped[bool] = mapped_column(Boolean, default=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_run_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_runs.id"))
    install_date: Mapped[datetime | None] = mapped_column(DateTime)

    device = relationship("Device")
    product: Mapped[SoftwareProduct] = relationship()
    version: Mapped[SoftwareVersion] = relationship()


class SoftwarePolicy(Base):
    """Autorización por ámbito. Precedencia: dispositivo > departamento > global.

    status = exception exige justificación y aprobador; puede caducar (valid_until).
    """

    __tablename__ = "software_policies"
    __table_args__ = (Index("ix_software_policies_lookup", "product_id", "scope", "active"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("software_products.id"))
    scope: Mapped[str] = mapped_column(String(20))  # global | department | device
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id"))
    status: Mapped[str] = mapped_column(String(20))
    justification: Mapped[str | None] = mapped_column(Text)
    approved_by: Mapped[str | None] = mapped_column(String(255))
    valid_from: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoked_by: Mapped[str | None] = mapped_column(String(255))

    product: Mapped[SoftwareProduct] = relationship()
    department = relationship("Department")
    device = relationship("Device")
