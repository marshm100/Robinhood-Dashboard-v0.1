from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from api.config import DATABASE_URL

Base = declarative_base()

connect_args = {}
if "postgres" in DATABASE_URL:
    connect_args["sslmode"] = "require"

engine = create_engine(
    DATABASE_URL,
    echo=False,  # Set to True for debug SQL logs
    future=True,
    connect_args=connect_args
)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _run_migrations():
    """
    Idempotent ALTER TABLE statements for columns added after initial deployment.
    PostgreSQL ADD COLUMN IF NOT EXISTS is safe to run repeatedly.
    """
    migrations = [
        "ALTER TABLE portfolios ADD COLUMN IF NOT EXISTS inception_date DATE",
        "ALTER TABLE portfolios ADD COLUMN IF NOT EXISTS snapshot_date DATE",
        "ALTER TABLE portfolios ADD COLUMN IF NOT EXISTS track_to_present BOOLEAN DEFAULT TRUE",
        "ALTER TABLE holdings ADD COLUMN IF NOT EXISTS avg_cost NUMERIC",
    ]
    try:
        with engine.begin() as conn:
            for sql in migrations:
                conn.execute(text(sql))
        print("SUCCESS: Schema migrations applied")
    except Exception as e:
        print(f"WARN: Schema migration failed (may be fine on first deploy): {e}")


def init_db():
    try:
        # Lazy import models
        from api.models.portfolio import Portfolio, Holding, Benchmark, Stock
        Base.metadata.create_all(bind=engine)
        print("SUCCESS: Database tables created successfully")
        # Add columns that create_all won't add to existing tables
        _run_migrations()
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("SUCCESS: Postgres connection test passed")
    except Exception as e:
        print(f"ERROR in init_db(): {e}")
        import traceback
        traceback.print_exc()