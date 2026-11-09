"""Configuración de Asserta Inventario 2.0, leída de variables de entorno / .env."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INV_", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"

    # Base de datos. En la nube: PostgreSQL de Supabase (postgresql://usuario:clave@host:6543/postgres).
    # También admite mysql+pymysql://… y SQLite para desarrollo.
    database_url: str = "sqlite:///./inventario_dev.db"
    # Funciones sin estado (Vercel): sin pool de conexiones propio. Se activa sola si existe VERCEL.
    serverless: bool = Field(default_factory=lambda: bool(os.environ.get("VERCEL")))

    # Autenticación
    # - "entra": valida tokens de Microsoft Entra ID (obligatorio en producción).
    # - "dev": identidad fija tomada de dev_user_*; solo se permite fuera de producción.
    auth_mode: Literal["entra", "dev"] = "dev"
    entra_tenant_id: str = ""
    entra_api_client_id: str = ""  # App registration de la API (audience)
    entra_spa_client_id: str = ""  # App registration del frontend (se expone a la SPA)
    # Mapeo de roles de aplicación (app roles de Entra) a roles internos.
    entra_role_admin: str = "Inventario.Admin"
    entra_role_technician: str = "Inventario.Tecnico"
    entra_role_auditor: str = "Inventario.Auditor"
    dev_user_upn: str = "dev@localhost"
    dev_user_role: Literal["admin", "technician", "auditor"] = "admin"

    # Microsoft Graph (conector Intune, credenciales de aplicación)
    graph_tenant_id: str = ""
    graph_client_id: str = ""
    graph_client_secret: str = Field(default="", repr=False)
    graph_certificate_path: str = ""  # alternativa recomendada al secreto
    graph_certificate_thumbprint: str = ""
    graph_base_url: str = "https://graph.microsoft.com"
    graph_max_retries: int = 5
    # Sesión de Microsoft iniciada desde la web (código de dispositivo, sin registro de aplicación):
    # se guarda cifrada (AES-GCM) en la base con esta clave de 32 bytes en base64. Debe ser la misma
    # en Vercel y en GitHub Actions. Vacía = no se puede conectar Intune con sesión de usuario.
    token_encryption_key: str = Field(default="", repr=False)

    # Worker
    worker_poll_seconds: int = 15
    # Cada cuánto pasa el worker, en minutos (para avisar si deja de latir). Local continuo: 1;
    # en la nube (GitHub Actions cada hora): 60.
    worker_interval_minutes: int = 1
    # Nube: lanzar el workflow del worker al encolar trabajo (token de GitHub con «Actions: write»).
    worker_dispatch_token: str = Field(default="", repr=False)
    worker_dispatch_repo: str = ""  # p. ej. BilalGates/inventario-de-software
    worker_dispatch_workflow: str = "worker.yml"
    worker_dispatch_ref: str = "main"
    stale_device_days: int = 30

    cors_origins: list[str] = ["http://localhost:5173"]
    frontend_dist: str = "../frontend/dist"

    @model_validator(mode="after")
    def _check_production(self) -> "Settings":
        if os.environ.get("VERCEL") and self.auth_mode != "entra":
            # Publicado en Internet: nunca sin inicio de sesión (el modo dev entra como administrador).
            raise ValueError("En Vercel la aplicación es pública: configure INV_AUTH_MODE=entra e "
                             "INV_ENVIRONMENT=production (ver docs/despliegue-nube.md).")
        if self.environment == "production":
            if self.auth_mode == "dev":
                raise ValueError("En producción INV_AUTH_MODE debe ser 'entra'.")
            if self.auth_mode == "entra" and not (self.entra_tenant_id and self.entra_api_client_id):
                raise ValueError("Faltan INV_ENTRA_TENANT_ID / INV_ENTRA_API_CLIENT_ID.")
            if self.auth_mode == "entra" and self.database_url.startswith("sqlite"):
                raise ValueError("Con acceso multiusuario (entra) use PostgreSQL o MySQL, no SQLite.")
        return self

    @property
    def graph_app_configured(self) -> bool:
        return bool(
            self.graph_tenant_id
            and self.graph_client_id
            and (self.graph_client_secret or self.graph_certificate_path)
        )


def env_files() -> list[Path]:
    """Ficheros .env (solo desarrollo): INV_ENV_FILE y backend/.env. En la nube todo va en variables."""
    if os.environ.get("INV_ENVIRONMENT") == "test":
        return []  # las pruebas nunca leen la configuración real del equipo
    files = [Path(__file__).resolve().parents[2] / ".env"]
    if os.environ.get("INV_ENV_FILE"):
        files.insert(0, Path(os.environ["INV_ENV_FILE"]))
    return [f for f in files if f.is_file()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # Las variables de entorno prevalecen; entre ficheros, el primero de la lista.
    return Settings(_env_file=list(reversed(env_files())) or None)
