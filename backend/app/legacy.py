"""Acceso al código estable de la aplicación PySide6 (raíz del repositorio).

El parser de exportaciones de Panda (`utils/panda_parser.py`) está probado en producción;
se reutiliza tal cual en lugar de duplicarlo.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from utils.normalizer import clean_version  # noqa: E402
from utils.panda_parser import PandaParseResult, parse_panda_text  # noqa: E402

__all__ = ["PandaParseResult", "clean_version", "parse_panda_text"]
