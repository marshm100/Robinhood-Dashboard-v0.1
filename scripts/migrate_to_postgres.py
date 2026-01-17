import sqlite3
import os
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import IntegrityError

# Local SQLite path — adjust if your old DB is elsewhere
LOCAL_DB = "data/portfolio.db"  # or wherever your old portfolio.db lives

# Vercel Postgres URL (set in shell before running)
POSTGRES_URL = os.getenv("POSTGRES_URL_NON_POOLING")
if not POSTGRES_URL:
    raise ValueError("Set POSTGRES_URL_NON_POOLING environment variable with your Neon connection string")

print(f"Connecting to local SQLite: {LOCAL_DB}")
print(f"Connecting to Postgres: {POSTGRES_URL[:40]}...")

# Connect to both
sqlite_conn = sqlite3.connect(LOCAL_DB)
sqlite_conn.row_factory = sqlite3.Row
postgres_engine = create_engine(POSTGRES_URL)

inspector = inspect(postgres_engine)

# Define migration order to respect foreign keys
TABLE_ORDER = ["portfolios", "holdings", "benchmarks"]

with sqlite_conn:
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    local_tables = [row["name"] for row in cursor.fetchall() if row["name"] != "sqlite_sequence"]

print(f"Found local tables: {local_tables}")

with postgres_engine.begin() as conn:
    for table in TABLE_ORDER:
        if table not in local_tables:
            print(f"Skipping {table} — not in local DB")
            continue
        
        if table in inspector.get_table_names():
            # Check if already has data
            row_count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            if row_count > 0:
                print(f"Skipping {table} — already has {row_count} rows in Postgres")
                continue
        
        print(f"Migrating {table}...")
        cursor.execute(f"SELECT * FROM {table}")
        rows = cursor.fetchall()
        if not rows:
            print(f"  No rows to migrate")
            continue
        
        columns = rows[0].keys()
        placeholders = ", ".join([f":{c}" for c in columns])
        insert_sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
        
        data = [dict(row) for row in rows]
        try:
            conn.execute(text(insert_sql), data)
            print(f"  Successfully migrated {len(rows)} rows")
        except IntegrityError as e:
            print(f"  Integrity error (possible duplicates) — skipping batch: {e}")

print("Migration complete! Verify data in your live dashboard.")