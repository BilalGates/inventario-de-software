"""Catálogo de software, versiones, instalaciones, alias, fusiones y políticas de autorización."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.api.common import Page, export_response, not_found, paginate
from app.core.security import CurrentUser, Reader, Technician
from app.db import get_db, utcnow
from app.models import (
    Department,
    Device,
    InventoryChange,
    SoftwareAlias,
    SoftwareInstallation,
    SoftwarePolicy,
    SoftwareProduct,
    SoftwareVersion,
)
from app.models.software import AUTH_STATUSES, SOFTWARE_CATEGORIES
from app.services import audit
from app.services.alerts import evaluate_unauthorized, resolve_alerts
from app.services.normalization import name_key, publisher_key
from app.services.software import PolicyEvaluator

router = APIRouter(prefix="/api/software", tags=["Software"])

PRODUCT_FIELDS = ["name", "publisher", "category", "is_relevant", "authorization_status", "ens_classification", "notes"]


def _counts(db: Session, product_ids: list[int]) -> dict[int, tuple[int, int]]:
    if not product_ids:
        return {}
    rows = db.execute(
        select(SoftwareInstallation.product_id, func.count(func.distinct(SoftwareInstallation.device_id)),
               func.count(func.distinct(SoftwareInstallation.version_id)))
        .join(Device, Device.id == SoftwareInstallation.device_id)
        .where(SoftwareInstallation.product_id.in_(product_ids), SoftwareInstallation.present.is_(True),
               Device.status != "retired")
        .group_by(SoftwareInstallation.product_id)
    ).all()
    return {pid: (devs, vers) for pid, devs, vers in rows}


def _product(p: SoftwareProduct, counts: tuple[int, int] = (0, 0)) -> dict:
    return {"id": p.id, "name": p.name, "publisher": p.publisher, "category": p.category,
            "is_relevant": p.is_relevant, "authorization_status": p.authorization_status,
            "ens_classification": p.ens_classification, "notes": p.notes, "first_seen_at": p.first_seen_at,
            "last_seen_at": p.last_seen_at, "devices": counts[0], "versions": counts[1],
            "merged_into_id": p.merged_into_id}


def _catalog_query(q, status, category, relevant, department_id, device_id, seen_since, not_seen_since, installed):
    query = select(SoftwareProduct).where(SoftwareProduct.merged_into_id.is_(None))
    if q:
        like = f"%{q.strip()}%"
        query = query.where(or_(SoftwareProduct.name.ilike(like), SoftwareProduct.publisher.ilike(like)))
    if status:
        query = query.where(SoftwareProduct.authorization_status.in_(status.split(",")))
    if category:
        query = query.where(SoftwareProduct.category.in_(category.split(",")))
    if relevant is not None:
        query = query.where(SoftwareProduct.is_relevant.is_(relevant))
    if seen_since:
        query = query.where(SoftwareProduct.first_seen_at >= seen_since)
    if department_id or device_id or installed is not None:
        sub = (select(SoftwareInstallation.product_id).join(Device, Device.id == SoftwareInstallation.device_id)
               .where(SoftwareInstallation.present.is_(True), Device.status != "retired"))
        if department_id:
            sub = sub.where(Device.department_id == department_id)
        if device_id:
            sub = sub.where(Device.id == device_id)
        query = query.where(SoftwareProduct.id.in_(sub) if installed is not False else SoftwareProduct.id.not_in(sub))
    if not_seen_since:
        # dejaron de detectarse: tuvieron instalaciones y ninguna sigue presente
        present = select(SoftwareInstallation.product_id).where(SoftwareInstallation.present.is_(True))
        gone = select(SoftwareInstallation.product_id).where(SoftwareInstallation.removed_at >= not_seen_since)
        query = query.where(SoftwareProduct.id.in_(gone), SoftwareProduct.id.not_in(present))
    return query


@router.get("")
def list_products(page: Page = Depends(), q: str | None = None, status: str | None = None,
                  category: str | None = None, relevant: bool | None = None, department_id: int | None = None,
                  device_id: int | None = None, seen_since: datetime | None = None,
                  not_seen_since: datetime | None = None, installed: bool | None = None,
                  db: Session = Depends(get_db), _: CurrentUser = Reader):
    query = _catalog_query(q, status, category, relevant, department_id, device_id, seen_since, not_seen_since,
                           installed)
    inst_count = (select(func.count(func.distinct(SoftwareInstallation.device_id)))
                  .where(SoftwareInstallation.product_id == SoftwareProduct.id, SoftwareInstallation.present.is_(True))
                  .correlate(SoftwareProduct).scalar_subquery())
    sortable = {"name": SoftwareProduct.name, "publisher": SoftwareProduct.publisher,
                "first_seen_at": SoftwareProduct.first_seen_at, "status": SoftwareProduct.authorization_status,
                "devices": inst_count}
    rows, total = paginate(db, query, page, sortable, inst_count.desc())
    products = [r[0] for r in rows]
    counts = _counts(db, [p.id for p in products])
    return {"total": total, "items": [_product(p, counts.get(p.id, (0, 0))) for p in products]}


@router.get("/export")
def export_products(format: str = Query("xlsx", pattern="^(csv|xlsx)$"), q: str | None = None,
                    status: str | None = None, category: str | None = None, relevant: bool | None = None,
                    department_id: int | None = None, db: Session = Depends(get_db), user: CurrentUser = Reader):
    query = _catalog_query(q, status, category, relevant, department_id, None, None, None,
                           True if department_id else None).order_by(SoftwareProduct.name)
    products = db.execute(query).scalars().all()
    counts = _counts(db, [p.id for p in products])
    versions: dict[int, list[str]] = {}
    for pid, ver in db.execute(select(SoftwareInstallation.product_id, SoftwareVersion.version).join(
            SoftwareVersion, SoftwareVersion.id == SoftwareInstallation.version_id)
            .where(SoftwareInstallation.present.is_(True)).distinct()):
        versions.setdefault(pid, []).append(ver or "?")
    rows = [{**_product(p, counts.get(p.id, (0, 0))), "version_list": sorted(versions.get(p.id, []))}
            for p in products]
    audit.record(db, user.upn, "export.software", "software_product", None, f"Exportación de {len(rows)} productos")
    db.commit()
    return export_response(rows, [("name", "Producto"), ("publisher", "Editor"), ("category", "Categoría"),
                                  ("authorization_status", "Autorización"), ("devices", "Dispositivos"),
                                  ("version_list", "Versiones"), ("ens_classification", "Clasificación ENS"),
                                  ("first_seen_at", "Primera detección"), ("last_seen_at", "Última detección"),
                                  ("notes", "Notas")], f"software_{utcnow():%Y%m%d}", format)


@router.get("/meta")
def software_meta(_: CurrentUser = Reader):
    return {"statuses": list(AUTH_STATUSES), "categories": list(SOFTWARE_CATEGORIES)}


@router.get("/{product_id}")
def product_detail(product_id: int, db: Session = Depends(get_db), _: CurrentUser = Reader):
    p = db.get(SoftwareProduct, product_id)
    if p is None:
        raise not_found("Producto")
    versions = db.execute(
        select(SoftwareVersion.id, SoftwareVersion.version, SoftwareVersion.first_seen_at,
               func.count(func.distinct(SoftwareInstallation.device_id)))
        .outerjoin(SoftwareInstallation, (SoftwareInstallation.version_id == SoftwareVersion.id)
                   & SoftwareInstallation.present.is_(True))
        .where(SoftwareVersion.product_id == product_id)
        .group_by(SoftwareVersion.id, SoftwareVersion.version, SoftwareVersion.first_seen_at)
        .order_by(SoftwareVersion.first_seen_at.desc())
    ).all()
    aliases = db.execute(select(SoftwareAlias).where(SoftwareAlias.product_id == product_id)).scalars().all()
    by_dept = db.execute(
        select(Department.name, func.count(func.distinct(Device.id)))
        .select_from(SoftwareInstallation).join(Device, Device.id == SoftwareInstallation.device_id)
        .outerjoin(Department, Department.id == Device.department_id)
        .where(SoftwareInstallation.product_id == product_id, SoftwareInstallation.present.is_(True),
               Device.status != "retired").group_by(Department.name)
    ).all()
    return {
        **_product(p, _counts(db, [p.id]).get(p.id, (0, 0))),
        "version_list": [{"id": v[0], "version": v[1] or None, "first_seen_at": v[2], "devices": v[3]}
                         for v in versions],
        "aliases": [{"id": a.id, "raw_name": a.raw_name, "publisher_key": a.raw_publisher_key, "origin": a.origin,
                     "created_by": a.created_by} for a in aliases],
        "by_department": [{"department": n or "Sin departamento", "devices": c} for n, c in by_dept],
        "policies": [_policy(pol) for pol in db.execute(select(SoftwarePolicy).where(
            SoftwarePolicy.product_id == product_id).order_by(SoftwarePolicy.id.desc())).scalars()],
    }


@router.get("/{product_id}/installations")
def product_installations(product_id: int, version: str | None = None, include_removed: bool = False,
                          db: Session = Depends(get_db), _: CurrentUser = Reader):
    p = db.get(SoftwareProduct, product_id)
    if p is None:
        raise not_found("Producto")
    query = (select(SoftwareInstallation, Device, SoftwareVersion.version)
             .join(Device, Device.id == SoftwareInstallation.device_id)
             .join(SoftwareVersion, SoftwareVersion.id == SoftwareInstallation.version_id)
             .where(SoftwareInstallation.product_id == product_id, Device.status != "retired"))
    if not include_removed:
        query = query.where(SoftwareInstallation.present.is_(True))
    if version is not None:
        query = query.where(SoftwareVersion.version == version)
    evaluator = PolicyEvaluator(db)
    items = []
    for inst, dev, ver in db.execute(query.order_by(Device.hostname)).all():
        status, origin = evaluator.evaluate(p, dev)
        items.append({"device_id": dev.id, "device": dev.display_name,
                      "department": dev.department.name if dev.department else None,
                      "user": dev.primary_user.upn if dev.primary_user else None, "version": ver or None,
                      "source": inst.source, "present": inst.present, "first_seen_at": inst.first_seen_at,
                      "last_seen_at": inst.last_seen_at, "removed_at": inst.removed_at,
                      "authorization_status": status, "authorization_origin": origin})
    return {"total": len(items), "items": items}


class ProductPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=300)
    category: str | None = None
    is_relevant: bool | None = None
    authorization_status: str | None = None
    ens_classification: str | None = Field(None, max_length=80)
    notes: str | None = Field(None, max_length=5000)
    reason: str | None = Field(None, max_length=1000)

    @model_validator(mode="after")
    def _valid(self):
        if self.category and self.category not in SOFTWARE_CATEGORIES:
            raise ValueError("Categoría no válida")
        if self.authorization_status and self.authorization_status not in AUTH_STATUSES:
            raise ValueError("Estado de autorización no válido")
        if self.authorization_status == "exception":
            raise ValueError("Las excepciones se crean como política con justificación y responsable")
        return self


def _update_product(db: Session, p: SoftwareProduct, data: dict, user: CurrentUser) -> None:
    before = audit.snapshot(p, PRODUCT_FIELDS)
    reason = data.pop("reason", None)
    status_changed = "authorization_status" in data and data["authorization_status"] != p.authorization_status
    for key, value in data.items():
        setattr(p, key, value)
    if status_changed:
        db.add(InventoryChange(change_type="authorization_changed", product_id=p.id, field="authorization_status",
                               old_value=before["authorization_status"], new_value=p.authorization_status,
                               source="manual", detected_at=utcnow()))
        if p.authorization_status != "unclassified":
            resolve_alerts(db, {f"new_software:{p.id}"}, by=user.upn, resolution="Clasificado")
    audit.record(db, user.upn, "software.update", "software_product", p.id, f"{p.name}: {reason or 'edición'}",
                 before=before, after=audit.snapshot(p, PRODUCT_FIELDS))


@router.patch("/{product_id}")
def update_product(product_id: int, body: ProductPatch, db: Session = Depends(get_db),
                   user: CurrentUser = Technician):
    p = db.get(SoftwareProduct, product_id)
    if p is None:
        raise not_found("Producto")
    _update_product(db, p, body.model_dump(exclude_unset=True), user)
    evaluate_unauthorized(db)
    db.commit()
    return _product(p, _counts(db, [p.id]).get(p.id, (0, 0)))


class BulkProductPatch(ProductPatch):
    product_ids: list[int] = Field(..., min_length=1, max_length=2000)


@router.post("/bulk-update")
def bulk_update(body: BulkProductPatch, db: Session = Depends(get_db), user: CurrentUser = Technician):
    data = body.model_dump(exclude_unset=True, exclude={"product_ids", "name"})
    if not data:
        raise HTTPException(422, "Nada que actualizar")
    products = db.execute(select(SoftwareProduct).where(SoftwareProduct.id.in_(body.product_ids))).scalars().all()
    for p in products:
        _update_product(db, p, dict(data), user)
    evaluate_unauthorized(db)
    db.commit()
    return {"updated": len(products)}


class MergeIn(BaseModel):
    source_ids: list[int] = Field(..., min_length=1)
    reason: str = Field(..., min_length=3, max_length=1000)


@router.post("/{product_id}/merge")
def merge_products(product_id: int, body: MergeIn, db: Session = Depends(get_db), user: CurrentUser = Technician):
    """Fusión manual: las instalaciones y alias de los productos origen pasan al destino.

    Los productos origen no se borran (quedan con merged_into_id) para conservar la trazabilidad.
    """
    target = db.get(SoftwareProduct, product_id)
    if target is None or target.merged_into_id:
        raise not_found("Producto destino")
    if product_id in body.source_ids:
        raise HTTPException(422, "El destino no puede estar entre los orígenes")
    sources = db.execute(select(SoftwareProduct).where(SoftwareProduct.id.in_(body.source_ids))).scalars().all()
    if len(sources) != len(set(body.source_ids)):
        raise not_found("Producto origen")
    for src in sources:
        for ver in db.execute(select(SoftwareVersion).where(SoftwareVersion.product_id == src.id)).scalars().all():
            target_ver = db.execute(select(SoftwareVersion).where(
                SoftwareVersion.product_id == target.id, SoftwareVersion.version == ver.version)).scalar_one_or_none()
            if target_ver is None:
                target_ver = SoftwareVersion(product_id=target.id, version=ver.version, first_seen_at=ver.first_seen_at)
                db.add(target_ver)
                db.flush()
            for inst in db.execute(select(SoftwareInstallation).where(
                    SoftwareInstallation.version_id == ver.id)).scalars().all():
                clash = db.execute(select(SoftwareInstallation).where(
                    SoftwareInstallation.device_id == inst.device_id, SoftwareInstallation.product_id == target.id,
                    SoftwareInstallation.version_id == target_ver.id, SoftwareInstallation.source == inst.source,
                )).scalar_one_or_none()
                if clash:
                    clash.present = clash.present or inst.present
                    clash.first_seen_at = min(clash.first_seen_at, inst.first_seen_at)
                    clash.last_seen_at = max(clash.last_seen_at, inst.last_seen_at)
                    inst.present = False
                    inst.removed_at = inst.removed_at or utcnow()
                    inst.product_id, inst.version_id = src.id, ver.id
                else:
                    inst.product_id, inst.version_id = target.id, target_ver.id
        db.execute(update(SoftwareAlias).where(SoftwareAlias.product_id == src.id)
                   .values(product_id=target.id, origin="manual", created_by=user.upn))
        db.execute(update(SoftwarePolicy).where(SoftwarePolicy.product_id == src.id, SoftwarePolicy.active.is_(True))
                   .values(active=False, revoked_at=utcnow(), revoked_by=user.upn))
        src.merged_into_id = target.id
        if src.first_seen_at and (target.first_seen_at is None or src.first_seen_at < target.first_seen_at):
            target.first_seen_at = src.first_seen_at
    audit.record(db, user.upn, "software.merge", "software_product", target.id,
                 f"Fusión en {target.name}: {body.reason}", before={"sources": [s.id for s in sources]},
                 after={"target": target.id})
    evaluate_unauthorized(db)
    db.commit()
    return product_detail(target.id, db, user)


class AliasIn(BaseModel):
    raw_name: str = Field(..., min_length=1, max_length=300)
    raw_publisher: str | None = Field(None, max_length=200)


@router.post("/{product_id}/aliases", status_code=201)
def add_alias(product_id: int, body: AliasIn, db: Session = Depends(get_db), user: CurrentUser = Technician):
    """Regla manual: este nombre/editor se considerará siempre este producto en futuras sincronizaciones."""
    p = db.get(SoftwareProduct, product_id)
    if p is None:
        raise not_found("Producto")
    nk, pk = name_key(body.raw_name), publisher_key(body.raw_publisher)
    existing = db.execute(select(SoftwareAlias).where(SoftwareAlias.raw_name_key == nk,
                                                      SoftwareAlias.raw_publisher_key == pk)).scalar_one_or_none()
    if existing and existing.product_id != product_id:
        raise HTTPException(409, f"Ese nombre ya está asociado al producto {existing.product_id}; use la fusión")
    if existing is None:
        db.add(SoftwareAlias(product_id=p.id, raw_name=body.raw_name, raw_name_key=nk, raw_publisher_key=pk,
                             origin="manual", created_by=user.upn))
    audit.record(db, user.upn, "software.alias", "software_product", p.id, f"Alias '{body.raw_name}' -> {p.name}")
    db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- políticas
def _policy(pol: SoftwarePolicy) -> dict:
    now = utcnow()
    return {"id": pol.id, "product_id": pol.product_id, "product": pol.product.name if pol.product else None,
            "scope": pol.scope, "department_id": pol.department_id,
            "department": pol.department.name if pol.department else None, "device_id": pol.device_id,
            "device": pol.device.display_name if pol.device else None, "status": pol.status,
            "justification": pol.justification, "approved_by": pol.approved_by, "valid_from": pol.valid_from,
            "valid_until": pol.valid_until, "active": pol.active,
            "expired": bool(pol.valid_until and pol.valid_until <= now), "created_by": pol.created_by,
            "created_at": pol.created_at, "revoked_at": pol.revoked_at, "revoked_by": pol.revoked_by}


class PolicyIn(BaseModel):
    product_id: int
    scope: str = Field(..., pattern="^(global|department|device)$")
    department_id: int | None = None
    device_id: int | None = None
    status: str = Field(..., pattern="^(authorized|unauthorized|pending_review|exception)$")
    justification: str | None = Field(None, max_length=2000)
    approved_by: str | None = Field(None, max_length=255)
    valid_until: datetime | None = None

    @model_validator(mode="after")
    def _valid(self):
        if self.scope == "department" and not self.department_id:
            raise ValueError("Indique el departamento")
        if self.scope == "device" and not self.device_id:
            raise ValueError("Indique el dispositivo")
        if self.status == "exception":
            if self.scope == "global":
                raise ValueError("Una excepción se aplica a un departamento o dispositivo")
            if not (self.justification or "").strip() or not (self.approved_by or "").strip():
                raise ValueError("Una excepción exige justificación y responsable que la aprueba")
        if self.valid_until and self.valid_until <= utcnow():
            raise ValueError("La vigencia debe ser futura")
        return self


policies = APIRouter(prefix="/api/policies", tags=["Software"])


@policies.get("")
def list_policies(active: bool | None = True, status: str | None = None, product_id: int | None = None,
                  db: Session = Depends(get_db), _: CurrentUser = Reader):
    query = select(SoftwarePolicy).order_by(SoftwarePolicy.id.desc())
    if active is not None:
        query = query.where(SoftwarePolicy.active.is_(active))
    if status:
        query = query.where(SoftwarePolicy.status == status)
    if product_id:
        query = query.where(SoftwarePolicy.product_id == product_id)
    return [_policy(p) for p in db.execute(query.limit(2000)).scalars()]


@policies.post("", status_code=201)
def create_policy(body: PolicyIn, db: Session = Depends(get_db), user: CurrentUser = Technician):
    if db.get(SoftwareProduct, body.product_id) is None:
        raise not_found("Producto")
    if body.department_id and db.get(Department, body.department_id) is None:
        raise not_found("Departamento")
    if body.device_id and db.get(Device, body.device_id) is None:
        raise not_found("Dispositivo")
    # Una política activa por ámbito: la anterior se revoca (queda en el histórico).
    prev = db.execute(select(SoftwarePolicy).where(
        SoftwarePolicy.product_id == body.product_id, SoftwarePolicy.scope == body.scope,
        SoftwarePolicy.department_id.is_(body.department_id) if body.department_id is None
        else SoftwarePolicy.department_id == body.department_id,
        SoftwarePolicy.device_id.is_(body.device_id) if body.device_id is None
        else SoftwarePolicy.device_id == body.device_id,
        SoftwarePolicy.active.is_(True))).scalars().all()
    now = utcnow()
    for old in prev:
        old.active, old.revoked_at, old.revoked_by = False, now, user.upn
    pol = SoftwarePolicy(**body.model_dump(), created_by=user.upn, valid_from=now)
    db.add(pol)
    if body.scope == "global":
        product = db.get(SoftwareProduct, body.product_id)
        _update_product(db, product, {"authorization_status": body.status}, user)
    db.flush()
    audit.record(db, user.upn, "policy.create", "software_policy", pol.id,
                 f"{body.status} ({body.scope}) para producto {body.product_id}", after=body.model_dump())
    evaluate_unauthorized(db)
    db.commit()
    return _policy(pol)


@policies.post("/{policy_id}/revoke")
def revoke_policy(policy_id: int, db: Session = Depends(get_db), user: CurrentUser = Technician):
    pol = db.get(SoftwarePolicy, policy_id)
    if pol is None or not pol.active:
        raise not_found("Política activa")
    pol.active, pol.revoked_at, pol.revoked_by = False, utcnow(), user.upn
    audit.record(db, user.upn, "policy.revoke", "software_policy", pol.id, f"Revocada política {pol.id}",
                 before=_policy(pol))
    evaluate_unauthorized(db)
    db.commit()
    return _policy(pol)
