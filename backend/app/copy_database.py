"""Copia íntegra de una base de Asserta Inventario a otra (p. ej. SQLite local -> PostgreSQL de Supabase).

    python -m app.copy_database --source sqlite:///C:/ruta/inventario.db --target postgresql://...:5432/postgres
    python -m app.copy_database ... --check     # solo comprueba, no escribe

Requisitos del destino: esquema creado con «alembic upgrade head» (misma revisión que el origen)
y sin datos. Se copian todas las tablas tal cual (ids, fechas, hashes de auditoría), de modo que la
cadena de auditoría sigue siendo verificable y los enlaces no cambian.

Pasos: comprobaciones -> copia por tablas en orden de dependencias (las claves que apuntan a la propia
tabla se rellenan en una segunda pasada) -> ajuste de las secuencias de PostgreSQL -> verificación de
recuentos y de la cadena de auditoría.
"""
from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable

from sqlalchemy import Integer, String, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - registra todas las tablas
from app.db import Base, make_engine
from app.services.audit import verify_chain

CHUNK = 500
# Lo que la API escribe sola en una base recién creada: datos de referencia al arrancar y una fila
# en «users» por cada inicio de sesión. Se borra en el destino y se copia del origen.
REPLACEABLE = ("users", "app_settings", "inventory_sources", "device_types")
# Con --reset se vacía el destino entero, pero solo si no contiene inventario real.
INVENTORY_TABLES = ("devices", "software_products", "inventory_snapshots")


def _revision(engine: Engine) -> str | None:
    with engine.connect() as c:
        try:
            return c.execute(text("SELECT version_num FROM alembic_version")).scalar()
        except Exception:  # noqa: BLE001 - sin tabla de Alembic
            return None


def _counts(engine: Engine) -> dict[str, int]:
    with engine.connect() as c:
        return {t.name: c.execute(select(func.count()).select_from(t)).scalar() or 0 for t in Base.metadata.sorted_tables}


def check(source: Engine, target: Engine, reset: bool = False) -> list[str]:
    """Problemas que impiden copiar. Lista vacía = se puede copiar.

    reset=True admite un destino con datos de prueba (p. ej. ejecuciones del worker sobre la base
    vacía): se borrarán. Nunca si el destino ya tiene equipos, software o inventarios mensuales."""
    problems = []
    src_rev, dst_rev = _revision(source), _revision(target)
    if dst_rev is None:
        problems.append("El destino no tiene esquema: ejecute antes «alembic upgrade head» contra él.")
    elif src_rev and src_rev != dst_rev:
        problems.append(f"Revisiones distintas: origen {src_rev}, destino {dst_rev}. Actualice ambas a la misma.")
    if dst_rev is not None:
        busy = {k: v for k, v in _counts(target).items() if v}
        # La API crea datos de referencia al arrancar y una fila en «users» por cada inicio de sesión:
        # se aceptan (y se sustituyen por los del origen) solo si el destino no tiene nada más.
        if reset:
            real = {k: v for k, v in busy.items() if k in INVENTORY_TABLES}
            if real:
                problems.append("El destino tiene inventario real y no se vaciará: "
                                f"{', '.join(f'{k}={v}' for k, v in real.items())}.")
        elif set(busy) - set(REPLACEABLE):
            problems.append(f"El destino ya tiene datos: {', '.join(f'{k}={v}' for k, v in busy.items())}. "
                            "Si son solo pruebas (p. ej. el worker ejecutado antes de copiar), use --reset.")
    # PostgreSQL hace cumplir la longitud de VARCHAR; SQLite no.
    with source.connect() as c:
        for table in Base.metadata.sorted_tables:
            for col in table.columns:
                if isinstance(col.type, String) and col.type.length:
                    n = c.execute(select(func.count()).select_from(table)
                                  .where(func.length(col) > col.type.length)).scalar()
                    if n:
                        problems.append(f"{table.name}.{col.name}: {n} valores superan {col.type.length} caracteres.")
    return problems


