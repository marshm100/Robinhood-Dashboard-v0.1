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

def init_db():
    try:
        # Lazy import models - include Transaction so create_all knows about it
        from api.models.portfolio import Portfolio, Holding, Transaction, Benchmark
        Base.metadata.create_all(bind=engine)
        print("SUCCESS: Database tables created successfully")
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("SUCCESS: Postgres connection test passed")
        # Ensure transactions table has activity_date column (may be missing if table pre-existed)
        _ensure_transactions_columns(engine)
    except Exception as e:
        print("ERROR in init_db():")
        import traceback
        traceback.print_exc()

def _ensure_transactions_columns(eng):
    """Add missing columns to the transactions table if it already existed without them."""
    columns_to_ensure = {
        "activity_date": "VARCHAR",
        "ticker": "VARCHAR",
        "trans_code": "VARCHAR",
        "quantity": "FLOAT",
        "price": "FLOAT",
        "amount": "FLOAT",
        "portfolio_id": "INTEGER",
    }
    try:
        with eng.connect() as conn:
            # Check which columns exist
            result = conn.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'transactions'"
            ))
            existing = {row[0] for row in result}
            if not existing:
                # Table doesn't exist yet; create_all already handled it
                return
            for col_name, col_type in columns_to_ensure.items():
                if col_name not in existing:
                    print(f"  Adding missing column transactions.{col_name} ({col_type})")
                    conn.execute(text(f"ALTER TABLE transactions ADD COLUMN {col_name} {col_type}"))
            conn.commit()
    except Exception as e:
        print(f"WARNING: Could not ensure transactions columns: {e}")