import os
import logging

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Database configuration
# Priority order for Vercel PostgreSQL:
# 1. POSTGRES_URL_NON_POOLING - Best for serverless (no connection pooling)
# 2. POSTGRES_URL - Standard Vercel Postgres URL
# 3. DATABASE_URL - Generic database URL
# 4. SQLite fallback - Local development only
DATABASE_URL = (
    os.getenv("POSTGRES_URL_NON_POOLING") or
    os.getenv("POSTGRES_URL") or
    os.getenv("DATABASE_URL") or
    "sqlite:///./data/portfolio.db"  # Local dev - persistent in project dir
)

# Vercel Postgres URLs use 'postgres://' but SQLAlchemy needs 'postgresql://'
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")