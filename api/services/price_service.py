"""
Price service with persistent database caching.

Fetches historical prices from yfinance and caches them in PostgreSQL/SQLite
for persistent storage across serverless function invocations.
"""
import logging
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple

import pandas as pd
import yfinance as yf
from sqlalchemy.orm import Session
from sqlalchemy import and_

from api.database import SessionLocal
from api.models.portfolio import HistoricalPrice

logger = logging.getLogger(__name__)

# Period to date range mapping
PERIOD_DAYS = {
    "1mo": 30,
    "3mo": 90,
    "6mo": 180,
    "1y": 365,
    "2y": 730,
    "5y": 1825,
}


def _period_to_date_range(period: str) -> Tuple[date, date]:
    """Convert period string to start/end dates."""
    end_date = date.today()
    days = PERIOD_DAYS.get(period, 365)
    start_date = end_date - timedelta(days=days)
    return start_date, end_date


def _load_from_db_cache(
    db: Session,
    tickers: List[str],
    start_date: date,
    end_date: date
) -> Tuple[pd.DataFrame, Dict[str, List[date]]]:
    """
    Load cached prices from database.

    Returns:
        - DataFrame with cached prices (may have gaps)
        - Dict mapping ticker -> list of missing dates
    """
    if not tickers:
        return pd.DataFrame(), {}

    # Query all cached prices for these tickers in date range
    prices = db.query(HistoricalPrice).filter(
        and_(
            HistoricalPrice.ticker.in_(tickers),
            HistoricalPrice.date >= start_date,
            HistoricalPrice.date <= end_date
        )
    ).all()

    if not prices:
        # Generate all expected dates for missing calculation
        all_dates = pd.date_range(start=start_date, end=end_date, freq='B').date
        missing = {t: list(all_dates) for t in tickers}
        return pd.DataFrame(), missing

    # Convert to DataFrame
    data = {}
    for price in prices:
        if price.ticker not in data:
            data[price.ticker] = {}
        data[price.ticker][price.date] = price.close_price

    # Build DataFrame
    df = pd.DataFrame(data)
    if not df.empty:
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()

    # Calculate missing dates per ticker
    all_dates = set(pd.date_range(start=start_date, end=end_date, freq='B').date)
    missing = {}
    for ticker in tickers:
        if ticker in df.columns:
            cached_dates = set(df[ticker].dropna().index.date)
            ticker_missing = all_dates - cached_dates
        else:
            ticker_missing = all_dates
        if ticker_missing:
            missing[ticker] = sorted(ticker_missing)

    logger.debug(f"DB cache: {len(prices)} prices loaded, {len(missing)} tickers need updates")
    return df, missing


def _save_to_db_cache(db: Session, ticker: str, prices: Dict[date, float]) -> int:
    """Save prices to database cache. Returns count of new records."""
    if not prices:
        return 0

    count = 0
    for price_date, close_price in prices.items():
        # Check if already exists (upsert logic)
        existing = db.query(HistoricalPrice).filter(
            and_(
                HistoricalPrice.ticker == ticker,
                HistoricalPrice.date == price_date
            )
        ).first()

        if existing:
            existing.close_price = close_price
            existing.fetched_at = datetime.utcnow()
        else:
            db.add(HistoricalPrice(
                ticker=ticker,
                date=price_date,
                close_price=close_price,
                fetched_at=datetime.utcnow()
            ))
            count += 1

    return count


