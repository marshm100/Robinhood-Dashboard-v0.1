"""
Database connection and initialization
"""

import logging
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from .config import settings

logger = logging.getLogger(__name__)


def _ensure_db_directory(db_url: str) -> None:
    """
    Ensure database directory exists for SQLite databases.
    
    This function creates the parent directory if it doesn't exist
    and logs the database file location for debugging.
    
    Default path: ./data/portfolio.db (persisted via Docker volume)
    """
    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "")
        db_file = Path(db_path)
        
        # Create parent directory if needed
        db_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Log database location for debugging
        logger.info(f"Database location: {db_file.resolve()}")
        logger.info(f"Database file exists: {db_file.exists()}")


# Ensure database directory exists before creating engine
_ensure_db_directory(settings.database_url)

engine = create_engine(
    settings.database_url,
    echo=settings.debug,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {}
)

SessionLocal = sessionmaker(
    bind=engine,
    expire_on_commit=False
)


def init_db_sync():
    """Initialize database tables synchronously"""
    try:
        from .models import Base
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise


def get_db_sync():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def reset_db_sync():
    """Reset database (drop all tables and recreate) synchronously"""
    try:
        from .models import Base
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        logger.info("Database reset successfully")
    except Exception as e:
        logger.error(f"Error resetting database: {e}")
        raise
