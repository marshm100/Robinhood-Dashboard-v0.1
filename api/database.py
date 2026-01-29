import logging
import traceback

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool, StaticPool

from api.config import DATABASE_URL

logger = logging.getLogger(__name__)

Base = declarative_base()


def _create_engine():
    """
    Create SQLAlchemy engine with appropriate settings for the database type.

    For PostgreSQL (Vercel serverless):
    - Use NullPool to avoid connection pooling issues in serverless
    - Require SSL for secure connections

    For SQLite (local development):
    - Use StaticPool for thread safety
    - Disable same-thread check for FastAPI async compatibility
    """
    is_postgres = "postgres" in DATABASE_URL.lower()
    is_sqlite = "sqlite" in DATABASE_URL.lower()

    if is_postgres:
        logger.info(f"Configuring PostgreSQL engine (serverless mode)")
        return create_engine(
            DATABASE_URL,
            poolclass=NullPool,  # Critical for serverless - no persistent connections
            connect_args={"sslmode": "require"},
            echo=False,
            future=True,
        )
    elif is_sqlite:
        logger.info(f"Configuring SQLite engine (local development)")
        return create_engine(
            DATABASE_URL,
            poolclass=StaticPool,  # Thread-safe for SQLite
            connect_args={"check_same_thread": False},  # Allow multi-thread access
            echo=False,
            future=True,
        )
    else:
        # Generic fallback
        logger.warning(f"Unknown database type, using default engine config")
        return create_engine(
            DATABASE_URL,
            echo=False,
            future=True,
        )


engine = _create_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def get_db():
    """Dependency injection for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables and verify connection."""
    try:
        # Lazy import models to avoid circular imports
        from api.models.portfolio import Portfolio, Holding, Benchmark, HistoricalPrice

        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")

        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()

        db_type = "PostgreSQL" if "postgres" in DATABASE_URL.lower() else "SQLite"
        logger.info(f"{db_type} connection test passed")

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        traceback.print_exc()
        raise