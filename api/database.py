from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from api.config import DATABASE_URL

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from api.models.portfolio import Portfolio, Holding, Benchmark

def init_db():
    Base.metadata.create_all(bind=engine)
    print("Database tables created (portfolios, holdings, benchmarks)")