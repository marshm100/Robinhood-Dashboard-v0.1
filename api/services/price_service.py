import logging
import pandas as pd
import yfinance as yf
from typing import List

logger = logging.getLogger(__name__)

def get_historical_prices(tickers: List[str], period: str = "1y") -> pd.DataFrame:
    """
    Fetch historical close prices for given tickers.
    Returns a DataFrame with Date index and ticker columns, even for single tickers.
    Falls back to individual downloads on batch failure.
    """
    if not tickers:
        return pd.DataFrame()

    # Dedupe and clean
    tickers = sorted(set(t.upper().strip() for t in tickers if t and t.strip()))
    if not tickers:
        return pd.DataFrame()

    logger.info(f"Fetching prices for {len(tickers)} tickers: {tickers[:5]}{'...' if len(tickers) > 5 else ''}")

    def batch_download() -> pd.DataFrame | None:
        try:
            data = yf.download(
                tickers=tickers,
                period=period,
                auto_adjust=True,
                progress=False,
                threads=True,
            )

            # Handle MultiIndex columns case (happens with multiple tickers)
            if isinstance(data.columns, pd.MultiIndex):
                data = data["Close"]
            elif "Close" in data.columns:
                data = data["Close"]
            # else: already just Close data

            # Handle single-ticker Series case
            if isinstance(data, pd.Series):
                data = data.to_frame(name=tickers[0])

            if data.empty:
                logger.warning("Batch download returned empty DataFrame")
                return None

            # Ensure all requested tickers are present (yfinance drops failed ones silently)
            if hasattr(data, 'columns'):
                missing = set(tickers) - set(data.columns)
                if missing:
                    logger.warning(f"Batch download missing tickers: {missing}")
                    return None

            # Clean the data
            data = data.dropna(how="all").ffill().bfill()
            logger.info(f"Batch download succeeded: {len(data)} rows, {len(data.columns)} tickers")
            return data

        except Exception as e:
            logger.error(f"Batch download failed: {e}")
            return None

    # Try batch first
    prices_df = batch_download()
    if prices_df is not None and not prices_df.empty:
        return prices_df

    # Fallback: individual downloads
    logger.info("Falling back to individual ticker downloads")
    individual_dfs = []
    successful_tickers = []

    for ticker in tickers:
        try:
            df = yf.download(
                tickers=ticker,
                period=period,
                auto_adjust=True,
                progress=False,
            )

            if df.empty:
                logger.warning(f"No data returned for {ticker}")
                continue

            # Extract Close column
            if "Close" in df.columns:
                close_data = df["Close"]
            else:
                close_data = df.iloc[:, 0]  # Fallback to first column

            # Single ticker always returns Series here
            ticker_df = close_data.to_frame(name=ticker)
            individual_dfs.append(ticker_df)
            successful_tickers.append(ticker)
            logger.info(f"Individual download succeeded: {ticker} ({len(ticker_df)} rows)")

        except Exception as e:
            logger.error(f"Failed to download {ticker}: {e}")

    if not individual_dfs:
        logger.error("All individual downloads failed")
        return pd.DataFrame()

    # Combine all individual downloads
    prices_df = pd.concat(individual_dfs, axis=1)
    prices_df = prices_df.dropna(how="all").ffill().bfill()

    logger.info(f"Individual fallback complete: {len(successful_tickers)}/{len(tickers)} tickers succeeded")
    return prices_df


def get_single_ticker_prices(ticker: str, period: str = "1y") -> dict:
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