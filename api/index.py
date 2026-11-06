"""Función de Vercel: expone la API FastAPI de backend/ bajo /api/*.

La interfaz (frontend/dist) la sirve Vercel como estáticos; esta función solo atiende /api/*
(ver vercel.json). El worker no corre aquí: lo ejecuta GitHub Actions (.github/workflows/worker.yml).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.main import app  # noqa: E402

__all__ = ["app"]
