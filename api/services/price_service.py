import yfinance as yf
import pandas as pd
import requests
from typing import List, Optional
from datetime import datetime, date, timedelta
from io import StringIO
import time
from sqlalchemy import func

from api.database import SessionLocal
from api.models.portfolio import Stock, PriceHistory

# ---------------------------------------------------------------------------
# Period helpers
# ---------------------------------------------------------------------------

_PERIOD_DAYS = {
    "1mo": 30,
    "3mo": 90,
    "6mo": 180,
    "1y": 365,
    "2y": 730,
    "5y": 1825,
    "10y": 3650,
    "max": 365 * 30,
}

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


def _period_to_start_date(period: str) -> date:
    """Convert period string to a start date."""
    days = _PERIOD_DAYS.get(period, 365)
    return date.today() - timedelta(days=days)


# ---------------------------------------------------------------------------
# Discovered-tickers registry
# ---------------------------------------------------------------------------

def get_all_discovered_tickers() -> List[str]:
    """Return every symbol in the stocks table."""
    db = SessionLocal()
    try:
        rows = db.query(Stock.symbol).all()
        return [r.symbol for r in rows]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Individual data sources
# ---------------------------------------------------------------------------

def _fetch_stooq(ticker: str, start_dt: date, end_dt: date) -> Optional[pd.DataFrame]:
    """Download daily closes from Stooq (primary source)."""
    try:
        d1 = start_dt.strftime("%Y%m%d")
        d2 = end_dt.strftime("%Y%m%d")
        url = (
            f"https://stooq.com/q/d/l/"
            f"?s={ticker.lower()}.us&d1={d1}&d2={d2}&i=d"
        )
        resp = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=15)
        if resp.status_code != 200 or len(resp.text) < 50:
            return None

        df = pd.read_csv(StringIO(resp.text))
        if "Close" not in df.columns or "Date" not in df.columns:
            return None
        if len(df) < 2:
            return None

        df["Date"] = pd.to_datetime(df["Date"])
        df = df[["Date", "Close"]].dropna().sort_values("Date").reset_index(drop=True)
        print(f"  Stooq OK for {ticker}: {len(df)} rows")
        return df
    except Exception as e:
        print(f"  Stooq failed for {ticker}: {e}")
        return None


