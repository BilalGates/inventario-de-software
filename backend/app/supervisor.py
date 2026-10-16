"""Mantiene viva la aplicación: lanza app.server y lo reinicia si termina.

    pythonw -m app.supervisor      # lo usa la tarea de arranque (deploy/windows/install-autostart.ps1)
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
PYTHON = BACKEND / ".venv" / "Scripts" / "python.exe"
LOG_DIR = Path(os.environ.get("LOCALAPPDATA", str(BACKEND))) / "InventarioAsserta" / "logs"


def main() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    python = str(PYTHON if PYTHON.exists() else sys.executable)
    delay = 5
    while True:
        started = time.monotonic()
        with open(LOG_DIR / "supervisor.log", "a", encoding="utf-8") as log:
            log.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} arrancando app.server\n")
        with open(LOG_DIR / "app-output.log", "ab") as out:
            code = subprocess.call([python, "-m", "app.server"], cwd=str(BACKEND), stdout=out,
                                   stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        # Si llevaba tiempo en marcha, reinicio rápido; si cae al arrancar, espera creciente.
        delay = 5 if time.monotonic() - started > 300 else min(delay * 2, 300)
        with open(LOG_DIR / "supervisor.log", "a", encoding="utf-8") as log:
            log.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} app.server terminó (código {code}); "
                      f"reinicio en {delay}s\n")
        time.sleep(delay)


if __name__ == "__main__":
    main()
