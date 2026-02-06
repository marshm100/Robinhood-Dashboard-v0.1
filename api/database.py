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
        from api.models.portfolio import Portfolio, Holding, Benchmark
        Base.metadata.create_all(bind=engine)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        print(f"ERROR in init_db(): {e}")