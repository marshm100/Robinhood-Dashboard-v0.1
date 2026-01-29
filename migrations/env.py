from logging.config import fileConfig

from sqlalchemy import create_engine
from sqlalchemy import pool

from alembic import context

# Import database config and models
from api.config import DATABASE_URL
from api.database import Base

# Import models to ensure they're registered with Base.metadata
from api.models.portfolio import Portfolio, Holding, Benchmark, HistoricalPrice, Transaction

config = context.config

if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name)
    except KeyError:
        pass  # Skip if logging sections missing

target_metadata = Base.metadata


def get_url() -> str:
    """Get database URL from environment config."""
    return DATABASE_URL


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL script)."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (applies to database directly)."""
    url = get_url()

    # Configure engine based on database type
    connect_args = {}
    if "postgres" in url.lower():
        connect_args["sslmode"] = "require"
    elif "sqlite" in url.lower():
        connect_args["check_same_thread"] = False

    connectable = create_engine(
        url,
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
