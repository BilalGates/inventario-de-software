"""Proceso único para el servicio de Windows: web (API + interfaz) y worker en segundo plano.

    python -m app.server          # en primer plano (Ctrl+C para parar)

El servicio de Windows (app.winservice) ejecuta exactamente esto.
"""
from __future__ import annotations

import logging
import threading

import uvicorn

from app.core.config import get_settings
from app.core.logging import setup_logging

log = logging.getLogger("inventario.server")


class InventoryServer:
    def __init__(self, log_file: str | None = None) -> None:
        self.settings = get_settings()
        self.log_file = log_file
        self._stop = threading.Event()
        self._uvicorn: uvicorn.Server | None = None

    def _worker_loop(self) -> None:
        from app import worker

        while not self._stop.is_set():
            try:
                summary = worker.tick(self.settings)
                if summary.get("executed") or summary.get("enqueued") or summary.get("files"):
                    log.info("Worker: %s", summary)
            except Exception:  # noqa: BLE001 - el servicio no debe caer por un error puntual
                log.exception("Error en el worker")
            self._stop.wait(self.settings.worker_poll_seconds)

    def migrate(self) -> None:
        """Aplica las migraciones pendientes al arrancar (idempotente)."""
        from pathlib import Path

        from alembic import command
        from alembic.config import Config

        root = Path(__file__).resolve().parents[1]
        cfg = Config()  # sin alembic.ini: su configuración de logging sustituiría la del servicio
        cfg.set_main_option("script_location", str(root / "alembic"))
        cfg.set_main_option("sqlalchemy.url", self.settings.database_url)
        command.upgrade(cfg, "head")

    def run(self) -> None:
        setup_logging(log_file=self.log_file)
        s = self.settings
        if s.database_url.startswith("sqlite:///"):
            from pathlib import Path

            Path(s.database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        self.migrate()
        from app.db import session_scope
        from app.services.bootstrap import ensure_reference_data

        with session_scope() as db:
            ensure_reference_data(db)
        threading.Thread(target=self._worker_loop, name="worker", daemon=True).start()
        from app.main import create_app

        config = uvicorn.Config(create_app(), host=s.bind_host, port=s.port, log_config=None, access_log=False)
        self._uvicorn = uvicorn.Server(config)
        log.info("Inventario Asserta escuchando en http://%s:%s", s.bind_host, s.port)
        self._uvicorn.run()
        self._stop.set()

    def stop(self) -> None:
        self._stop.set()
        if self._uvicorn:
            self._uvicorn.should_exit = True


if __name__ == "__main__":
    import os

    InventoryServer(log_file=os.environ.get("INV_LOG_FILE") or None).run()
