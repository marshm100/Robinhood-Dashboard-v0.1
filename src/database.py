"""
Database connection and initialization
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from .config import settings

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
        print("Database tables created successfully")
    except Exception as e:
        print(f"Error creating database tables: {e}")
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
        print("Database reset successfully")
    except Exception as e:
        print(f"Error resetting database: {e}")
        raise
