"""
Temporary debug endpoint for verifying Neon Postgres connectivity.

Remove once the connection is confirmed stable in production.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text, inspect
from sqlalchemy.orm import Session

from api.database import get_db, engine
from api.models.portfolio import Stock, HistoricalPrice

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/internal", tags=["internal"])


@router.get("/db-status")
def db_status(db: Session = Depends(get_db)):
    """
    Diagnostic endpoint: verify DB connectivity, schema presence, and
    basic row counts.  No auth — intended for one-off manual checks
    after deploy.
    """
    result = {
        "status": "unknown",
        "database": "unknown",
        "test_query": "not_run",
        "tables": [],
        "row_counts": {},
    }

    try:
        # 1. Basic connectivity
        db.execute(text("SELECT 1")).scalar()
        result["test_query"] = "success"

        # 2. Identify the database engine
        url = str(engine.url)
        if "postgres" in url:
            result["database"] = "Neon Postgres"
        elif "sqlite" in url:
            result["database"] = "SQLite"
        else:
            result["database"] = url.split("://")[0] if "://" in url else "unknown"

        # 3. List all tables the engine can see
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        result["tables"] = tables

        # 4. Row counts for key tables
        counts = {}
        for table in ("portfolios", "holdings", "stocks", "historical_prices", "benchmarks"):
            if table in tables:
                count = db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                counts[table] = count
        result["row_counts"] = counts

        # 5. Quick sample: newest cached stock (if any)
        sample_stock = db.query(Stock).first()
        if sample_stock:
            price_count = (
                db.query(HistoricalPrice)
                .filter(HistoricalPrice.stock_id == sample_stock.id)
                .count()
            )
            result["sample_stock"] = {
                "symbol": sample_stock.symbol,
                "cached_prices": price_count,
            }

        result["status"] = "connected"
        logger.info("DB connection test successful — %s, %d tables", result["database"], len(tables))

    except Exception as exc:
        result["status"] = "failed"
        result["error"] = str(exc)
        logger.error("DB connection test FAILED: %s", exc)

    return result
