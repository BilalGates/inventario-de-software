"""Servidor para las pruebas E2E: BD SQLite temporal, worker real en segundo plano y API + SPA.

    python tests/e2e_server.py --port 8765
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
db_file = Path(tempfile.mkdtemp()) / "e2e.db"
os.environ.update(INV_ENVIRONMENT="test", INV_AUTH_MODE="dev", INV_DATABASE_URL=f"sqlite:///{db_file.as_posix()}",
                  INV_DEV_USER_ROLE="admin", INV_DEV_USER_UPN="e2e@asserta.test")

import uvicorn  # noqa: E402

from app import worker  # noqa: E402
from app.db import Base, get_engine, session_scope  # noqa: E402
from app.models import AppSetting  # noqa: E402
from app.services.bootstrap import ensure_reference_data  # noqa: E402


def worker_loop() -> None:
    while True:
        try:
            worker.tick()
        except Exception as exc:  # noqa: BLE001
            print("worker:", exc, file=sys.stderr)
        time.sleep(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    Base.metadata.create_all(get_engine())
    with session_scope() as db:
        ensure_reference_data(db)
        db.get(AppSetting, "schedule.monthly").value = {"enabled": False, "day": 1, "hour": 0, "sources": []}
    threading.Thread(target=worker_loop, daemon=True).start()
    from app.main import create_app

    uvicorn.run(create_app(), host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
