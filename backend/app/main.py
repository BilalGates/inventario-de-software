"""Aplicación web de Inventario Asserta 2.0.

    uvicorn app.main:app --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import devices, inventory, org, software
from app.core.config import get_settings
from app.core.logging import setup_logging

log = logging.getLogger("inventario.api")
VERSION = "2.0.0"


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging()
    docs = settings.environment != "production"
    app = FastAPI(title="Inventario Asserta API", version=VERSION, docs_url="/api/docs" if docs else None,
                  redoc_url=None, openapi_url="/api/openapi.json" if docs else None)

    if settings.environment == "development":
        app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                           allow_methods=["*"], allow_headers=["*"])

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        if settings.environment == "production":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        errors = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"].removeprefix("Value error, ")}
                  for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": errors[0]["message"] if errors else "Datos no válidos",
                                                      "errors": errors})

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        log.exception("Error no controlado en %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Error interno. Consulte los registros del servidor."})

    for router in (devices.router, org.router, software.router, software.policies, inventory.router,
                   inventory.health):
        app.include_router(router)

    @app.get("/api/config/public", tags=["Sistema"])
    def public_config():
        """Lo mínimo que la SPA necesita para iniciar sesión con Entra ID (sin secretos)."""
        return {"auth_mode": settings.auth_mode, "tenant_id": settings.entra_tenant_id,
                "client_id": settings.entra_spa_client_id,
                "api_scope": f"api://{settings.entra_api_client_id}/access_as_user"
                if settings.entra_api_client_id else None, "version": VERSION, "environment": settings.environment}

    dist = Path(settings.frontend_dist)
    if not dist.is_absolute():
        dist = (Path(__file__).resolve().parents[1] / dist).resolve()
    if (dist / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith("api/"):
                return JSONResponse(status_code=404, content={"detail": "No encontrado"})
            file = (dist / path).resolve()
            if path and file.is_file() and dist in file.parents:
                return FileResponse(file)
            return FileResponse(dist / "index.html")

    return app


app = create_app()
