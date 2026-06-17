"""
Capa de acceso a datos — SQLAlchemy + PyMySQL.

El motor SQLAlchemy se usa en toda la lógica de negocio (modules/).
scripts/init_database.py usa PyMySQL directo para inicializar el schema.
"""
from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from config import ensure_secure_db_config, get_database_url


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    # Rechaza arrancar contra una BD insegura (root / contraseña vacía) salvo que
    # se autorice explícitamente con ALLOW_INSECURE_LOCAL_DB=true.
    ensure_secure_db_config()
    return create_engine(
        get_database_url(),
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_size=3,
        max_overflow=2,
        future=True,
    )


@contextmanager
def connect() -> Iterator:
    """Context manager de conexión de solo lectura."""
    with get_engine().connect() as conn:
        yield conn


@contextmanager
def begin() -> Iterator:
    """Context manager de conexión con transacción (escritura)."""
    with get_engine().begin() as conn:
        yield conn
