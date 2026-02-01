import os
from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context

# Import Base from the actual api package (not the deleted src/)
from api.database import Base

# Ensure all models are imported so Base.metadata is populated
from api.models.portfolio import (  # noqa: F401
    Portfolio, Holding, Benchmark, Stock, HistoricalPrice,
)

config = context.config

if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name)
    except KeyError:
        pass  # Skip if logging sections missing

target_metadata = Base.metadata


def _get_url() -> str:
    """Prefer env var over alembic.ini so prod Postgres works."""
    return os.getenv(
        "POSTGRES_URL",
        os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url")),
    )


def run_migrations_offline() -> None:
    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(_get_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
