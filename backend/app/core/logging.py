"""Logs estructurados (JSON por línea) sin secretos."""
from __future__ import annotations

import json
import logging
import re

_SECRET = re.compile(r"(?i)(bearer\s+[a-z0-9._-]+|client_secret=[^&\s]+|password=[^&\s]+|access_token\"?:\s*\"[^\"]+)")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        msg = _SECRET.sub("[REDACTED]", record.getMessage())
        data = {"ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"), "level": record.levelname,
                "logger": record.name, "msg": msg}
        if record.exc_info:
            data["exc"] = _SECRET.sub("[REDACTED]", self.formatException(record.exc_info))
        return json.dumps(data, ensure_ascii=False)


def setup_logging(level: int = logging.INFO, log_file: str | None = None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        from logging.handlers import RotatingFileHandler
        from pathlib import Path

        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(RotatingFileHandler(log_file, maxBytes=5_000_000, backupCount=5, encoding="utf-8"))
    for handler in handlers:
        handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = handlers
    root.setLevel(level)
    logging.getLogger("httpx").setLevel(logging.WARNING)