def _fetch_yfinance_single(ticker: str, start_dt: date, end_dt: date) -> Optional[pd.DataFrame]:
    """Download daily closes from yfinance for one ticker (fallback)."""
    for attempt in range(3):
        try:
            data = yf.download(
                ticker,
                start=start_dt.strftime("%Y-%m-%d"),
                end=(end_dt + timedelta(days=1)).strftime("%Y-%m-%d"),
                progress=False,
                auto_adjust=True,
                headers={"User-Agent": _USER_AGENT},
                timeout=30,
            )
            if data.empty:
                raise ValueError("empty result")

            # Handle MultiIndex columns from single-ticker download
            if isinstance(data.columns, pd.MultiIndex):
                data = data.droplevel("Ticker", axis=1)

            close = data[["Close"]].dropna().reset_index()
            close.columns = ["Date", "Close"]
            if len(close) < 2:
                raise ValueError("fewer than 2 rows")

            print(f"  yfinance OK for {ticker}: {len(close)} rows (attempt {attempt+1})")
            return close
        except Exception as e:
            print(f"  yfinance attempt {attempt+1} failed for {ticker}: {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)

    return None


# ---------------------------------------------------------------------------
# fetch_and_store  –  Stooq → yfinance, then persist to price_history
# ---------------------------------------------------------------------------

def fetch_and_store(ticker: str, incremental: bool = True) -> bool:
    """
    Fetch prices for *ticker* and upsert into the price_history table.
    Stooq is tried first; yfinance is the fallback.
    incremental=True  → only fetch from last stored date onward.
    incremental=False → fetch full history (~10 years).
    """
    db = SessionLocal()
    try:
        ticker = ticker.upper()
        end_dt = date.today()

        if incremental:
            last = (
                db.query(func.max(PriceHistory.date))
                .filter(PriceHistory.symbol == ticker)
                .scalar()
            )
            if last:
                start_dt = last + timedelta(days=1)
                if start_dt >= end_dt:
                    print(f"  {ticker}: already up-to-date")
                    return True
            else:
                # No cached data at all → full prime
                start_dt = end_dt - timedelta(days=365 * 10)
        else:
            start_dt = end_dt - timedelta(days=365 * 10)

        print(f"Fetching {ticker}: {start_dt} → {end_dt} (incremental={incremental})")

        # Try Stooq first
        df = _fetch_stooq(ticker, start_dt, end_dt)

        # Fallback to yfinance
        if df is None or len(df) < 2:
            df = _fetch_yfinance_single(ticker, start_dt, end_dt)

        if df is None or len(df) < 2:
            print(f"  {ticker}: NO DATA from any source")
            return False

        # Collect existing dates so we only INSERT new rows
        existing_dates = set(
            row[0]
            for row in db.query(PriceHistory.date)
            .filter(
                PriceHistory.symbol == ticker,
                PriceHistory.date >= start_dt,
            )
            .all()
        )

        new_rows = []
        for _, row in df.iterrows():
            dt = row["Date"]
            if hasattr(dt, "date"):
                dt = dt.date()
            if dt not in existing_dates:
                new_rows.append(
                    PriceHistory(symbol=ticker, date=dt, close=float(row["Close"]))
                )

        if new_rows:
            db.bulk_save_objects(new_rows)

        # Upsert the Stock record
        db.merge(Stock(symbol=ticker, last_updated=datetime.utcnow()))
        db.commit()
        print(f"  {ticker}: stored {len(new_rows)} new rows (total fetched: {len(df)})")
        return True
    except Exception as e:
        db.rollback()
        print(f"  fetch_and_store FAILED for {ticker}: {e}")
        return False
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Public API  –  same signature as before
# ---------------------------------------------------------------------------

def get_historical_prices(tickers: List[str], period: str = "1y") -> pd.DataFrame:
    """
    Return a DataFrame of daily closes (DatetimeIndex, columns=tickers).

    Reads from the price_history cache first.  Any ticker that is missing
    or has too few rows triggers an on-demand fetch_and_store.
    """
    if not tickers:
        return pd.DataFrame()

    upper_tickers = [t.upper() for t in tickers]
    start_date = _period_to_start_date(period)

    db = SessionLocal()
    try:
        # --- First pass: read cache ---
        pivot = _load_from_cache(db, upper_tickers, start_date)

        # --- Identify tickers with insufficient cache ---
        min_rows = max(20, int(len(pivot) * 0.3)) if len(pivot) > 0 else 20
        missing = []
        for t in upper_tickers:
            if t not in pivot.columns or pivot[t].dropna().shape[0] < min_rows:
                missing.append(t)

        if missing:
            print(f"Price cache miss for: {missing}  → fetching …")
            for t in missing:
                fetch_and_store(t, incremental=False)

            # --- Second pass after fetch ---
            pivot = _load_from_cache(db, upper_tickers, start_date)

        # Final cleanup
        if not pivot.empty:
            pivot = pivot.ffill().bfill()

        return pivot
    finally:
        db.close()


def _load_from_cache(db, upper_tickers: List[str], start_date: date) -> pd.DataFrame:
    """Query price_history and return a pivoted DataFrame."""
    rows = (
        db.query(PriceHistory.date, PriceHistory.symbol, PriceHistory.close)
        .filter(
            PriceHistory.symbol.in_(upper_tickers),
            PriceHistory.date >= start_date,
        )
        .all()
    )
    if not rows:
        return pd.DataFrame()

    data = [{"date": r.date, "symbol": r.symbol, "close": r.close} for r in rows]
    pdf = pd.DataFrame(data)
    pivot = pdf.pivot_table(index="date", columns="symbol", values="close")
    pivot.index = pd.to_datetime(pivot.index)
    pivot = pivot.sort_index()
    return pivot


def get_single_ticker_prices(ticker: str, period: str = "1y") -> dict:
    df = get_historical_prices([ticker], period)
    tu = ticker.upper()
    if tu not in df.columns:
        return {}
    return {
        d.strftime("%Y-%m-%d"): float(price)
        for d, price in df[tu].items()
        if pd.notna(price)
    }


# ---------------------------------------------------------------------------
# Daily cron helper  –  called by the /api/internal/daily-price-update route
# ---------------------------------------------------------------------------

def run_daily_price_update() -> dict:
    """Incrementally update prices for every discovered ticker."""
    tickers = get_all_discovered_tickers()
    # Always include common benchmarks
    for bm in ("SPY", "QQQ", "IWM", "BND", "GLD"):
        if bm not in tickers:
            tickers.append(bm)

    results = {"updated": [], "failed": [], "skipped": []}
    for t in tickers:
        ok = fetch_and_store(t, incremental=True)
        if ok:
            results["updated"].append(t)
        else:
            results["failed"].append(t)

    results["total"] = len(tickers)
    print(f"Daily price update done: {len(results['updated'])} updated, "
          f"{len(results['failed'])} failed out of {len(tickers)}")
    return results
