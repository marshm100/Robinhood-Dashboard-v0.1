"""
Vercel Cron endpoint for daily stock price cache refresh.

Vercel sends GET requests to cron paths. The CRON_SECRET env var
is checked to prevent unauthorized access.
"""

import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.database import get_db
from api.services.stock_price_service import refresh_all_tickers

router = APIRouter(tags=["cron"])

CRON_SECRET = os.getenv("CRON_SECRET", "")


@router.get("/api/internal/refresh-stock-cache")
def refresh_stock_cache(token: str = "", db: Session = Depends(get_db)):
    """
    Incrementally refresh cached prices for every discovered ticker.
    Protected by CRON_SECRET — Vercel passes this as a query param.
    """
    if not CRON_SECRET or token != CRON_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    results = refresh_all_tickers(db)

    total_added = sum(v for v in results.values() if v > 0)
    errors = [sym for sym, v in results.items() if v < 0]

    return {
        "status": "ok",
        "tickers_processed": len(results),
        "records_added": total_added,
        "errors": errors,
    }
