import yfinance as yf
import pandas as pd
from typing import List
import time

def get_historical_prices(tickers: List[str], period: str = "1y") -> pd.DataFrame:
    """
    Robust fetch with headers, retries, backoff, and period fallback.
    """
    if not tickers:
        return pd.DataFrame()

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    max_retries = 3
    current_period = period

    for attempt in range(max_retries + 1):  # +1 for fallback attempt
        try:
            print(f"yfinance attempt {attempt+1} for {tickers} (period: {current_period})")
            data = yf.download(
                tickers,
                period=current_period,
                progress=False,
                auto_adjust=True,
                threads=True,
                headers=headers,
                timeout=30,
            )["Close"]

            if data.empty or data.isna().all().all():
                raise ValueError("Empty or all-NaN data")

            data = data.dropna(how="all").ffill().bfill()
            print(f"yfinance SUCCESS: {len(data)} rows fetched")
            return data

        except Exception as e:
            print(f"yfinance attempt {attempt+1} failed: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            elif attempt == max_retries - 1:
                # Final fallback
                current_period = "6mo"
                print("Falling back to 6mo period")
                time.sleep(2)

    print("yfinance all attempts failed")
    return pd.DataFrame()

def get_single_ticker_prices(ticker: str, period: str = "1y") -> dict:
    df = get_historical_prices([ticker], period)
    if ticker not in df.columns:
        return {}
    return {date.strftime("%Y-%m-%d"): float(price) for date, price in df[ticker].items() if pd.notna(price)}