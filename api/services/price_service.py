import logging
import time
from datetime import date, datetime, timedelta
from typing import Dict, List

import pandas as pd
import yfinance as yf
from sqlalchemy import func

from api.database import SessionLocal
from api.models.price_cache import DailyPrice, Stock

log = logging.getLogger(__name__)

_YF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
}

PERIOD_TO_DAYS = {"5d": 5, "1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "2y": 730, "5y": 1825}


# ── internal: yfinance fetch with retries ────────────────────────────

def _fetch_yfinance(ticker: str, period: str = "max", max_retries: int = 3) -> pd.DataFrame:
    """Download OHLCV from yfinance with retries + backoff. Returns DataFrame with Date index."""
    for attempt in range(max_retries):
        try:
            log.info("yfinance fetch %s period=%s attempt=%d", ticker, period, attempt + 1)
            df = yf.download(
                ticker,
                period=period,
                progress=False,
                auto_adjust=True,
                threads=False,
                headers=_YF_HEADERS,
                timeout=30,
            )
            if df.empty or df.isna().all().all():
                raise ValueError("empty result")
            log.info("yfinance OK %s: %d rows", ticker, len(df))
            return df
        except Exception as e:
            log.warning("yfinance attempt %d failed for %s: %s", attempt + 1, ticker, e)
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    return pd.DataFrame()


# ── internal: ensure Stock row exists ────────────────────────────────

def _ensure_stock(db, ticker: str) -> Stock:
    stock = db.query(Stock).filter(Stock.ticker == ticker).first()
    if not stock:
        stock = Stock(ticker=ticker)
        db.add(stock)
        db.flush()
        log.info("Registered new ticker: %s", ticker)
    return stock


# ── internal: upsert daily prices from a DataFrame ──────────────────

def _upsert_prices(db, ticker: str, df: pd.DataFrame) -> int:
    """Insert new daily prices; skip dates that already exist. Returns count of new rows."""
    if df.empty:
        return 0

    # Flatten multi-level columns from yfinance (e.g. ('Close', 'AAPL'))
    if isinstance(df.columns, pd.MultiIndex):
        df = df.droplevel("Ticker", axis=1) if "Ticker" in df.columns.names else df
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

    if "Close" not in df.columns:
        return 0

    existing_dates = set(
        row[0] for row in db.query(DailyPrice.date)
        .filter(DailyPrice.ticker == ticker)
        .all()
    )

    new_rows = []
    for idx, row in df.iterrows():
        d = idx.date() if hasattr(idx, "date") else idx
        if d in existing_dates:
            continue
        close = row.get("Close") if not pd.isna(row.get("Close")) else None
        if close is None:
            continue
        vol = int(row["Volume"]) if "Volume" in row and not pd.isna(row.get("Volume")) else None
        new_rows.append(DailyPrice(ticker=ticker, date=d, close=float(close), volume=vol))

    if new_rows:
        db.bulk_save_objects(new_rows)
        db.flush()
    return len(new_rows)


# ── public: cached historical prices ────────────────────────────────

def get_cached_history(ticker: str, period: str = "1y") -> pd.Series:
    """
    Return a pd.Series of close prices (indexed by date) for *ticker*.
    Uses the DB cache; fetches from yfinance only when data is missing or stale.
    """
    ticker = ticker.upper().strip()
    db = SessionLocal()
    try:
        stock = _ensure_stock(db, ticker)

        # Decide what date range we need
        days_needed = PERIOD_TO_DAYS.get(period, 9999)  # 9999 → "max"
        cutoff = date.today() - timedelta(days=days_needed)

        # Check what we have cached
        cached_count = (
            db.query(func.count(DailyPrice.id))
            .filter(DailyPrice.ticker == ticker, DailyPrice.date >= cutoff)
            .scalar()
        )
        latest_cached = (
            db.query(func.max(DailyPrice.date))
            .filter(DailyPrice.ticker == ticker)
            .scalar()
        )

        stale = (
            stock.last_fetched is None
            or cached_count == 0
            or latest_cached is None
            or (date.today() - latest_cached).days > 1
        )

        if stale:
            # Fetch full "max" history if we have nothing, otherwise incremental
            fetch_period = "max" if cached_count == 0 else period
            df = _fetch_yfinance(ticker, period=fetch_period)
            if not df.empty:
                inserted = _upsert_prices(db, ticker, df)
                stock.last_fetched = datetime.utcnow()
                db.commit()
                log.info("Cache primed %s: %d new rows", ticker, inserted)
            else:
                db.commit()

        # Read from cache
        rows = (
            db.query(DailyPrice.date, DailyPrice.close)
            .filter(DailyPrice.ticker == ticker, DailyPrice.date >= cutoff)
            .order_by(DailyPrice.date)
            .all()
        )
        if not rows:
            return pd.Series(dtype=float)

        series = pd.Series(
            {r.date: r.close for r in rows},
            name=ticker,
        )
        series.index = pd.DatetimeIndex(series.index)

        # Forward-fill minor gaps (weekends already absent; fill ≤3 day gaps)
        full_idx = pd.bdate_range(series.index.min(), series.index.max())
        series = series.reindex(full_idx).ffill(limit=3)
        series = series.dropna()
        return series

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ── public: latest price per ticker ──────────────────────────────────

def get_latest_prices(tickers: List[str]) -> Dict[str, float]:
    """Return {ticker: latest_close_price} using the cache."""
    result: Dict[str, float] = {}
    for t in tickers:
        try:
            series = get_cached_history(t.upper().strip(), period="1mo")
            if not series.empty:
                result[t] = round(float(series.iloc[-1]), 2)
        except Exception:
            log.warning("get_latest_prices failed for %s", t, exc_info=True)
    return result


# ── public: single-ticker price dict (used by stockr route) ─────────

def get_single_ticker_prices(ticker: str, period: str = "1y") -> dict:
    series = get_cached_history(ticker.upper().strip(), period=period)
    if series.empty:
        return {}
    return {d.strftime("%Y-%m-%d"): round(float(v), 2) for d, v in series.items()}


# ── public: register tickers (called on CSV upload) ──────────────────

def register_tickers(tickers: List[str]) -> None:
    """Ensure Stock rows exist for a list of tickers (no price fetch)."""
    if not tickers:
        return
    db = SessionLocal()
    try:
        for t in tickers:
            _ensure_stock(db, t.upper().strip())
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
