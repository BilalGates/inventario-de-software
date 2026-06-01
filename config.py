import os
from urllib.parse import quote_plus

from dotenv import load_dotenv

from app_paths import project_root, resource_path


load_dotenv(resource_path(".env"))
load_dotenv(project_root() / ".env", override=True)

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "database": os.getenv("DB_NAME", "inventario_software"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
}


def get_database_url() -> str:
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
