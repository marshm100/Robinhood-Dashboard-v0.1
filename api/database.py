from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from api.config import DATABASE_URL

Base = declarative_base()

engine = create_engine(DATABASE_URL, echo=False, future=True)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    # Lazy import models here to avoid circular imports
    from api.models.portfolio import Portfolio, Holding, Benchmark
    Base.metadata.create_all(bind=engine)
    print("Database tables created (sync engine - Postgres or SQLite)")