"""Entorno de Alembic: usa INV_DATABASE_URL y el metadata de los modelos."""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

import app.models  # noqa: F401 - registra todas las tablas
from app.core.config import get_settings
from app.db import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

url = config.get_main_option("sqlalchemy.url") or get_settings().database_url
config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Genera el SQL sin conectar (para revisarlo o entregarlo a un DBA)."""
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"}, render_as_batch=url.startswith("sqlite"))
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = config.attributes.get("connection")
    if connectable is None:
        connectable = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.",
                                         poolclass=pool.NullPool)
        with connectable.connect() as connection:
            _run(connection)
    else:
        _run(connectable)


def _include(dialect: str):
    def include(obj, name, type_, reflected, compare_to):
        # SQLite (solo desarrollo/tests) no puede crear la FK circular departments<->users.
        return not (dialect == "sqlite" and type_ == "foreign_key_constraint"
                    and name == "fk_departments_manager_id_users")
    return include


def _run(connection) -> None:
    dialect = connection.dialect.name
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True,
                      render_as_batch=dialect == "sqlite", include_object=_include(dialect))
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
