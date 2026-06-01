from __future__ import annotations

import sys
from pathlib import Path


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def bundled_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", project_root())).resolve()


def resource_path(*parts: str) -> Path:
    installed_path = project_root().joinpath(*parts)
    if installed_path.exists():
        return installed_path
    return bundled_root().joinpath(*parts)

