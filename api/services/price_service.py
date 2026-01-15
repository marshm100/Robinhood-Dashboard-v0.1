import yfinance as yf
import pandas as pd
from typing import List

def get_historical_prices(tickers: List[str], period: str = "1y") -> pd.DataFrame:
    """
    Fetch adjusted close prices for multiple tickers.
    Valid periods: "1mo", "3mo", "6mo", "1y", "2y", "5y", "max", etc.
    """
    if not tickers:
        return pd.DataFrame()

    data = yf.download(
        tickers,
        period=period,
        progress=False,
        auto_adjust=True,
        threads=True,
    )["Close"]

    # Drop rows with all NaN and forward/backward fill remaining gaps
    data = data.dropna(how="all").ffill().bfill()
    return data

def get_single_ticker_prices(ticker: str, period: str = "1y") -> dict:
    df = get_historical_prices([ticker], period)
    if ticker not in df.columns:
        return {}
    return {date.strftime("%Y-%m-%d"): price for date, price in df[ticker].items()}