"""Configuración de Inventario Asserta 2.0, leída de variables de entorno / .env."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="INV_", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"

    # Base de datos. En producción: mysql+pymysql://usuario:clave@host:3306/inventario_asserta?charset=utf8mb4
    database_url: str = "sqlite:///./inventario_dev.db"

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

    # Carpeta supervisada para exportaciones de Panda (contingencia sin API)
    panda_drop_dir: str = ""

    # Worker
    worker_poll_seconds: int = 15
    stale_device_days: int = 30

    cors_origins: list[str] = ["http://localhost:5173"]
    frontend_dist: str = "../frontend/dist"

    @model_validator(mode="after")
    def _check_production(self) -> "Settings":
        if self.environment == "production":
            if self.auth_mode != "entra":
                raise ValueError("En producción INV_AUTH_MODE debe ser 'entra'.")
            if not (self.entra_tenant_id and self.entra_api_client_id):
                raise ValueError("Faltan INV_ENTRA_TENANT_ID / INV_ENTRA_API_CLIENT_ID.")
            if self.database_url.startswith("sqlite"):
                raise ValueError("SQLite no está soportado en producción; usa MySQL.")
        return self

    @property
    def graph_configured(self) -> bool:
        return bool(
            self.graph_tenant_id
            and self.graph_client_id
            and (self.graph_client_secret or self.graph_certificate_path)
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
