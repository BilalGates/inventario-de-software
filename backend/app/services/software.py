"""Catálogo de software: resolución de productos, versiones y autorización efectiva."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models import Device, SoftwareAlias, SoftwarePolicy, SoftwareProduct, SoftwareVersion
from app.services.normalization import classify, display_name, name_key, publisher_key, version_text


class ProductResolver:
    """Resuelve (nombre, editor, versión) -> producto canónico, con caché por ejecución.

    Orden: alias manual/auto exacto -> identidad (name_key, publisher_key) -> crear producto.
    Un producto nuevo nace 'unclassified': nunca se autoriza automáticamente.
    """

    def __init__(self, db: Session, now: datetime | None = None):
        self.db = db
        self.now = now or utcnow()
        self._products: dict[tuple[str, str], SoftwareProduct] = {}
        self._versions: dict[tuple[int, str], SoftwareVersion] = {}
        self.created: list[SoftwareProduct] = []

    def product(self, raw_name: str, raw_publisher: str | None, version: str | None) -> SoftwareProduct:
        nk = name_key(raw_name, version)
        pk = publisher_key(raw_publisher)
        cache_key = (nk, pk)
        if cache_key in self._products:
            return self._products[cache_key]
        alias = self.db.execute(
            select(SoftwareAlias).where(SoftwareAlias.raw_name_key == nk, SoftwareAlias.raw_publisher_key == pk)
        ).scalar_one_or_none()
        product = self.db.get(SoftwareProduct, alias.product_id) if alias else None
        if product is None:
            product = self.db.execute(
                select(SoftwareProduct).where(SoftwareProduct.name_key == nk, SoftwareProduct.publisher_key == pk)
            ).scalar_one_or_none()
        while product is not None and product.merged_into_id:
            product = self.db.get(SoftwareProduct, product.merged_into_id)
        if product is None:
            category = classify(raw_name, raw_publisher)
            product = SoftwareProduct(
                name=display_name(raw_name, version)[:300], publisher=(raw_publisher or None),
                name_key=nk, publisher_key=pk, category=category, is_relevant=category == "application",
                authorization_status="unclassified", first_seen_at=self.now, last_seen_at=self.now,
            )
            self.db.add(product)
            self.db.flush()
            self.db.add(SoftwareAlias(product_id=product.id, raw_name=raw_name[:300], raw_name_key=nk,
                                      raw_publisher_key=pk, origin="auto"))
            self.created.append(product)
        product.last_seen_at = self.now
        self._products[cache_key] = product
        return product

    def version(self, product: SoftwareProduct, raw_version: str | None) -> SoftwareVersion:
        ver = version_text(raw_version)
        key = (product.id, ver)
        if key not in self._versions:
            row = self.db.execute(
                select(SoftwareVersion).where(SoftwareVersion.product_id == product.id, SoftwareVersion.version == ver)
            ).scalar_one_or_none()
            if row is None:
                row = SoftwareVersion(product_id=product.id, version=ver, first_seen_at=self.now)
                self.db.add(row)
                self.db.flush()
            self._versions[key] = row
        return self._versions[key]


def active_policies_query(now: datetime):
    return select(SoftwarePolicy).where(
        SoftwarePolicy.active.is_(True),
        or_(SoftwarePolicy.valid_until.is_(None), SoftwarePolicy.valid_until > now),
    )


class PolicyEvaluator:
    """Autorización efectiva: dispositivo > departamento > global > estado del producto."""

    def __init__(self, db: Session, now: datetime | None = None):
        self.now = now or utcnow()
        self.by_device: dict[tuple[int, int], SoftwarePolicy] = {}
        self.by_dept: dict[tuple[int, int], SoftwarePolicy] = {}
        self.global_: dict[int, SoftwarePolicy] = {}
        for pol in db.execute(active_policies_query(self.now).order_by(SoftwarePolicy.id)).scalars():
            if pol.scope == "device" and pol.device_id:
                self.by_device[(pol.product_id, pol.device_id)] = pol
            elif pol.scope == "department" and pol.department_id:
                self.by_dept[(pol.product_id, pol.department_id)] = pol
            elif pol.scope == "global":
                self.global_[pol.product_id] = pol

    def evaluate(self, product: SoftwareProduct, device: Device | None) -> tuple[str, str]:
        """Devuelve (estado, origen)."""
        if device is not None:
            if (pol := self.by_device.get((product.id, device.id))) is not None:
                return pol.status, f"device:{pol.id}"
            if device.department_id and (pol := self.by_dept.get((product.id, device.department_id))) is not None:
                return pol.status, f"department:{pol.id}"
        if (pol := self.global_.get(product.id)) is not None:
            return pol.status, f"global:{pol.id}"
        return product.authorization_status, "product"
