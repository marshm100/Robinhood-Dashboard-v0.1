"""
Stock price cache service — Stooq-first with yfinance fallback.

Integrates stockr_backbone logic directly into the main app:
- Cache-first: always check DB before external fetch
- Incremental updates: only fetch dates we don't already have
- Auto-discovery: new tickers are added on first request
- Dual source: Stooq (primary, no API key needed), yfinance (fallback)
"""

import csv
import logging
import time
from datetime import date, datetime, timedelta
from io import StringIO
from typing import Dict, List, Optional

import httpx
from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from api.models.portfolio import HistoricalPrice, Holding, Stock

logger = logging.getLogger(__name__)

STOOQ_URL = "https://stooq.com/q/d/l/?s={symbol}.us&i=d"
MAX_RETRIES = 3


# ---------------------------------------------------------------------------
# External fetchers
# ---------------------------------------------------------------------------

def _fetch_stooq(symbol: str, timeout: int = 30) -> Optional[str]:
    """Fetch CSV data from Stooq.com with retries and exponential backoff."""
    url = STOOQ_URL.format(symbol=symbol.lower())
    for attempt in range(MAX_RETRIES):
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(url)
                resp.raise_for_status()
                text = resp.text
                # Stooq returns minimal text with "No data" when ticker unknown
                if "No data" in text or len(text.strip().splitlines()) < 2:
                    logger.warning("Stooq returned no data for %s", symbol)
                    return None
                return text
        except Exception as exc:
            wait = 2 ** attempt
            logger.warning(
                "Stooq attempt %d/%d for %s failed: %s (retry in %ds)",
                attempt + 1, MAX_RETRIES, symbol, exc, wait,
            )
            if attempt < MAX_RETRIES - 1:
                time.sleep(wait)
    return None


def _fetch_yfinance(symbol: str, start_date: Optional[date] = None) -> Optional[str]:
    """Fallback: fetch from yfinance, return Stooq-compatible CSV string."""
    try:
        import yfinance as yf

        ticker = yf.Ticker(symbol)
        if start_date:
            df = ticker.history(start=start_date.isoformat(), auto_adjust=True)
        else:
            df = ticker.history(period="max", auto_adjust=True)

        if df.empty:
            return None

        lines = ["Date,Open,High,Low,Close,Volume"]
        for idx, row in df.iterrows():
            d = idx.strftime("%Y-%m-%d")
            lines.append(
                f"{d},{row.get('Open','')},{row.get('High','')}"
                f",{row.get('Low','')},{row['Close']},{int(row.get('Volume', 0))}"
            )
        return "\n".join(lines)
    except Exception as exc:
        logger.warning("yfinance fallback failed for %s: %s", symbol, exc)
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(val) -> Optional[float]:
    try:
        v = float(val)
        return v if v > 0 else None
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> Optional[int]:
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _get_or_create_stock(db: Session, symbol: str) -> Stock:
    """Return existing Stock row or create a new one."""
    stock = db.query(Stock).filter(Stock.symbol == symbol).first()
    if not stock:
        stock = Stock(symbol=symbol)
        db.add(stock)
        db.flush()
    return stock


# ---------------------------------------------------------------------------
# Core fetch-and-store
# ---------------------------------------------------------------------------

def fetch_and_store(symbol: str, db: Session, incremental: bool = True) -> int:
    """
    Fetch daily OHLCV for *symbol* from Stooq (primary) or yfinance (fallback),
    store new rows in DB, return count of records added.
    """
    symbol = symbol.strip().upper()
    if not symbol or not symbol.replace(".", "").replace("-", "").isalnum():
        return 0

    stock = _get_or_create_stock(db, symbol)

    # Determine start date for incremental fetch
    start_date: Optional[date] = None
    if incremental:
        latest = (
            db.query(func.max(HistoricalPrice.date))
            .filter(HistoricalPrice.stock_id == stock.id)
            .scalar()
        )
        if latest:
            start_date = latest + timedelta(days=1)
            if start_date > date.today():
                return 0  # already up-to-date

    # Try Stooq first, then yfinance
    csv_text = _fetch_stooq(symbol)
    source = "stooq"
    if csv_text is None:
        csv_text = _fetch_yfinance(symbol, start_date)
        source = "yfinance"
    if csv_text is None:
        logger.error("All sources failed for %s", symbol)
        return 0

    # Parse CSV and insert rows
    records_added = 0
    reader = csv.DictReader(StringIO(csv_text))
    for row in reader:
        date_str = (row.get("Date") or "").strip()
        if not date_str:
            continue
        try:
            row_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            continue

        if start_date and row_date < start_date:
            continue

        close = _safe_float(row.get("Close"))
        if close is None:
            continue

        # Skip duplicates
        exists = (
            db.query(HistoricalPrice.id)
            .filter(
                HistoricalPrice.stock_id == stock.id,
                HistoricalPrice.date == row_date,
            )
            .first()
        )
        if exists:
            continue

        db.add(
            HistoricalPrice(
                stock_id=stock.id,
                date=row_date,
                open=_safe_float(row.get("Open")),
                high=_safe_float(row.get("High")),
                low=_safe_float(row.get("Low")),
                close=close,
                volume=_safe_int(row.get("Volume")),
            )
        )
        records_added += 1

    if records_added:
        db.commit()
    logger.info("Stored %d records for %s from %s", records_added, symbol, source)
    return records_added


