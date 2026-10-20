"""Tareas de mantenimiento del catálogo.

    python -m app.maintenance renormalizar-software            # simulación: solo informa
    python -m app.maintenance renormalizar-software --apply    # aplica y lo registra en auditoría

renormalizar-software: vuelve a aplicar las reglas de normalización actuales a los productos
existentes (editor legible a partir del sujeto de certificado de las apps MSIX/AppX y
clasificación de paquetes de Windows como componentes del sistema). Nunca cambia la
categoría de un producto editado a mano por IT (según la auditoría).
"""
from __future__ import annotations

import argparse
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import session_scope
from app.models import AuditEvent, SoftwareAlias, SoftwareProduct
from app.services import audit
from app.services.normalization import classify, clean_publisher, publisher_key


def renormalize_software(db: Session, actor: str, apply: bool) -> dict:
    every = db.execute(select(SoftwareProduct)).scalars().all()
    products = [p for p in every if p.merged_into_id is None]
    # La clave (nombre, editor) es única también entre productos fusionados: el origen la conserva
    # para que las importaciones futuras se redirijan al destino.
    taken = {(p.name_key, p.publisher_key): p for p in every}
    report = {"publisher": 0, "category": 0, "collisions": [], "examples": []}
    edited = {int(i) for i in db.execute(select(AuditEvent.entity_id).where(
        AuditEvent.entity_type == "software_product", AuditEvent.action == "software.update")).scalars() if i}
    for p in products:
        # La categoría se calcula con el editor original: el sujeto de certificado es la señal de
        # paquete. Solo se recalculan categorías automáticas (producto nunca editado a mano).
        new_cat = p.category if p.id in edited else classify(p.name, p.publisher)
        if new_cat != p.category:
            report["category"] += 1
            if apply:
                p.category, p.is_relevant = new_cat, new_cat == "application"
        new_pk = publisher_key(p.publisher)
        if new_pk != p.publisher_key and p.publisher != clean_publisher(p.publisher):
            other = taken.get((p.name_key, new_pk))
            if other is not None and other.merged_into_id == p.id:
                if p.publisher == clean_publisher(p.publisher):
                    continue  # ya corregido en una pasada anterior
                # Ya fusionado en este: solo se corrige el editor visible; la clave limpia la tiene el
                # origen y el resolutor de productos lo redirige aquí.
                report["publisher"] += 1
                if apply:
                    p.publisher = clean_publisher(p.publisher)
            elif other is not None and other.id != p.id:
                report["collisions"].append({"id": p.id, "name": p.name, "with": other.id})
            else:
                old_pk = p.publisher_key
                if len(report["examples"]) < 10:
                    report["examples"].append(f"{p.name}: {p.publisher!r} -> {clean_publisher(p.publisher)!r}")
                report["publisher"] += 1
                if apply:
                    taken.pop((p.name_key, old_pk), None)
                    taken[(p.name_key, new_pk)] = p
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
