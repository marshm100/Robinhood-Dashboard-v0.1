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

        logger.info("yfinance %s: df.shape=%s, empty=%s", symbol, df.shape, df.empty)

        if df.empty:
            logger.warning("yfinance returned empty DataFrame for %s", symbol)
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
        logger.error("yfinance fallback failed for %s: %s", symbol, exc, exc_info=True)
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

def fetch_and_store(symbol: str, db: Session, incremental: bool = True) -> dict:
    """
    Fetch daily OHLCV for *symbol* from Stooq (primary) or yfinance (fallback),
    store new rows in DB.

    Returns dict: {"records_added": int, "source": str, "skip_reasons": dict,
                    "total_csv_rows": int, "sample_skipped_dates": list}
    """
    result: Dict = {
        "records_added": 0,
        "source": "none",
        "skip_reasons": {},
        "total_csv_rows": 0,
        "sample_skipped_dates": [],
    }
    symbol = symbol.strip().upper()
    if not symbol or not symbol.replace(".", "").replace("-", "").isalnum():
        result["skip_reasons"]["invalid_symbol"] = 1
        return result

    stock = _get_or_create_stock(db, symbol)

    # --- Diagnostic: log stock_id and existing row count ---
    existing_count = (
        db.query(func.count(HistoricalPrice.id))
        .filter(HistoricalPrice.stock_id == stock.id)
        .scalar()
    ) or 0
    logger.info(
        "fetch_and_store %s: stock_id=%s, existing_rows=%d, incremental=%s",
        symbol, stock.id, existing_count, incremental,
    )

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
                result["skip_reasons"]["already_up_to_date"] = 1
                return result

    # Try Stooq first, then yfinance
    csv_text = _fetch_stooq(symbol)
    source = "stooq"
    if csv_text is None:
        logger.info("Stooq returned None for %s, trying yfinance fallback", symbol)
        csv_text = _fetch_yfinance(symbol, start_date)
        source = "yfinance"
    if csv_text is None:
        logger.error("All sources failed for %s", symbol)
        result["skip_reasons"]["all_sources_failed"] = 1
        return result

    result["source"] = source

    # --- Parse CSV rows into candidate records first, then bulk-insert ---
    skip_reasons: Dict[str, int] = {}
    sample_skipped_dates: List[str] = []
    candidates: list = []
    reader = csv.DictReader(StringIO(csv_text))
    total_rows = 0

    for row in reader:
        total_rows += 1

        # --- Normalize field names to lowercase, strip whitespace from values ---
        row = {k.lower().strip(): v.strip() if isinstance(v, str) else v for k, v in row.items()}

        # Log first 5 raw rows for diagnostics
        if total_rows <= 5:
            logger.info(
                "%s row %d raw (source=%s): %s",
                symbol, total_rows, source, dict(row),
            )

        # --- Parse date ---
        date_str = (row.get("date") or "").strip()
        if not date_str:
            skip_reasons["no_date"] = skip_reasons.get("no_date", 0) + 1
            continue
        try:
            row_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            skip_reasons["bad_date_format"] = skip_reasons.get("bad_date_format", 0) + 1
            if total_rows <= 5:
                logger.warning("%s: bad date format: %r", symbol, date_str)
            continue

        if start_date and row_date < start_date:
            skip_reasons["before_start_date"] = skip_reasons.get("before_start_date", 0) + 1
            continue

        # --- Parse close price: strip commas, try float ---
        close_str = row.get("close")
        if not close_str:
            skip_reasons["no_close_value"] = skip_reasons.get("no_close_value", 0) + 1
            continue

        close_str = close_str.replace(",", "")
        try:
            close = float(close_str)
        except (ValueError, TypeError):
            skip_reasons["close_not_numeric"] = skip_reasons.get("close_not_numeric", 0) + 1
            if skip_reasons.get("close_not_numeric", 0) <= 5:
                logger.warning("%s: close not numeric: %r", symbol, close_str)
            continue

        if close <= 0:
            skip_reasons["close_lte_zero"] = skip_reasons.get("close_lte_zero", 0) + 1
            continue

        # --- Parse OHLV (optional, tolerant) ---
        open_ = _safe_float((row.get("open") or "").replace(",", ""))
        high = _safe_float((row.get("high") or "").replace(",", ""))
        low = _safe_float((row.get("low") or "").replace(",", ""))
        volume = _safe_int(row.get("volume"))

        if total_rows <= 5:
            logger.info("%s row %d parsed close=%.4f", symbol, total_rows, close)

        candidates.append({
            "date": row_date,
            "close": close,
            "open": open_,
            "high": high,
            "low": low,
            "volume": volume,
        })

    logger.info(
        "%s: parsed %d candidates from %d CSV rows (skips so far: %s)",
        symbol, len(candidates), total_rows, skip_reasons,
    )

    # --- Insert phase: strategy depends on incremental flag ---
    records_added = 0

    if not incremental:
        # FULL FETCH (prime-cache): batch INSERT … ON CONFLICT DO NOTHING.
        # No per-row SELECT, no per-row flush.  The DB unique constraint
        # (uq_stock_date) silently skips rows that already exist.
        db.flush()  # flush any pending ORM state (e.g. new Stock row)

        # Dialect-specific insert with on_conflict_do_nothing
        dialect_name = db.bind.dialect.name
        if dialect_name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as dialect_insert
        else:
            from sqlalchemy.dialects.sqlite import insert as dialect_insert

        rows = [
            {
                "stock_id": stock.id,
                "date": cand["date"],
                "open": cand["open"],
                "high": cand["high"],
                "low": cand["low"],
                "close": cand["close"],
                "volume": cand["volume"],
            }
            for cand in candidates
        ]

        logger.info(
            "Batch insert for full fetch %s: candidates=%d, existing_before=%d",
            symbol, len(rows), existing_count,
        )

        # Insert in chunks of 500 to stay within DB parameter limits
        CHUNK = 500
        for i in range(0, len(rows), CHUNK):
            chunk = rows[i : i + CHUNK]
            stmt = dialect_insert(HistoricalPrice.__table__).values(chunk)
            stmt = stmt.on_conflict_do_nothing(
                index_elements=["stock_id", "date"],
            )
            result_proxy = db.execute(stmt)
            records_added += result_proxy.rowcount

        db.commit()

        db_ignored = len(candidates) - records_added
        if db_ignored > 0:
            skip_reasons["db_ignored_duplicate"] = db_ignored
            # Sample a few dates that were already present
            if existing_count > 0:
                existing_dates = (
                    db.query(HistoricalPrice.date)
                    .filter(HistoricalPrice.stock_id == stock.id)
                    .order_by(HistoricalPrice.date.desc())
                    .limit(10)
                    .all()
                )
                sample_skipped_dates = [d.isoformat() for (d,) in existing_dates]
    else:
        # INCREMENTAL: per-row duplicate check (small row counts expected)
        for cand in candidates:
            exists = (
                db.query(HistoricalPrice.id)
                .filter(
                    HistoricalPrice.stock_id == stock.id,
                    HistoricalPrice.date == cand["date"],
                )
                .scalar()
            )
            if exists is not None:
                skip_reasons["duplicate"] = skip_reasons.get("duplicate", 0) + 1
                if len(sample_skipped_dates) < 10:
                    sample_skipped_dates.append(cand["date"].isoformat())
                if skip_reasons.get("duplicate", 0) <= 5:
                    logger.debug(
                        "%s: skipping duplicate date %s (existing id=%s)",
                        symbol, cand["date"], exists,
                    )
                continue

            db.add(
                HistoricalPrice(
                    stock_id=stock.id,
                    date=cand["date"],
                    open=cand["open"],
                    high=cand["high"],
                    low=cand["low"],
                    close=cand["close"],
                    volume=cand["volume"],
                )
            )
            records_added += 1

        if records_added:
            db.commit()

    logger.info(
        "fetch_and_store %s: source=%s, total_csv_rows=%d, candidates=%d, "
        "records_added=%d, skip_reasons=%s",
        symbol, source, total_rows, len(candidates), records_added, skip_reasons,
    )
    result["records_added"] = records_added
    result["skip_reasons"] = skip_reasons
    result["total_csv_rows"] = total_rows
    result["sample_skipped_dates"] = sample_skipped_dates
    return result


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
        res = fetch_and_store(symbol, db, incremental=False)
        logger.info("get_prices first-fetch %s: %s", symbol, res)
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


def refresh_all_tickers(db: Session) -> Dict[str, dict]:
    """
    Incrementally refresh all discovered tickers.
    Returns {symbol: fetch_result_dict}.
    """
    tickers = discover_tickers(db)
    results: Dict[str, dict] = {}
    for symbol in tickers:
        try:
            results[symbol] = fetch_and_store(symbol, db, incremental=True)
        except Exception as exc:
            logger.error("Refresh failed for %s: %s", symbol, exc)
            results[symbol] = {"records_added": -1, "error": str(exc)}
    return results
