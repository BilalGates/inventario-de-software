"""
Configuración central de la aplicación Inventario Asserta.
Los valores de BD se leen desde .env con fallback a valores por defecto.
"""
from __future__ import annotations

import os
import sys
import warnings
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv


# ---------------------------------------------------------------------------
# Resolución de rutas — compatible con PyInstaller (frozen) y desarrollo
# ---------------------------------------------------------------------------

def _project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _bundled_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", _project_root())).resolve()


def resource_path(*parts: str) -> Path:
    """Devuelve la ruta correcta tanto en desarrollo como en el .exe compilado."""
    installed = _project_root().joinpath(*parts)
    if installed.exists():
        return installed
    return _bundled_root().joinpath(*parts)


BASE_DIR = _project_root()

# Cargar .env desde la raíz del proyecto
load_dotenv(resource_path(".env"))
load_dotenv(BASE_DIR / ".env", override=True)

# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "database": os.getenv("DB_NAME", "inventario_software"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "charset": "utf8mb4",
    "connection_timeout": 10,
}


def get_database_url() -> str:
    """URL de conexión SQLAlchemy (mysql+pymysql://)."""
    user = quote_plus(DB_CONFIG["user"])
    password = quote_plus(DB_CONFIG["password"])
    host = DB_CONFIG["host"]
    port = DB_CONFIG["port"]
    database = quote_plus(DB_CONFIG["database"])
    return (
        "mysql+pymysql://"
        f"{user}:{password}"
        f"@{host}:{port}/{database}"
        "?charset=utf8mb4"
    )


# ---------------------------------------------------------------------------
# Seguridad de la conexión a BD
# ---------------------------------------------------------------------------

_TRUTHY = {"1", "true", "yes", "on", "si", "sí"}


class InsecureDatabaseConfigError(RuntimeError):
    """Se intentó usar una configuración de BD insegura sin autorizarla explícitamente."""


def allow_insecure_local_db() -> bool:
    """True si ALLOW_INSECURE_LOCAL_DB está activado (solo para desarrollo local)."""
    return os.getenv("ALLOW_INSECURE_LOCAL_DB", "").strip().lower() in _TRUTHY


def check_db_security(config: dict | None = None) -> list[str]:
    """Devuelve la lista de problemas de seguridad de la configuración de BD (vacía si es segura)."""
    config = config or DB_CONFIG
    issues: list[str] = []
    if str(config.get("user", "")).strip().lower() == "root":
        issues.append("el usuario de BD es 'root'")
    if not str(config.get("password", "") or ""):
        issues.append("la contraseña de BD está vacía")
    return issues


def ensure_secure_db_config(config: dict | None = None) -> None:
    """
    Bloquea el arranque si la configuración de BD es insegura (root / contraseña vacía).

    En desarrollo local se puede permitir explícitamente con ALLOW_INSECURE_LOCAL_DB=true,
    en cuyo caso se emite solo una advertencia en lugar de un error.
    """
    issues = check_db_security(config)
    if not issues:
        return
    detail = "; ".join(issues)
    if allow_insecure_local_db():
        warnings.warn(
            f"Configuración de BD insegura permitida por ALLOW_INSECURE_LOCAL_DB: {detail}.",
            stacklevel=2,
        )
        return
    raise InsecureDatabaseConfigError(
        "Configuración de base de datos insegura: "
        + detail
        + ".\n\nCrea un usuario MySQL dedicado y con contraseña (ver docs/OPERACION.md) "
        "y configúralo en el fichero .env.\n"
        "Solo para desarrollo local desechable puedes saltarte esta comprobación "
        "estableciendo ALLOW_INSECURE_LOCAL_DB=true (no recomendado)."
    )


# ---------------------------------------------------------------------------
# Departamentos — valores fijos del negocio (no configurables)
# ---------------------------------------------------------------------------

DEPARTMENTS = [
    "Gerencia",
    "IT",
    "Silicon",
    "Data Science/Analytics",
    "Administración",
    "Servidores",
]

# Mapeo código DB → nombre display
DEPT_CODE_MAP = {
    "gerencia": "Gerencia",
    "it": "IT",
    "silicon": "Silicon",
    "data_science": "Data Science/Analytics",
    "administracion": "Administración",
    "servidores": "Servidores",
}

# ---------------------------------------------------------------------------
# Rutas de recursos
# ---------------------------------------------------------------------------

RESOURCES_DIR = BASE_DIR / "resources"
ICONS_DIR = RESOURCES_DIR / "icons"
HARDWARE_CSV = RESOURCES_DIR / "Inventario_Equipos_Asserta.csv"
SOFTWARE_EXCEL = RESOURCES_DIR / "Inventario_Software_ENS_Por_Departamento.xlsx"
SOFTWARE_VBS = RESOURCES_DIR / "Inventario_Software.vbs"

# ---------------------------------------------------------------------------
# Ventana principal
# ---------------------------------------------------------------------------

APP_NAME = "Inventario Asserta"
APP_VERSION = "2.0.0"
WINDOW_MIN_WIDTH = 1280
WINDOW_MIN_HEIGHT = 720

# ---------------------------------------------------------------------------
# ENS
# ---------------------------------------------------------------------------

ENS_GUIDE_VERSION = "CCN-STIC Guía 105"
