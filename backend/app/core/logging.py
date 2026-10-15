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


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    logging.getLogger("httpx").setLevel(logging.WARNING)
