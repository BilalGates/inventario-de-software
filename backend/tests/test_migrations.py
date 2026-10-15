"""Las migraciones Alembic crean exactamente el esquema de los modelos y son reversibles."""
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.db import Base

ROOT = Path(__file__).resolve().parents[1]


def _cfg(url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def test_upgrade_downgrade_and_no_drift(tmp_path):
    url = f"sqlite:///{(tmp_path / 'm.db').as_posix()}"
    cfg = _cfg(url)
    command.upgrade(cfg, "head")
    tables = set(inspect(create_engine(url)).get_table_names())
    assert set(Base.metadata.tables) <= tables
    command.check(cfg)  # falla si los modelos y las migraciones difieren
    command.downgrade(cfg, "base")
    assert set(inspect(create_engine(url)).get_table_names()) <= {"alembic_version"}
    command.upgrade(cfg, "head")


def test_mysql_offline_sql_contains_constraints(capsys):
    cfg = _cfg("mysql+pymysql://u:p@localhost/x")
    command.upgrade(cfg, "head", sql=True)
    ddl = capsys.readouterr().out
    assert "fk_departments_manager_id_users" in ddl
    assert "uq_software_products_identity" in ddl
    assert "uq_device_external_ids_key" in ddl
