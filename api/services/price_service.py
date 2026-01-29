"""
Price service with persistent database caching and resilient fetching.

Fetches historical prices from yfinance and caches them in PostgreSQL/SQLite
for persistent storage across serverless function invocations.

Handles partial data gracefully for leveraged/newer ETFs with limited history.
"""
import logging
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple, NamedTuple
from dataclasses import dataclass, field

import pandas as pd
import yfinance as yf
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

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
    "max": 3650,  # ~10 years
}

# Fallback periods to try if longer periods fail
PERIOD_FALLBACKS = ["5y", "2y", "1y", "6mo", "3mo", "1mo"]


@dataclass
class PriceResult:
    """Result from get_historical_prices with metadata."""
    df: pd.DataFrame
    missing_tickers: List[str] = field(default_factory=list)
    partial_tickers: Dict[str, str] = field(default_factory=dict)  # ticker -> "data since YYYY-MM-DD"
    failed_tickers: List[str] = field(default_factory=list)
    is_partial: bool = False


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
        all_dates = pd.date_range(start=start_date, end=end_date, freq='B').date
        missing = {t: list(all_dates) for t in tickers}
        return pd.DataFrame(), missing

    # Convert to DataFrame
    data = {}
    for price in prices:
        if price.ticker not in data:
            data[price.ticker] = {}
        data[price.ticker][price.date] = price.close_price

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


def _get_latest_cached_price(db: Session, ticker: str) -> Optional[Tuple[date, float]]:
    """Get the most recent cached price for a ticker."""
    latest = db.query(HistoricalPrice).filter(
        HistoricalPrice.ticker == ticker
    ).order_by(desc(HistoricalPrice.date)).first()

    if latest:
        return (latest.date, latest.close_price)
    return None


def _get_current_price(ticker: str) -> Optional[float]:
    """Fetch current price for a ticker using yfinance."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        # Try various price fields
        for field in ['regularMarketPrice', 'currentPrice', 'previousClose', 'open']:
            if field in info and info[field]:
                price = float(info[field])
                if price > 0:
                    logger.info(f"Got current price for {ticker}: ${price:.2f}")
                    return price

        # Fallback: try to get from recent history
        hist = stock.history(period="5d")
        if not hist.empty and 'Close' in hist.columns:
            price = float(hist['Close'].iloc[-1])
            if price > 0:
                logger.info(f"Got recent price for {ticker} from history: ${price:.2f}")
                return price

    except Exception as e:
        logger.warning(f"Failed to get current price for {ticker}: {e}")

    return None


def _save_to_db_cache(db: Session, ticker: str, prices: Dict[date, float]) -> int:
    """Save prices to database cache. Returns count of new records."""
    if not prices:
        return 0

    count = 0
    for price_date, close_price in prices.items():
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


def _fetch_single_ticker(
    ticker: str,
    start_date: date,
    end_date: date,
    fallback_periods: bool = True
) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    Fetch historical prices for a single ticker with period fallbacks.

    Returns:
        - DataFrame with prices (or None if completely failed)
        - Error message if failed (or None if success)
    """
    # Calculate days requested
    days_requested = (end_date - start_date).days

    # Determine which periods to try
    if fallback_periods:
        periods_to_try = []
        for period in PERIOD_FALLBACKS:
            period_days = PERIOD_DAYS.get(period, 365)
            if period_days <= days_requested * 1.5:  # Allow some buffer
                periods_to_try.append(period)
        if not periods_to_try:
            periods_to_try = ["1mo"]
    else:
        periods_to_try = [None]  # Use explicit dates

    last_error = None

    for period in periods_to_try:
        try:
            if period:
                df = yf.download(
                    tickers=ticker,
                    period=period,
                    auto_adjust=True,
                    progress=False,
                )
            else:
                df = yf.download(
                    tickers=ticker,
                    start=start_date,
                    end=end_date + timedelta(days=1),
                    auto_adjust=True,
                    progress=False,
                )

            if df.empty:
                last_error = f"Empty data for period {period}"
                continue

            # Extract Close prices
            if "Close" in df.columns:
                close_data = df["Close"]
            elif isinstance(df.columns, pd.MultiIndex):
                close_data = df["Close"][ticker] if ticker in df["Close"].columns else df.iloc[:, 0]
            else:
                close_data = df.iloc[:, 0]

            result_df = close_data.to_frame(name=ticker)

            if len(result_df) > 0:
                logger.debug(f"Fetched {ticker}: {len(result_df)} rows (period={period})")
                return result_df, None

        except Exception as e:
            last_error = str(e)
            logger.debug(f"Failed to fetch {ticker} with period {period}: {e}")
            continue

    return None, last_error or "No data available"


