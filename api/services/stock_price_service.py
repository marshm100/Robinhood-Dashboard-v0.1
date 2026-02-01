"""
Stock price cache service — yfinance-primary with Stooq fallback.

Integrates stockr_backbone logic directly into the main app:
- Cache-first: always check DB before external fetch
- Incremental updates: only fetch dates we don't already have
- Auto-discovery: new tickers are added on first request
- Dual source: yfinance (primary, reliable on Vercel), Stooq (fallback)
"""

import csv
import logging
import time
from datetime import date, datetime, timedelta
from io import StringIO
from typing import Dict, List, Optional, Tuple

import httpx
from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from api.models.portfolio import HistoricalPrice, Holding, Stock

logger = logging.getLogger(__name__)

STOOQ_URL = "https://stooq.com/q/d/l/?s={symbol}.us&i=d"
MAX_RETRIES = 3
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# If the primary source yields fewer rows than this on a full fetch,
# try the fallback source.
MIN_ROWS_FULL_FETCH = 100


# ---------------------------------------------------------------------------
# External fetchers
# ---------------------------------------------------------------------------

def _fetch_yfinance(symbol: str, start_date: Optional[date] = None):
    """Primary source: fetch via yf.download, return a pandas DataFrame
    with flat columns (Open, High, Low, Close, Volume) and DatetimeIndex,
    or None on failure."""
    try:
        import pandas as pd
        import yfinance as yf

        logger.info("yfinance fetch for %s (start=%s)", symbol, start_date)

        kwargs: dict = {"progress": False, "auto_adjust": True, "timeout": 30}
        if start_date:
            kwargs["start"] = start_date.isoformat()
        else:
            kwargs["period"] = "max"

        df = yf.download(symbol, **kwargs)

        if df.empty:
            logger.warning("yfinance %s: empty DataFrame", symbol)
            return None

        # yf.download returns MultiIndex columns even for single ticker
        # e.g. ('Close', 'SPY') — flatten to just 'Close'
        if isinstance(df.columns, pd.MultiIndex):
            logger.info("yfinance %s: flattening MultiIndex columns: %s", symbol, list(df.columns[:5]))
            df.columns = df.columns.get_level_values(0)

        logger.info(
            "yfinance %s: shape=%s, columns=%s, date_range=%s..%s",
            symbol, df.shape, list(df.columns),
            df.index[0].strftime("%Y-%m-%d"), df.index[-1].strftime("%Y-%m-%d"),
        )
        return df

    except Exception as exc:
        logger.error("yfinance fetch FAILED for %s: %s", symbol, exc)
        return None


def _fetch_stooq(symbol: str, timeout: int = 30) -> Optional[str]:
    """Fallback: fetch CSV data from Stooq.com with browser User-Agent."""
    url = STOOQ_URL.format(symbol=symbol.lower())
    for attempt in range(MAX_RETRIES):
        try:
            with httpx.Client(
                timeout=timeout,
                headers={"User-Agent": BROWSER_UA},
                follow_redirects=True,
            ) as client:
                resp = client.get(url)
                logger.info(
                    "Stooq %s: HTTP %d, %d bytes",
                    symbol, resp.status_code, len(resp.text),
                )
                resp.raise_for_status()

                text = resp.text
                lines = text.strip().splitlines()

                if not lines or "Date" not in lines[0]:
                    logger.warning(
                        "Stooq %s: not CSV (header: %r)",
                        symbol, lines[0][:120] if lines else "EMPTY",
                    )
                    return None

                if "No data" in text:
                    logger.warning("Stooq %s: 'No data' in response body", symbol)
                    return None

                data_rows = len(lines) - 1
                if data_rows < 2:
                    logger.warning("Stooq %s: only %d data rows", symbol, data_rows)
                    return None

                logger.info("Stooq %s: %d CSV data rows", symbol, data_rows)
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
# Insertion helpers — one for DataFrames (yfinance), one for CSV (Stooq)
# ---------------------------------------------------------------------------

def _insert_from_dataframe(
    df,
    stock: Stock,
    db: Session,
    start_date: Optional[date],
) -> Tuple[int, int, int, int, int]:
    """Insert rows from a pandas DataFrame (DatetimeIndex + OHLCV columns).

    Returns ``(added, parsed, skipped_date, skipped_close, skipped_dup)``.
    """
    import math

    added = parsed = skipped_date = skipped_close = skipped_dup = 0

    for idx, row in df.iterrows():
        parsed += 1

        try:
            row_date = idx.date() if hasattr(idx, "date") else idx
        except Exception:
            skipped_date += 1
            continue

        if start_date and row_date < start_date:
            continue

        close_val = row.get("Close")
        if close_val is None or (isinstance(close_val, float) and (math.isnan(close_val) or close_val <= 0)):
            skipped_close += 1
            if parsed <= 3:
                logger.warning("%s row %d: Close=%r — skipping", stock.symbol, parsed, close_val)
            continue

        close = float(close_val)

        exists = (
            db.query(HistoricalPrice.id)
            .filter(
                HistoricalPrice.stock_id == stock.id,
                HistoricalPrice.date == row_date,
            )
            .first()
        )
        if exists:
            skipped_dup += 1
            continue

        def _row_float(key):
            v = row.get(key)
            if v is None:
                return None
            try:
                fv = float(v)
                return fv if fv > 0 and not math.isnan(fv) else None
            except (ValueError, TypeError):
                return None

        def _row_int(key):
            v = row.get(key)
            if v is None:
                return None
            try:
                return int(float(v))
            except (ValueError, TypeError):
                return None

        db.add(
            HistoricalPrice(
                stock_id=stock.id,
                date=row_date,
                open=_row_float("Open"),
                high=_row_float("High"),
                low=_row_float("Low"),
                close=close,
                volume=_row_int("Volume"),
            )
        )
        added += 1

        # Log first and last sample rows
        if added == 1:
            logger.info(
                "%s first row: date=%s close=%.2f open=%s",
                stock.symbol, row_date, close, _row_float("Open"),
            )

    return added, parsed, skipped_date, skipped_close, skipped_dup


