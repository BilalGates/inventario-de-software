"""Parser de exportaciones de Panda heredado de la aplicación de escritorio (probado en producción)."""
from __future__ import annotations

from app.parsers.normalizer import clean_version
from app.parsers.panda import PandaParseResult, parse_panda_text

__all__ = ["PandaParseResult", "clean_version", "parse_panda_text"]
