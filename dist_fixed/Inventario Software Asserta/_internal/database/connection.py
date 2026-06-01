from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from config import get_database_url


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(
        get_database_url(),
        pool_pre_ping=True,
        pool_recycle=3600,
        future=True,
    )


@contextmanager
def connect() -> Iterator:
    with get_engine().connect() as conn:
        yield conn


@contextmanager
def begin() -> Iterator:
    with get_engine().begin() as conn:
        yield conn
