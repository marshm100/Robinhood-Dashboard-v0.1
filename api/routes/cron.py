"""
Vercel Cron endpoint for daily stock price cache refresh.

Vercel sends GET requests to cron paths.  The CRON_SECRET env var
is checked to prevent unauthorized access.
"""

import os

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.database import get_db
from api.services.stock_price_service import refresh_all_tickers

router = APIRouter(prefix="/api/internal", tags=["internal"])


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
