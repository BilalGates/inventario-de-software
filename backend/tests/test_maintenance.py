from sqlalchemy import select

from app.maintenance import renormalize_software
from app.models import AuditEvent, SoftwareAlias, SoftwareProduct

DN = "CN=Microsoft Corporation, O=Microsoft Corporation, L=Redmond, S=Washington, C=US"


def _product(db, name, publisher, category="application"):
    from app.services.normalization import name_key
    p = SoftwareProduct(name=name, publisher=publisher, name_key=name_key(name), publisher_key=publisher.casefold(),
                        category=category, is_relevant=category == "application")
    db.add(p)
    db.flush()
    db.add(SoftwareAlias(product_id=p.id, raw_name=name, raw_name_key=p.name_key, raw_publisher_key=p.publisher_key,
                         origin="auto"))
    return p


def test_renormalize_dry_run_then_apply(db):
    pkg = _product(db, "Microsoft.BingNews", DN)
    teams = _product(db, "MSTeams", DN)
    manual = _product(db, "Microsoft.Copilot", DN, category="runtime")  # clasificado a mano: no se toca
    db.commit()

    report = renormalize_software(db, "it@local", apply=False)
    assert report["publisher"] == 3 and report["category"] == 1
    assert db.get(SoftwareProduct, pkg.id).publisher == DN  # simulación: nada cambia

    renormalize_software(db, "it@local", apply=True)
    pkg, teams, manual = (db.get(SoftwareProduct, i) for i in (pkg.id, teams.id, manual.id))
    assert pkg.publisher == "Microsoft Corporation" and pkg.publisher_key == "microsoft"
    assert pkg.category == "system_component" and not pkg.is_relevant
    assert teams.category == "application" and teams.publisher == "Microsoft Corporation"
    assert manual.category == "runtime"
    alias = db.execute(select(SoftwareAlias).where(SoftwareAlias.product_id == pkg.id)).scalar_one()
    assert alias.raw_publisher_key == "microsoft"
    assert db.execute(select(AuditEvent).where(AuditEvent.action == "software.renormalize")).scalar_one()


def test_renormalize_reports_collisions(db):
    _product(db, "Paint", "Microsoft Corporation").publisher_key = "microsoft"
    dup = _product(db, "Paint", DN)
    db.commit()
    report = renormalize_software(db, "it@local", apply=True)
    assert report["collisions"] == [{"id": dup.id, "name": "Paint", "with": report["collisions"][0]["with"]}]
    assert db.get(SoftwareProduct, dup.id).publisher == DN  # no se fusiona solo
