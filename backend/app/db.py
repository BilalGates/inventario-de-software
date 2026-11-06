"""Motor, sesiones y base declarativa."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import JSON as _JSON
from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


# JSON portable: jsonb en PostgreSQL (admite igualdad, necesaria para SELECT DISTINCT), JSON en el resto.
JSON = _JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


def utcnow() -> datetime:
    """Fechas siempre en UTC sin tzinfo (MySQL DATETIME no guarda zona)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_url(url: str) -> str:
    """Supabase y otros proveedores dan «postgres://» o «postgresql://»: se usa el controlador psycopg 3."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def make_engine(url: str, *, serverless: bool = False) -> Engine:
    """serverless=True (funciones de Vercel): sin pool propio, el pooler de Supabase reparte las conexiones."""
    url = normalize_url(url)
    kwargs: dict = {"future": True, "pool_pre_ping": True}
    if url.startswith("sqlite"):
        # timeout: espera al bloqueo en lugar de fallar enseguida ("database is locked").
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
    elif serverless:
        kwargs["poolclass"] = NullPool
    else:
        kwargs.update(pool_recycle=3600, pool_size=5, max_overflow=5)
    if url.startswith("postgresql+psycopg"):
        # El pooler en modo transacción (puerto 6543) no admite sentencias preparadas.
        kwargs["connect_args"] = {"prepare_threshold": None, "connect_timeout": 15}
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _):  # pragma: no cover - trivial
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
            if ":memory:" not in url and "mode=memory" not in url:
                # WAL: la web puede leer mientras el worker procesa una sincronización larga.
                dbapi_conn.execute("PRAGMA journal_mode=WAL")
    return engine


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        s = get_settings()
        _engine = make_engine(s.database_url, serverless=s.serverless)
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def configure(engine: Engine) -> None:
    """Permite a los tests inyectar su propio motor."""
    global _engine, _SessionLocal
    _engine = engine
    _SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


def session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    session = session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    """Dependencia FastAPI: una sesión por petición, commit explícito en los servicios."""
    session = session_factory()()
    try:
        yield session
    finally:
        session.close()