# ---------------------------------------------------------------------------
# Cache-first price lookups
# ---------------------------------------------------------------------------

def get_prices(
    symbol: str,
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> List[Dict]:
    """
    Cache-first price lookup.  Returns list of
    {date, open, high, low, close, volume} dicts, ordered by date.
    Fetches from an external source if the cache is empty.
    """
    symbol = symbol.strip().upper()

    stock = db.query(Stock).filter(Stock.symbol == symbol).first()

    if not stock:
        # First time seeing this ticker — full fetch
        fetch_and_store(symbol, db, incremental=False)
        stock = db.query(Stock).filter(Stock.symbol == symbol).first()
        if not stock:
            return []
    else:
        # Incremental refresh for known tickers
        fetch_and_store(symbol, db, incremental=True)

    query = db.query(HistoricalPrice).filter(HistoricalPrice.stock_id == stock.id)
    if start_date:
        query = query.filter(HistoricalPrice.date >= start_date)
    if end_date:
        query = query.filter(HistoricalPrice.date <= end_date)
    query = query.order_by(HistoricalPrice.date)

    return [
        {
            "date": p.date.isoformat(),
            "open": p.open,
            "high": p.high,
            "low": p.low,
            "close": p.close,
            "volume": p.volume,
        }
        for p in query.all()
    ]


def get_close_price_on_date(
    symbol: str, target_date: date, db: Session
) -> Optional[float]:
    """Get the closing price for *symbol* on or before *target_date*."""
    symbol = symbol.strip().upper()

    stock = db.query(Stock).filter(Stock.symbol == symbol).first()
    if not stock:
        fetch_and_store(symbol, db, incremental=False)
        stock = db.query(Stock).filter(Stock.symbol == symbol).first()
        if not stock:
            return None

    price = (
        db.query(HistoricalPrice)
        .filter(
            HistoricalPrice.stock_id == stock.id,
            HistoricalPrice.date <= target_date,
        )
        .order_by(HistoricalPrice.date.desc())
        .first()
    )
    return price.close if price else None


# ---------------------------------------------------------------------------
# DataFrame output (drop-in replacement for price_service.get_historical_prices)
# ---------------------------------------------------------------------------

PERIOD_DAYS = {
    "1mo": 30, "3mo": 90, "6mo": 180,
    "1y": 365, "2y": 730, "5y": 1825, "max": 3650,
}


def get_prices_dataframe(
    tickers: List[str],
    db: Session,
    period: str = "1y",
):
    """
    Cache-first replacement for ``price_service.get_historical_prices()``.

    Returns a :class:`pandas.DataFrame` with **Close** prices where
    columns = tickers (uppercased), index = ``DatetimeIndex``, matching
    the exact shape that ``analysis_service`` expects.
    """
    import pandas as pd

    days = PERIOD_DAYS.get(period, 365)
    start_date = date.today() - timedelta(days=days)

    series: Dict[str, "pd.Series"] = {}
    for ticker in tickers:
        t = ticker.strip().upper()
        prices = get_prices(t, db, start_date=start_date)
        if prices:
            df = pd.DataFrame(prices)
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
            series[t] = df["close"]

    if not series:
        return pd.DataFrame()

    result = pd.DataFrame(series)
    # Forward-fill then back-fill to align tickers with slightly different
    # trading calendars, matching the old yfinance-based service behaviour.
    result = result.dropna(how="all").ffill().bfill()
    return result


# ---------------------------------------------------------------------------
# Ticker discovery
# ---------------------------------------------------------------------------

def discover_tickers(db: Session) -> List[str]:
    """
    Discover all unique tickers across holdings and the stocks table.
    Returns a sorted, deduplicated, uppercased list.
    """
    holding_tickers = db.query(distinct(Holding.ticker)).all()
    stock_tickers = db.query(distinct(Stock.symbol)).all()

    all_tickers: set[str] = set()
    for (t,) in holding_tickers:
        if t:
            all_tickers.add(t.strip().upper())
    for (t,) in stock_tickers:
        if t:
            all_tickers.add(t.strip().upper())

    return sorted(all_tickers)


def refresh_all_tickers(db: Session) -> Dict[str, int]:
    """
    Incrementally refresh all discovered tickers.
    Returns {symbol: records_added} (negative value means error).
    """
    tickers = discover_tickers(db)
    results: Dict[str, int] = {}
    for symbol in tickers:
        try:
            added = fetch_and_store(symbol, db, incremental=True)
            results[symbol] = added
        except Exception as exc:
            logger.error("Refresh failed for %s: %s", symbol, exc)
            results[symbol] = -1
    return results
