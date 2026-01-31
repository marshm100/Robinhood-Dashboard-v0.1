"""
Temporary endpoint to fix incomplete stock price cache schema in Neon.

Inspects the current columns on stocks / historical_prices and recreates
the tables if they are missing or incomplete.  Remove after the schema
is confirmed correct in production.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from api.database import Base, engine, get_db
from api.models.portfolio import HistoricalPrice, Stock

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/internal", tags=["internal"])

REQUIRED_HP_COLUMNS = {"id", "stock_id", "date", "open", "high", "low", "close", "volume"}
REQUIRED_STOCK_COLUMNS = {"id", "symbol"}


@router.get("/ping")
def ping():
    """Minimal test: if this returns, the schema_fix router is mounted."""
    return {"status": "internal_router_ok", "message": "If you see this, /api/internal prefix is mounted"}


@router.get("/schema-fix/stock-cache")
def fix_stock_cache_schema(db: Session = Depends(get_db)):
    """
    Inspect stocks + historical_prices tables.  If columns are missing
    (e.g. stock_id), drop both tables and recreate from the ORM models.
    """
    insp = inspect(engine)
    actions: list[str] = []
    existing_tables = insp.get_table_names()

    # --- inspect current state ---
    stocks_cols: set[str] = set()
    hp_cols: set[str] = set()

    if "stocks" in existing_tables:
        stocks_cols = {c["name"] for c in insp.get_columns("stocks")}
    if "historical_prices" in existing_tables:
        hp_cols = {c["name"] for c in insp.get_columns("historical_prices")}

    before = {
        "stocks_columns": sorted(stocks_cols),
        "historical_prices_columns": sorted(hp_cols),
    }

    # --- decide if we need to recreate ---
    stocks_ok = "stocks" in existing_tables and REQUIRED_STOCK_COLUMNS <= stocks_cols
    hp_ok = "historical_prices" in existing_tables and REQUIRED_HP_COLUMNS <= hp_cols

    if stocks_ok and hp_ok:
        # count rows to confirm usable
        stocks_count = db.execute(text("SELECT COUNT(*) FROM stocks")).scalar()
        hp_count = db.execute(text("SELECT COUNT(*) FROM historical_prices")).scalar()
        return {
            "status": "schema_ok",
            "actions": [],
            "before": before,
            "after": before,
            "row_counts": {"stocks": stocks_count, "historical_prices": hp_count},
        }

    # --- drop and recreate ---
    with engine.begin() as conn:
        if "historical_prices" in existing_tables:
            logger.warning("Dropping historical_prices (missing columns: %s)",
                           REQUIRED_HP_COLUMNS - hp_cols if hp_cols else "table incomplete")
            conn.execute(text("DROP TABLE IF EXISTS historical_prices CASCADE"))
            actions.append("dropped historical_prices")

        if "stocks" in existing_tables:
            logger.warning("Dropping stocks (missing columns: %s)",
                           REQUIRED_STOCK_COLUMNS - stocks_cols if stocks_cols else "table incomplete")
            conn.execute(text("DROP TABLE IF EXISTS stocks CASCADE"))
            actions.append("dropped stocks")

    # Recreate only these two tables from ORM metadata
    Base.metadata.create_all(
        bind=engine,
        tables=[Stock.__table__, HistoricalPrice.__table__],
    )
    actions.append("recreated stocks")
    actions.append("recreated historical_prices")
    logger.info("Schema fixed: stock cache tables recreated")

    # --- verify ---
    insp2 = inspect(engine)
    after_stocks = sorted(c["name"] for c in insp2.get_columns("stocks"))
    after_hp = sorted(c["name"] for c in insp2.get_columns("historical_prices"))

    return {
        "status": "schema_fixed",
        "actions": actions,
        "before": before,
        "after": {
            "stocks_columns": after_stocks,
            "historical_prices_columns": after_hp,
        },
        "row_counts": {"stocks": 0, "historical_prices": 0},
    }
