"""Tareas de mantenimiento del catálogo.

    python -m app.maintenance renormalizar-software            # simulación: solo informa
    python -m app.maintenance renormalizar-software --apply    # aplica y lo registra en auditoría

renormalizar-software: vuelve a aplicar las reglas de normalización actuales a los productos
existentes (editor legible a partir del sujeto de certificado de las apps MSIX/AppX y
clasificación de paquetes de Windows como componentes del sistema). Las categorías solo
pasan de "application" a otra: nunca se deshace una clasificación hecha por IT.
"""
from __future__ import annotations

import argparse
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import session_scope
from app.models import SoftwareAlias, SoftwareProduct
from app.services import audit
from app.services.normalization import classify, clean_publisher, publisher_key


def renormalize_software(db: Session, actor: str, apply: bool) -> dict:
    products = db.execute(select(SoftwareProduct).where(SoftwareProduct.merged_into_id.is_(None))).scalars().all()
    taken = {(p.name_key, p.publisher_key): p.id for p in products}
    report = {"publisher": 0, "category": 0, "collisions": [], "examples": []}
    for p in products:
        # La categoría se calcula con el editor original: el sujeto de certificado es la señal de paquete.
        new_cat = classify(p.name, p.publisher) if p.category == "application" else p.category
        if new_cat != p.category:
            report["category"] += 1
            if apply:
                p.category, p.is_relevant = new_cat, False
        new_pk = publisher_key(p.publisher)
        if new_pk != p.publisher_key:
            other = taken.get((p.name_key, new_pk))
            if other and other != p.id:
                report["collisions"].append({"id": p.id, "name": p.name, "with": other})
            else:
                old_pk = p.publisher_key
                if len(report["examples"]) < 10:
                    report["examples"].append(f"{p.name}: {p.publisher!r} -> {clean_publisher(p.publisher)!r}")
                report["publisher"] += 1
                if apply:
                    taken.pop((p.name_key, old_pk), None)
                    taken[(p.name_key, new_pk)] = p.id
                    for alias in db.execute(select(SoftwareAlias).where(
                            SoftwareAlias.product_id == p.id, SoftwareAlias.raw_publisher_key == old_pk)).scalars():
                        alias.raw_publisher_key = new_pk
                    p.publisher, p.publisher_key = clean_publisher(p.publisher), new_pk
    if apply:
        audit.record(db, actor, "software.renormalize", "software_product", None,
                     f"Renormalización del catálogo: {report['publisher']} editores, {report['category']} categorías",
                     after={k: v for k, v in report.items() if k != "examples"})
        db.commit()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("tarea", choices=["renormalizar-software"])
    parser.add_argument("--apply", action="store_true", help="aplicar los cambios (por defecto solo simula)")
    parser.add_argument("--actor", default="administrador@local")
    args = parser.parse_args()
    with session_scope() as db:
        report = renormalize_software(db, args.actor, args.apply)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("Aplicado." if args.apply else "Simulación: no se ha cambiado nada (use --apply).")


if __name__ == "__main__":
    main()
