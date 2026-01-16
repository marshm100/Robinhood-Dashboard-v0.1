# Run locally: python scripts/migrate_sqlite_to_postgres.py
# Assumes local SQLite at /tmp/portfolio.db and POSTGRES_URL env var set

import os
import pandas as pd
from sqlalchemy import create_engine

SQLITE_URL = "sqlite:////tmp/portfolio.db"
POSTGRES_URL = os.getenv("POSTGRES_URL")  # Set to your Vercel Postgres URL

if not POSTGRES_URL:
    raise ValueError("Set POSTGRES_URL env var")

sqlite_engine = create_engine(SQLITE_URL)
postgres_engine = create_engine(POSTGRES_URL)

tables = ["portfolios", "holdings", "benchmarks"]

for table in tables:
    df = pd.read_sql_table(table, sqlite_engine)
    df.to_sql(table, postgres_engine, if_exists="append", index=False)
    print(f"Migrated {len(df)} rows from {table}")

print("Migration complete")