def _rows(conn, table, offset: int) -> list[dict]:
    pk = list(table.primary_key.columns)
    q = select(table).order_by(*pk).limit(CHUNK).offset(offset)
    return [dict(r._mapping) for r in conn.execute(q)]


def _batches(conn, table) -> Iterable[list[dict]]:
    offset = 0
    while True:
        rows = _rows(conn, table, offset)
        if not rows:
            return
        yield rows
        offset += len(rows)


def copy(source: Engine, target: Engine, log=print, reset: bool = False) -> dict[str, int]:
    copied: dict[str, int] = {}
    with source.connect() as src, target.begin() as dst:
        # reset: todo el destino (de hijas a padres); si no, solo lo que la API crea sola.
        tables = reversed(Base.metadata.sorted_tables) if reset else (Base.metadata.tables[n] for n in REPLACEABLE)
        for table in tables:
            dst.execute(table.delete())
        for table in Base.metadata.sorted_tables:
            self_fks = [fk.parent.name for fk in table.foreign_keys if fk.column.table is table]
            pk = [c.name for c in table.primary_key.columns]
            n = 0
            deferred: list[dict] = []
            for rows in _batches(src, table):
                if self_fks:
                    for r in rows:
                        later = {k: r[k] for k in self_fks if r[k] is not None}
                        if later:
                            deferred.append({**{k: r[k] for k in pk}, **later})
                            r.update({k: None for k in later})
                dst.execute(table.insert(), rows)
                n += len(rows)
            for r in deferred:
                where = [table.c[k] == r[k] for k in pk]
                dst.execute(table.update().where(*where).values({k: r[k] for k in self_fks if k in r}))
            copied[table.name] = n
            if n:
                log(f"  {table.name}: {n}")
        if target.dialect.name == "postgresql":
            for table in Base.metadata.sorted_tables:
                pkcols = list(table.primary_key.columns)
                if len(pkcols) == 1 and isinstance(pkcols[0].type, Integer) and pkcols[0].autoincrement is not False:
                    col = pkcols[0].name
                    dst.execute(text(
                        f"SELECT setval(pg_get_serial_sequence('{table.name}', '{col}'), "
                        f"COALESCE((SELECT MAX({col}) FROM {table.name}), 0) + 1, false)"))
    return copied


def verify(source: Engine, target: Engine) -> list[str]:
    problems = [f"{t}: origen {a}, destino {b}" for t, (a, b) in
                ((t, (n, _counts(target)[t])) for t, n in _counts(source).items()) if a != b]
    with Session(target) as db:
        chain = verify_chain(db)
    if not chain.get("valid"):
        problems.append(f"Cadena de auditoría rota en el evento #{chain.get('broken_event_id')}.")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Copia una base de Asserta Inventario a otra (p. ej. a Supabase).")
    parser.add_argument("--source", required=True, help="URL de origen, p. ej. sqlite:///C:/…/inventario.db")
    parser.add_argument("--target", required=True, help="URL de destino (Supabase: pooler de sesión, puerto 5432)")
    parser.add_argument("--check", action="store_true", help="Solo comprobar, sin escribir")
    parser.add_argument("--reset", action="store_true",
                        help="Vaciar antes el destino (solo si no tiene equipos, software ni inventarios mensuales)")
    args = parser.parse_args(argv)
    source, target = make_engine(args.source), make_engine(args.target)
    print("Comprobando…")
    problems = check(source, target, reset=args.reset)
    if problems:
        print("No se puede copiar:\n- " + "\n- ".join(problems))
        return 1
    if args.check:
        print("Todo correcto: se puede copiar.")
        return 0
    print("Vaciando el destino y copiando…" if args.reset else "Copiando…")
    copy(source, target, reset=args.reset)
    print("Verificando…")
    problems = verify(source, target)
    if problems:
        print("Copia con diferencias:\n- " + "\n- ".join(problems))
        return 2
    print("Copia completa y verificada (recuentos y cadena de auditoría).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