def _fetch_from_yfinance(
    tickers: List[str],
    start_date: date,
    end_date: date
) -> pd.DataFrame:
    """
    Fetch prices from yfinance for given tickers and date range.
    Handles batch download with fallback to individual downloads.
    """
    if not tickers:
        return pd.DataFrame()

    logger.info(f"Fetching from yfinance: {len(tickers)} tickers, {start_date} to {end_date}")

    def batch_download() -> Optional[pd.DataFrame]:
        try:
            data = yf.download(
                tickers=tickers,
                start=start_date,
                end=end_date + timedelta(days=1),  # end is exclusive
                auto_adjust=True,
                progress=False,
                threads=True,
            )

            if data.empty:
                return None

            # Handle MultiIndex columns (multiple tickers)
            if isinstance(data.columns, pd.MultiIndex):
                data = data["Close"]
            elif "Close" in data.columns:
                data = data["Close"]

            # Handle single-ticker Series case
            if isinstance(data, pd.Series):
                data = data.to_frame(name=tickers[0])

            return data

        except Exception as e:
            logger.error(f"Batch download failed: {e}")
            return None

    # Try batch first
    prices_df = batch_download()
    if prices_df is not None and not prices_df.empty:
        logger.info(f"Batch download succeeded: {len(prices_df)} rows")
        return prices_df

    # Fallback: individual downloads
    logger.info("Falling back to individual ticker downloads")
    individual_dfs = []

    for ticker in tickers:
        try:
            df = yf.download(
                tickers=ticker,
                start=start_date,
                end=end_date + timedelta(days=1),
                auto_adjust=True,
                progress=False,
            )

            if df.empty:
                logger.warning(f"No data for {ticker}")
                continue

            if "Close" in df.columns:
                close_data = df["Close"]
            else:
                close_data = df.iloc[:, 0]

            ticker_df = close_data.to_frame(name=ticker)
            individual_dfs.append(ticker_df)
            logger.debug(f"Individual download: {ticker} ({len(ticker_df)} rows)")

        except Exception as e:
            logger.error(f"Failed to download {ticker}: {e}")

    if not individual_dfs:
        return pd.DataFrame()

    return pd.concat(individual_dfs, axis=1)


def get_historical_prices(tickers: List[str], period: str = "1y") -> pd.DataFrame:
    """
    Fetch historical close prices for given tickers with persistent DB caching.

    Returns a DataFrame with Date index and ticker columns.
    Uses PostgreSQL/SQLite for persistent caching across serverless invocations.
    """
    if not tickers:
        return pd.DataFrame()

    # Clean and dedupe tickers
    tickers = sorted(set(t.upper().strip() for t in tickers if t and t.strip()))
    if not tickers:
        return pd.DataFrame()

    start_date, end_date = _period_to_date_range(period)
    logger.info(f"Price request: {len(tickers)} tickers, period={period} ({start_date} to {end_date})")

    db = SessionLocal()
    try:
        # Step 1: Load from DB cache
        cached_df, missing_dates = _load_from_db_cache(db, tickers, start_date, end_date)

        # If we have complete cache, return it
        if not missing_dates:
            logger.info(f"Full cache hit: {len(tickers)} tickers")
            cached_df = cached_df.dropna(how="all").ffill().bfill()
            return cached_df

        # Step 2: Fetch missing data from yfinance
        tickers_to_fetch = list(missing_dates.keys())
        logger.info(f"Fetching {len(tickers_to_fetch)} tickers with missing data")

        # Fetch full range for simplicity (yfinance doesn't support sparse date queries)
        fresh_df = _fetch_from_yfinance(tickers_to_fetch, start_date, end_date)

        # Step 3: Save new data to DB cache
        if not fresh_df.empty:
            total_saved = 0
            for ticker in fresh_df.columns:
                ticker_prices = {
                    d.date(): float(p)
                    for d, p in fresh_df[ticker].items()
                    if pd.notna(p)
                }
                saved = _save_to_db_cache(db, ticker, ticker_prices)
                total_saved += saved

            db.commit()
            logger.info(f"Saved {total_saved} new price records to DB cache")

        # Step 4: Merge cached and fresh data
        if cached_df.empty:
            result_df = fresh_df
        elif fresh_df.empty:
            result_df = cached_df
        else:
            # Combine: fresh data takes precedence
            result_df = cached_df.combine_first(fresh_df)

        # Clean the data
        if not result_df.empty:
            result_df = result_df.dropna(how="all").ffill().bfill()

        # Log final stats
        available = set(result_df.columns) if not result_df.empty else set()
        missing = set(tickers) - available
        if missing:
            logger.warning(f"Missing price data for: {missing}")

        logger.info(f"Returning {len(result_df)} rows for {len(available)}/{len(tickers)} tickers")
        return result_df

    except Exception as e:
        logger.error(f"Price fetch error: {e}")
        db.rollback()
        # Fallback to direct yfinance on DB error
        return _fetch_from_yfinance(tickers, start_date, end_date)

    finally:
        db.close()


