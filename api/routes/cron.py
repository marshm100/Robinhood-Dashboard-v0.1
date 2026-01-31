"""
Vercel Cron endpoint for daily stock price cache refresh, plus
temporary schema-fix fallback (in case schema_fix.py fails to import
on Vercel).

Vercel sends GET requests to cron paths.  The CRON_SECRET env var
is checked to prevent unauthorized access.
"""

import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from api.database import Base, engine, get_db
from api.models.portfolio import HistoricalPrice, Stock
from api.services.stock_price_service import refresh_all_tickers

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/internal", tags=["internal"])

REQUIRED_HP_COLUMNS = {"id", "stock_id", "date", "open", "high", "low", "close", "volume"}
REQUIRED_STOCK_COLUMNS = {"id", "symbol"}


@router.get("/refresh-stock-cache")
def refresh_stock_cache(
    token: str = Query(..., description="Must match CRON_SECRET env var"),
    db: Session = Depends(get_db),
):
    """
    Incrementally refresh cached prices for every discovered ticker.
    Protected by CRON_SECRET — Vercel passes this as a query param.
    """
    expected = os.getenv("CRON_SECRET", "")
    if not expected or token != expected:
        raise HTTPException(status_code=401, detail="Invalid token")

    results = refresh_all_tickers(db)

    total_added = sum(v for v in results.values() if v > 0)
    errors = [sym for sym, v in results.items() if v < 0]

    return {
        "status": "success",
        "tickers_processed": len(results),
        "records_added": total_added,
        "errors": errors,
        "details": results,
    }


@router.get("/schema-fix/stock-cache")
def fix_stock_cache_schema(db: Session = Depends(get_db)):
    """
    Temporary: inspect stocks + historical_prices and recreate if
    columns are missing.  Duplicated here from schema_fix.py as a
    fallback in case that file fails to import on Vercel.
    """
    insp = inspect(engine)
    actions: list[str] = []
    existing_tables = insp.get_table_names()

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

    stocks_ok = "stocks" in existing_tables and REQUIRED_STOCK_COLUMNS <= stocks_cols
    hp_ok = "historical_prices" in existing_tables and REQUIRED_HP_COLUMNS <= hp_cols

    if stocks_ok and hp_ok:
        stocks_count = db.execute(text("SELECT COUNT(*) FROM stocks")).scalar()
        hp_count = db.execute(text("SELECT COUNT(*) FROM historical_prices")).scalar()
        return {
            "status": "schema_ok",
            "actions": [],
            "before": before,
            "after": before,
            "row_counts": {"stocks": stocks_count, "historical_prices": hp_count},
        }

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

    Base.metadata.create_all(
        bind=engine,
        tables=[Stock.__table__, HistoricalPrice.__table__],
    )
    actions.append("recreated stocks")
    actions.append("recreated historical_prices")
    logger.info("Schema fixed: stock cache tables recreated")

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