def _parse_and_insert(
    csv_text: str,
    stock: Stock,
    db: Session,
    start_date: Optional[date],
) -> Tuple[int, int, int, int, int]:
    """Parse CSV text and insert new rows.

    Returns ``(added, parsed, skipped_date, skipped_close, skipped_dup)``.
    """
    added = parsed = skipped_date = skipped_close = skipped_dup = 0

    reader = csv.DictReader(StringIO(csv_text))

    # Log column names from the CSV header
    if reader.fieldnames:
        logger.info("%s CSV columns: %s", stock.symbol, reader.fieldnames)

    for row in reader:
        parsed += 1

        # Log first 2 raw rows for debugging
        if parsed <= 2:
            logger.info("%s CSV sample row %d: %s", stock.symbol, parsed, dict(row))

        date_str = (row.get("Date") or "").strip()
        if not date_str:
            skipped_date += 1
            continue
        try:
            row_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            skipped_date += 1
            if parsed <= 5:
                logger.warning("%s row %d: unparseable date %r", stock.symbol, parsed, date_str)
            continue

        if start_date and row_date < start_date:
            continue

        close = _safe_float(row.get("Close"))
        if close is None:
            skipped_close += 1
            if parsed <= 5:
                logger.warning("%s row %d: bad Close=%r", stock.symbol, parsed, row.get("Close"))
            continue

        exists = (
            db.query(HistoricalPrice.id)
            .filter(
                HistoricalPrice.stock_id == stock.id,
                HistoricalPrice.date == row_date,
            )
            .first()
        )
        if exists:
            skipped_dup += 1
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
        added += 1

        if added == 1:
            logger.info(
                "%s first CSV row stored: date=%s close=%.2f",
                stock.symbol, row_date, close,
            )

    return added, parsed, skipped_date, skipped_close, skipped_dup


# ---------------------------------------------------------------------------
# Core fetch-and-store
# ---------------------------------------------------------------------------

def fetch_and_store(symbol: str, db: Session, incremental: bool = True) -> dict:
    """
    Fetch daily OHLCV for *symbol* — yfinance primary, Stooq fallback.
    Store new rows in DB.

    Returns ``{"added": int, "source": str, "parsed": int, "skipped": int}``.
    """
    symbol = symbol.strip().upper()
    if not symbol or not symbol.replace(".", "").replace("-", "").isalnum():
        return {"added": 0, "source": "none", "parsed": 0, "skipped": 0}

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
                return {"added": 0, "source": "cache", "parsed": 0, "skipped": 0}

    source = "none"
    added = parsed = skipped = 0

    # ----- PRIMARY: yfinance (DataFrame, no CSV round-trip) -----
    yf_df = _fetch_yfinance(symbol, start_date)
    if yf_df is not None:
        source = "yfinance"
        added, parsed, sd, sc, sdup = _insert_from_dataframe(yf_df, stock, db, start_date)
        skipped = sd + sc + sdup
        logger.info(
            "%s yfinance insert: parsed=%d added=%d skip_date=%d skip_close=%d skip_dup=%d",
            symbol, parsed, added, sd, sc, sdup,
        )

        if not incremental and added < MIN_ROWS_FULL_FETCH:
            logger.warning(
                "%s: yfinance only produced %d rows on full fetch — trying Stooq",
                symbol, added,
            )
            yf_df = None  # trigger Stooq below

    # ----- FALLBACK: Stooq (CSV text) -----
    if yf_df is None:
        csv_text = _fetch_stooq(symbol)
        if csv_text is not None:
            source = "stooq" if added == 0 else "yfinance+stooq"
            st_added, st_parsed, sd, sc, sdup = _parse_and_insert(
                csv_text, stock, db, start_date,
            )
            logger.info(
                "%s stooq parse: parsed=%d added=%d skip_date=%d skip_close=%d skip_dup=%d",
                symbol, st_parsed, st_added, sd, sc, sdup,
            )
            added += st_added
            parsed += st_parsed
            skipped += sd + sc + sdup
        elif added == 0:
            logger.error("All sources failed for %s", symbol)
            source = "none"

    if added:
        db.commit()
    elif source != "cache":
        logger.warning(
            "WARNING: No rows added for %s from %s — parsed=%d skipped=%d — check parsing",
            symbol, source, parsed, skipped,
        )

    logger.info("fetch_and_store %s DONE: %d added from %s", symbol, added, source)
    return {"added": added, "source": source, "parsed": parsed, "skipped": skipped}


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
        fetch_and_store(symbol, db, incremental=False)
        stock = db.query(Stock).filter(Stock.symbol == symbol).first()
        if not stock:
            return []
    else:
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
            result = fetch_and_store(symbol, db, incremental=True)
            results[symbol] = result["added"]
        except Exception as exc:
            logger.error("Refresh failed for %s: %s", symbol, exc)
            results[symbol] = -1
    return results
