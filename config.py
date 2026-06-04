"""
Configuración central de la aplicación Inventario Asserta.
Los valores de BD se leen desde .env con fallback a valores por defecto.
"""
from __future__ import annotations

import os
import sys
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