def get_single_ticker_prices(ticker: str, period: str = "1y") -> Dict[str, float]:
    """Get prices for a single ticker as a date->price dictionary."""
    df = get_historical_prices([ticker], period)
    ticker = ticker.upper().strip()

    if df.empty:
        logger.warning(f"No price data for {ticker}")
        return {}

    if ticker not in df.columns:
        # Try case-insensitive match
        matching = [c for c in df.columns if c.upper() == ticker]
        if matching:
            ticker = matching[0]
        else:
            logger.warning(f"Ticker {ticker} not found in columns: {list(df.columns)}")
            return {}

    return {
        date.strftime("%Y-%m-%d"): float(price)
        for date, price in df[ticker].items()
        if pd.notna(price)
    }


def get_price_on_date(ticker: str, target_date: date) -> Optional[float]:
    """
    Get the closing price for a ticker on a specific date.
    Returns the closest available price if exact date not available.
    """
    ticker = ticker.upper().strip()

    db = SessionLocal()
    try:
        # Try exact date first
        price = db.query(HistoricalPrice).filter(
            and_(
                HistoricalPrice.ticker == ticker,
                HistoricalPrice.date == target_date
            )
        ).first()

        if price:
            return price.close_price

        # Try nearby dates (within 5 days)
        nearby = db.query(HistoricalPrice).filter(
            and_(
                HistoricalPrice.ticker == ticker,
                HistoricalPrice.date >= target_date - timedelta(days=5),
                HistoricalPrice.date <= target_date + timedelta(days=5)
            )
        ).order_by(
            # Order by distance from target date
            HistoricalPrice.date
        ).all()

        if nearby:
            # Find closest date
            closest = min(nearby, key=lambda p: abs((p.date - target_date).days))
            return closest.close_price

        # Not in cache - fetch from yfinance
        df = _fetch_from_yfinance([ticker], target_date - timedelta(days=10), target_date + timedelta(days=5))
        if df.empty or ticker not in df.columns:
            return None

        # Save to cache and return
        ticker_prices = {
            d.date(): float(p)
            for d, p in df[ticker].items()
            if pd.notna(p)
        }
        _save_to_db_cache(db, ticker, ticker_prices)
        db.commit()

        # Find closest to target date
        if ticker_prices:
            closest_date = min(ticker_prices.keys(), key=lambda d: abs((d - target_date).days))
            return ticker_prices[closest_date]

        return None

    finally:
        db.close()


def clear_price_cache(ticker: Optional[str] = None, older_than_days: int = 0) -> int:
    """
    Clear price cache entries.

    Args:
        ticker: If provided, only clear this ticker. Otherwise clear all.
        older_than_days: Only clear entries older than this many days.

    Returns:
        Number of records deleted.
    """
    db = SessionLocal()
    try:
        query = db.query(HistoricalPrice)

        if ticker:
            query = query.filter(HistoricalPrice.ticker == ticker.upper())

        if older_than_days > 0:
            cutoff = datetime.utcnow() - timedelta(days=older_than_days)
            query = query.filter(HistoricalPrice.fetched_at < cutoff)

        count = query.delete()
        db.commit()
        logger.info(f"Cleared {count} price cache entries")
        return count

    finally:
        db.close()
