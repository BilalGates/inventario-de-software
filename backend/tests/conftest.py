from __future__ import annotations

import os

os.environ.setdefault("INV_ENVIRONMENT", "test")
os.environ.setdefault("INV_AUTH_MODE", "dev")
os.environ.setdefault("INV_DATABASE_URL", "sqlite://")

import pytest  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import db as dbmod  # noqa: E402
from app.models import *  # noqa: E402,F403
from app.services.bootstrap import ensure_reference_data  # noqa: E402


@pytest.fixture()
def engine():
    from sqlalchemy import create_engine, event

    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)

    @event.listens_for(eng, "connect")
    def _fk(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    dbmod.Base.metadata.create_all(eng)
    dbmod.configure(eng)
    with Session(eng) as s:
        ensure_reference_data(s)
        s.commit()
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    session = dbmod.session_factory()()
    yield session
    session.close()
