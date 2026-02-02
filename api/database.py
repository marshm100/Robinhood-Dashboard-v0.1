from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from api.config import DATABASE_URL
import traceback

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

def init_db():
    try:
        # Lazy import models
        from api.models.portfolio import Portfolio, Holding, Benchmark, Stock, PriceHistory
        Base.metadata.create_all(bind=engine)
        print("SUCCESS: Database tables created successfully")
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("SUCCESS: Postgres connection test passed")

        # --- Defensive migration for existing databases ---
        _run_safe_migrations()

    except Exception as e:
        print("ERROR in init_db():")
        traceback.print_exc()


def _run_safe_migrations():
    """Idempotent ALTER TABLEs for databases created before new columns existed."""
    migrations = [
        "ALTER TABLE stocks ADD COLUMN IF NOT EXISTS last_updated TIMESTAMP",
    ]
    try:
        with engine.connect() as conn:
            for sql in migrations:
                try:
                    conn.execute(text(sql))
                except Exception:
                    pass  # column already exists or syntax not supported (SQLite)
            conn.commit()
        print("SUCCESS: Safe migrations applied")
    except Exception as e:
        print(f"WARNING: Safe migrations skipped: {e}")


def backfill_discovered_tickers():
    """
    Scan all holdings and register their tickers in the stocks table.
    This ensures tickers from portfolios uploaded before the Stock table
    existed are picked up by the daily cron.
    """
    try:
        from api.models.portfolio import Holding, Stock
        db = SessionLocal()
        try:
            # Get all unique tickers from existing holdings
            rows = db.query(Holding.ticker).distinct().all()
            tickers = [r.ticker.upper() for r in rows if r.ticker]

            if not tickers:
                print("Backfill: no holdings found")
                return

            # Get tickers already in stocks table
            existing = set(
                r.symbol for r in db.query(Stock.symbol).all()
            )

            new_tickers = [t for t in tickers if t not in existing]
            if new_tickers:
                for t in new_tickers:
                    db.merge(Stock(symbol=t))
                db.commit()
                print(f"Backfill: registered {len(new_tickers)} tickers → {new_tickers}")
            else:
                print(f"Backfill: all {len(tickers)} tickers already registered")
        finally:
            db.close()
    except Exception as e:
        print(f"WARNING: Ticker backfill failed: {e}")