from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import JSON, Base, utcnow


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    manager_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", use_alter=True))
    cost_center: Mapped[str | None] = mapped_column(String(50))
    attributes: Mapped[dict | None] = mapped_column(JSON)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    legacy_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    manager: Mapped["User | None"] = relationship(foreign_keys=[manager_id])


class User(Base):
    """Persona de la organización. Si tiene `role`, además puede entrar en la aplicación."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    upn: Mapped[str] = mapped_column(String(255), unique=True)
    display_name: Mapped[str | None] = mapped_column(String(200))
    entra_object_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
    role: Mapped[str | None] = mapped_column(String(20))  # admin | technician | auditor | None
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(String(30), default="manual")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)
    # Foto de perfil de Microsoft 365 (96x96), en caché; photo_checked_at también se rellena si no tiene.
    photo: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    photo_type: Mapped[str | None] = mapped_column(String(40))
    photo_checked_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    department: Mapped[Department | None] = relationship(foreign_keys=[department_id])


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict | list | str | int | bool | None] = mapped_column(JSON)
    updated_by: Mapped[str | None] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
