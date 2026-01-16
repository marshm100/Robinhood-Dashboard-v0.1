import traceback
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from api.config import DATABASE_URL

Base = declarative_base()

# Force SSL + echo for debugging
engine = create_engine(
    DATABASE_URL,
    echo=True,  # Log all SQL
    future=True,
    connect_args={"sslmode": "require"},
    pool_pre_ping=True  # Validate connections
)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    try:
        # Lazy import models
        from api.models.portfolio import Portfolio, Holding, Benchmark
        Base.metadata.create_all(bind=engine)
        print("SUCCESS: Database tables created successfully")
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("SUCCESS: Postgres connection test passed")
    except Exception as e:
        print("ERROR in init_db():")
        traceback.print_exc()