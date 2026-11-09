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
    # - "local": servicio en el propio PC, solo accesible desde 127.0.0.1; usuario único (local_user_*).
    auth_mode: Literal["entra", "dev", "local"] = "dev"
    entra_tenant_id: str = ""
    entra_api_client_id: str = ""  # App registration de la API (audience)
    entra_spa_client_id: str = ""  # App registration del frontend (se expone a la SPA)
    # Mapeo de roles de aplicación (app roles de Entra) a roles internos.
    entra_role_admin: str = "Inventario.Admin"
    entra_role_technician: str = "Inventario.Tecnico"
    entra_role_auditor: str = "Inventario.Auditor"
    dev_user_upn: str = "dev@localhost"
    dev_user_role: Literal["admin", "technician", "auditor"] = "admin"
    local_user_upn: str = "administrador@local"

    # Servidor (servicio de Windows / app.server)
    bind_host: str = "127.0.0.1"
    port: int = 8180

    # Microsoft Graph (conector Intune, credenciales de aplicación)
    graph_tenant_id: str = ""
    graph_client_id: str = ""
    graph_client_secret: str = Field(default="", repr=False)
    graph_certificate_path: str = ""  # alternativa recomendada al secreto
    graph_certificate_thumbprint: str = ""
    graph_base_url: str = "https://graph.microsoft.com"
    graph_max_retries: int = 5
    # Alternativa sin registro de aplicación: sesión de usuario iniciada desde la web (código de
    # dispositivo). Fichero con el refresh token cifrado; vacío = %LOCALAPPDATA%\InventarioAsserta.
    graph_token_file: str = ""
    # Nube: la sesión de Microsoft se guarda cifrada (AES-GCM) en la base con esta clave (32 bytes en
    # base64). Debe ser la misma en Vercel y en GitHub Actions. Vacía = fichero local (Windows).
    token_encryption_key: str = Field(default="", repr=False)

    # Carpeta supervisada para exportaciones de Panda (contingencia sin API)
    panda_drop_dir: str = ""
    # Carpeta donde Inventario_Programas_Intune.ps1 deja sus CSV (se importan solos)
    intune_drop_dir: str = ""

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
    log_file: str = ""
    stale_device_days: int = 30

    cors_origins: list[str] = ["http://localhost:5173"]
    frontend_dist: str = "../frontend/dist"

    @model_validator(mode="after")
    def _check_production(self) -> "Settings":
        if os.environ.get("VERCEL") and self.auth_mode != "entra":
            # Publicado en Internet: nunca sin inicio de sesión (los modos dev/local entran como administrador).
            raise ValueError("En Vercel la aplicación es pública: configure INV_AUTH_MODE=entra e "
                             "INV_ENVIRONMENT=production (ver docs/despliegue-nube.md).")
        if self.auth_mode == "local" and self.bind_host not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError("INV_AUTH_MODE=local solo puede escuchar en 127.0.0.1: sin login, "
                             "exponerlo en la red daría acceso a cualquiera. Use 'entra' para acceso en red.")
        if self.environment == "production":
            if self.auth_mode == "dev":
                raise ValueError("En producción INV_AUTH_MODE debe ser 'entra' o 'local'.")
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

    @property
    def graph_token_path(self) -> Path | None:
        if self.graph_token_file:
            return Path(self.graph_token_file)
        if self.environment == "test" or not os.environ.get("LOCALAPPDATA"):
            return None
        return Path(os.environ["LOCALAPPDATA"]) / "InventarioAsserta" / "graph_token.bin"



# Configuración del servicio de Windows (fuera del repositorio, solo legible por administradores).
SERVICE_DIR = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "InventarioAsserta"


def env_files() -> list[Path]:
    """Orden de lectura: INV_ENV_FILE, configuración del servicio y backend/.env (desarrollo)."""
    if os.environ.get("INV_ENVIRONMENT") == "test":
        return []  # las pruebas nunca leen la configuración real del equipo
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "InventarioAsserta" / "inventario.env"
    files = [local, SERVICE_DIR / "inventario.env", Path(__file__).resolve().parents[2] / ".env"]
    if os.environ.get("INV_ENV_FILE"):
        files.insert(0, Path(os.environ["INV_ENV_FILE"]))
    return [f for f in files if _readable(f)]


def _readable(path: Path) -> bool:
    """El inventario.env del servicio solo lo leen Administradores/SYSTEM: para el resto se ignora."""
    try:
        with path.open("rb"):
            return True
    except OSError:
        return False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # Las variables de entorno prevalecen; entre ficheros, el primero de la lista.
    return Settings(_env_file=list(reversed(env_files())) or None)
