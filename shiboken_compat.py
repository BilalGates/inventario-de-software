from __future__ import annotations

import os


def apply() -> None:
    os.environ.setdefault("SHIBOKEN_DISABLE", "1")
    os.environ.setdefault("PYDEVD_DISABLE_FILE_VALIDATION", "1")

    try:
        import six
    except Exception:
        return

    importer = getattr(six, "_importer", None)
    if importer is not None and not hasattr(importer, "_path"):
        importer._path = []

