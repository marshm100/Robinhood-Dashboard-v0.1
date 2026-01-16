import os

DATABASE_URL = os.getenv("POSTGRES_URL", os.getenv("DATABASE_URL", "sqlite:////tmp/portfolio.db"))
# Vercel injects POSTGRES_URL; fallback to SQLite local