def _fetch_from_yfinance_resilient(
    tickers: List[str],
    start_date: date,
    end_date: date,
    db: Session
) -> Tuple[pd.DataFrame, List[str], Dict[str, str]]:
    """
    Fetch prices from yfinance with resilient handling.

    Returns:
        - DataFrame with all available prices
        - List of completely failed tickers
        - Dict of partial tickers -> earliest date string
    """
    if not tickers:
        return pd.DataFrame(), [], {}

    logger.info(f"Fetching from yfinance: {len(tickers)} tickers, {start_date} to {end_date}")

    individual_dfs = []
    failed_tickers = []
    partial_tickers = {}

    # Try batch download first for efficiency
    batch_success = set()
    try:
        batch_data = yf.download(
            tickers=tickers if len(tickers) > 1 else tickers[0],
            start=start_date,
            end=end_date + timedelta(days=1),
            auto_adjust=True,
            progress=False,
            threads=True,
        )

        if not batch_data.empty:
            # Handle MultiIndex columns
            if isinstance(batch_data.columns, pd.MultiIndex):
                close_data = batch_data["Close"]
            elif "Close" in batch_data.columns:
                close_data = batch_data["Close"]
                if isinstance(close_data, pd.Series):
                    close_data = close_data.to_frame(name=tickers[0])
            else:
                close_data = batch_data

            if isinstance(close_data, pd.Series):
                close_data = close_data.to_frame(name=tickers[0])

            for ticker in tickers:
                if ticker in close_data.columns:
                    ticker_data = close_data[[ticker]].dropna()
                    if len(ticker_data) > 0:
                        individual_dfs.append(ticker_data)
                        batch_success.add(ticker)

                        # Check if partial data
                        first_date = ticker_data.index[0].date()
                        if first_date > start_date + timedelta(days=5):
                            partial_tickers[ticker] = first_date.isoformat()
                            logger.info(f"{ticker}: partial data available from {first_date}")

            logger.info(f"Batch download: {len(batch_success)}/{len(tickers)} tickers succeeded")

    except Exception as e:
        logger.warning(f"Batch download failed: {e}, falling back to individual")

    # Individual downloads for remaining tickers
    remaining = [t for t in tickers if t not in batch_success]

    for ticker in remaining:
        df, error = _fetch_single_ticker(ticker, start_date, end_date, fallback_periods=True)

        if df is not None and not df.empty:
            individual_dfs.append(df)

            # Check if partial data
            first_date = df.index[0].date()
            if first_date > start_date + timedelta(days=5):
                partial_tickers[ticker] = first_date.isoformat()
                logger.info(f"{ticker}: partial data from {first_date}")
        else:
            # Try to get current price as fallback
            current_price = _get_current_price(ticker)
            if current_price:
                # Create a single-row DataFrame with today's price
                today_df = pd.DataFrame(
                    {ticker: [current_price]},
                    index=pd.DatetimeIndex([datetime.now()])
                )
                individual_dfs.append(today_df)
                partial_tickers[ticker] = date.today().isoformat()
                logger.info(f"{ticker}: using current price ${current_price:.2f} as fallback")

                # Save to cache
                _save_to_db_cache(db, ticker, {date.today(): current_price})
            else:
                # Check if we have any cached price at all
                cached = _get_latest_cached_price(db, ticker)
                if cached:
                    cached_date, cached_price = cached
                    today_df = pd.DataFrame(
                        {ticker: [cached_price]},
                        index=pd.DatetimeIndex([datetime.now()])
                    )
                    individual_dfs.append(today_df)
                    partial_tickers[ticker] = cached_date.isoformat()
                    logger.info(f"{ticker}: using cached price from {cached_date}")
                else:
                    failed_tickers.append(ticker)
                    logger.warning(f"{ticker}: completely failed - {error}")

    if not individual_dfs:
        return pd.DataFrame(), failed_tickers, partial_tickers

    # Combine all DataFrames
    result_df = pd.concat(individual_dfs, axis=1)

    return result_df, failed_tickers, partial_tickers


