import os
import logging

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

DATABASE_URL = os.getenv("POSTGRES_URL", os.getenv("DATABASE_URL", "sqlite:////tmp/portfolio.db"))
# Vercel injects POSTGRES_URL; fallback to SQLite local

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

STOCKR_DB_PATH = os.getenv("STOCKR_DB_PATH", "stockr_backbone/stockr.db")