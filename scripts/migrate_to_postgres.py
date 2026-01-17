import sqlite3
import os
from sqlalchemy import create_engine, text

# Local SQLite path
LOCAL_DB = "data/portfolio.db"  # adjust if different

# Vercel Postgres URL (copy from your Vercel env vars)
POSTGRES_URL = os.getenv("POSTGRES_URL_NON_POOLING")  # set this in your shell before running

if not POSTGRES_URL:
    raise ValueError("Set POSTGRES_URL_NON_POOLING in environment")

# Connect to both
sqlite_conn = sqlite3.connect(LOCAL_DB)
sqlite_conn.row_factory = sqlite3.Row
postgres_engine = create_engine(POSTGRES_URL)

# Dump all tables
with sqlite_conn:
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row["name"] for row in cursor.fetchall() if row["name"] != "sqlite_sequence"]

with postgres_engine.begin() as conn:
    for table in tables:
        print(f"Migrating {table}...")
        # Get data
        sqlite_conn.execute(f"SELECT * FROM {table}")
        rows = sqlite_conn.fetchall()
        if not rows:
            continue
        # Build INSERT
        columns = rows[0].keys()
        placeholders = ", ".join([":" + c for c in columns])
        insert_sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
        # Execute many
        data = [dict(row) for row in rows]
        conn.execute(text(insert_sql), data)

print("Migration complete!")