def get_historical_prices(
    tickers: List[str],
    period: str = "1y",
    return_metadata: bool = False
) -> pd.DataFrame | PriceResult:
    """
    Fetch historical close prices for given tickers with persistent DB caching.

    Resilient handling for leveraged/newer ETFs with limited history:
    - Tries batch download, falls back to individual
    - Uses period fallbacks (5y → 2y → 1y → 6mo)
    - Gets current price for tickers with no history
    - Never fails completely - always returns available data

    Args:
        tickers: List of ticker symbols
        period: Time period (1mo, 3mo, 6mo, 1y, 2y, 5y, max)
        return_metadata: If True, return PriceResult with metadata

    Returns:
        DataFrame with Date index and ticker columns (or PriceResult if return_metadata=True)
    """
    if not tickers:
        if return_metadata:
            return PriceResult(df=pd.DataFrame())
        return pd.DataFrame()

    # Clean and dedupe tickers
    tickers = sorted(set(t.upper().strip() for t in tickers if t and t.strip()))
    if not tickers:
        if return_metadata:
            return PriceResult(df=pd.DataFrame())
        return pd.DataFrame()

    start_date, end_date = _period_to_date_range(period)
    logger.info(f"Price request: {len(tickers)} tickers, period={period} ({start_date} to {end_date})")

    db = SessionLocal()
    missing_tickers = []
    partial_tickers = {}
    failed_tickers = []

    try:
        # Step 1: Load from DB cache
        cached_df, missing_dates = _load_from_db_cache(db, tickers, start_date, end_date)

        # If we have complete cache for all tickers, return it
        if not missing_dates:
            logger.info(f"Full cache hit: {len(tickers)} tickers")
            result_df = cached_df.dropna(how="all").ffill().bfill()
            if return_metadata:
                return PriceResult(df=result_df)
            return result_df

        # Step 2: Fetch missing data from yfinance with resilient handling
        tickers_to_fetch = list(missing_dates.keys())
        logger.info(f"Fetching {len(tickers_to_fetch)} tickers with missing data")

        fresh_df, failed, partial = _fetch_from_yfinance_resilient(
            tickers_to_fetch, start_date, end_date, db
        )

        failed_tickers = failed
        partial_tickers = partial

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
            result_df = cached_df.combine_first(fresh_df)

        # Step 5: Handle missing tickers - fill with constants if we have any price
        for ticker in tickers:
            if ticker not in result_df.columns:
                # Try to get any cached price
                cached = _get_latest_cached_price(db, ticker)
                if cached:
                    _, price = cached
                    result_df[ticker] = price
                    partial_tickers[ticker] = "latest cached"
                    logger.info(f"Filled {ticker} with cached price: ${price:.2f}")
                else:
                    missing_tickers.append(ticker)

        # Clean the data
        if not result_df.empty:
            result_df = result_df.dropna(how="all").ffill().bfill()

        # Log final stats
        available = set(result_df.columns) if not result_df.empty else set()
        still_missing = set(tickers) - available
        if still_missing:
            missing_tickers = list(still_missing)
            logger.warning(f"Still missing price data for: {missing_tickers}")

        is_partial = bool(partial_tickers or missing_tickers or failed_tickers)

        logger.info(
            f"Returning {len(result_df)} rows for {len(available)}/{len(tickers)} tickers "
            f"(partial={len(partial_tickers)}, failed={len(failed_tickers)})"
        )

        if return_metadata:
            return PriceResult(
                df=result_df,
                missing_tickers=missing_tickers,
                partial_tickers=partial_tickers,
                failed_tickers=failed_tickers,
                is_partial=is_partial
            )
        return result_df

    except Exception as e:
        logger.error(f"Price fetch error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()

        # Emergency fallback - try direct yfinance
        try:
            fresh_df, failed, partial = _fetch_from_yfinance_resilient(
                tickers, start_date, end_date, db
            )
            if return_metadata:
                return PriceResult(
                    df=fresh_df,
                    missing_tickers=failed,
                    partial_tickers=partial,
                    failed_tickers=failed,
                    is_partial=True
                )
            return fresh_df
        except:
            if return_metadata:
                return PriceResult(df=pd.DataFrame(), missing_tickers=tickers, is_partial=True)
            return pd.DataFrame()

    finally:
        db.close()


def refresh_prices_for_portfolio(portfolio_id: int, force: bool = False) -> Dict:
    """
    Refresh historical prices for all holdings in a portfolio.

    Args:
        portfolio_id: Portfolio ID
        force: If True, clear cache and re-fetch all

    Returns:
        Dict with refresh stats
    """
    from api.models.portfolio import Holding

    db = SessionLocal()
    try:
        # Get all tickers for this portfolio
        holdings = db.query(Holding).filter(
            Holding.portfolio_id == portfolio_id
        ).all()

        tickers = list(set(h.ticker.upper() for h in holdings if h.ticker))

        if not tickers:
            return {"status": "error", "message": "No holdings found"}

        # Optionally clear cache
        if force:
            for ticker in tickers:
                db.query(HistoricalPrice).filter(
                    HistoricalPrice.ticker == ticker
                ).delete()
            db.commit()
            logger.info(f"Cleared price cache for {len(tickers)} tickers")

        # Fetch fresh prices
        result = get_historical_prices(tickers, period="5y", return_metadata=True)

        return {
            "status": "success",
            "tickers_requested": len(tickers),
            "tickers_fetched": len(result.df.columns) if not result.df.empty else 0,
            "missing_tickers": result.missing_tickers,
            "partial_tickers": result.partial_tickers,
            "failed_tickers": result.failed_tickers,
            "data_points": len(result.df) * len(result.df.columns) if not result.df.empty else 0,
        }

    finally:
        db.close()


def get_single_ticker_prices(ticker: str, period: str = "1y") -> Dict[str, float]:
    """Get prices for a single ticker as a date->price dictionary."""
    result = get_historical_prices([ticker], period, return_metadata=True)
    ticker = ticker.upper().strip()

    if result.df.empty:
        logger.warning(f"No price data for {ticker}")
        return {}

    if ticker not in result.df.columns:
        matching = [c for c in result.df.columns if c.upper() == ticker]
        if matching:
            ticker = matching[0]
        else:
            logger.warning(f"Ticker {ticker} not found in columns: {list(result.df.columns)}")
            return {}

    return {
        dt.strftime("%Y-%m-%d"): float(price)
        for dt, price in result.df[ticker].items()
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
        ).order_by(HistoricalPrice.date).all()

        if nearby:
            closest = min(nearby, key=lambda p: abs((p.date - target_date).days))
            return closest.close_price

        # Not in cache - fetch from yfinance
        df, error = _fetch_single_ticker(
            ticker,
            target_date - timedelta(days=10),
            target_date + timedelta(days=5),
            fallback_periods=False
        )

        if df is None or df.empty or ticker not in df.columns:
            # Try current price
            current = _get_current_price(ticker)
            if current:
                _save_to_db_cache(db, ticker, {date.today(): current})
                db.commit()
                return current
            return None

        # Save to cache
        ticker_prices = {
            d.date(): float(p)
            for d, p in df[ticker].items()
            if pd.notna(p)
        }
        _save_to_db_cache(db, ticker, ticker_prices)
        db.commit()

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
