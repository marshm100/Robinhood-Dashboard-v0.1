import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.database import get_db
from api.services.stock_price_service import get_prices, fetch_and_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stockr", tags=["stockr"])


@router.get("/prices/{ticker}")
def get_historical_prices(
    ticker: str,
    start: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """
    Cache-first historical prices.  Fetches from Stooq/yfinance on first
    request, then serves from the local DB on subsequent calls.
    """
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    try:
        if start:
            start_date = datetime.strptime(start, "%Y-%m-%d").date()
        if end:
            end_date = datetime.strptime(end, "%Y-%m-%d").date()
    except ValueError:
        return {"ticker": ticker.upper(), "error": "Invalid date format. Use YYYY-MM-DD."}

    prices = get_prices(ticker, db, start_date=start_date, end_date=end_date)
    if not prices:
        return {"ticker": ticker.upper(), "error": "No data found", "prices": []}

    return {
        "ticker": ticker.upper(),
        "count": len(prices),
        "prices": prices,
    }


@router.post("/fetch/{ticker}")
def trigger_fetch(
    ticker: str,
    incremental: bool = True,
    db: Session = Depends(get_db),
):
    """Manually trigger a fetch for a specific ticker."""
    added = fetch_and_store(ticker, db, incremental=incremental)
    return {"ticker": ticker.upper(), "records_added": added}


@router.get("/prime-cache/{ticker}")
def prime_cache(ticker: str, db: Session = Depends(get_db)):
    """
    GET-friendly full historical fetch for a ticker.
    Forces incremental=False so the entire history is pulled on first use.
    Curl-friendly: GET /api/stockr/prime-cache/BITU
    """
    symbol = ticker.strip().upper()
    try:
        added = fetch_and_store(symbol, db, incremental=False)
        logger.info("prime-cache %s: %d records added", symbol, added)
        return {
            "ticker": symbol,
            "records_added": added,
            "source": "stooq with yfinance fallback",
        }
    except Exception as exc:
        logger.error("prime-cache %s failed: %s", symbol, exc)
        return {"ticker": symbol, "records_added": 0, "error": str(exc)}
