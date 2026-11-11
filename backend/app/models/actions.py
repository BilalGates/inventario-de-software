from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import JSON, Base, utcnow

REMOTE_ACTION_KINDS = ("notify", "uninstall")
# notify: sent | failed. uninstall: sent → running → succeeded | failed | manual_required | expired.
REMOTE_ACTION_STATUSES = ("sent", "running", "succeeded", "failed", "manual_required", "expired")


class RemoteAction(Base):
    """Acción lanzada desde el inventario sobre un equipo: aviso por correo o desinstalación en Intune.

    Siempre la pide un técnico (nunca automática) y queda en auditoría; aquí se sigue su resultado.
    """

    __tablename__ = "remote_actions"
    __table_args__ = (Index("ix_remote_actions_kind_status", "kind", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="sent")
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id"), index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("software_products.id"), index=True)
    alert_id: Mapped[int | None] = mapped_column(ForeignKey("alerts.id"), index=True)
    recipient: Mapped[str | None] = mapped_column(String(255))
    requested_by: Mapped[str] = mapped_column(String(255))
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    reason: Mapped[str | None] = mapped_column(Text)
    # Salida del script, error de Graph, asunto del correo…
    detail: Mapped[dict | None] = mapped_column(JSON)
    # Id del script de Intune (desinstalación) o del mensaje.
    graph_ref: Mapped[str | None] = mapped_column(String(120))

    device = relationship("Device")
    product = relationship("SoftwareProduct")
