import logging
import pandas as pd
from typing import List
from api.models.portfolio import Holding
from .price_service import get_historical_prices

logger = logging.getLogger(__name__)

def calculate_portfolio_returns(
    holdings: List[Holding],
    benchmark: str = "SPY",
    period: str = "1y"
) -> dict:
    valid_holdings = [h for h in holdings if h.shares > 0]
    if not valid_holdings:
        logger.warning("No valid holdings provided")
        return {"error": "No valid holdings"}

    tickers = [h.ticker.upper() for h in valid_holdings]
    all_tickers = tickers + [benchmark.upper()]

    logger.info(f"Analysis request: {len(tickers)} tickers, benchmark={benchmark}, period={period}")
    prices_df = get_historical_prices(all_tickers, period=period)

    if prices_df.empty:
        logger.error("Price fetch returned empty DataFrame")
        return {"error": "Unable to fetch price data"}

    # Check which tickers we got
    available_tickers = set(prices_df.columns)
    missing_tickers = set(tickers) - available_tickers
    if missing_tickers:
        logger.warning(f"Missing price data for tickers: {missing_tickers}")

    benchmark_upper = benchmark.upper()
    if benchmark_upper not in prices_df.columns:
        logger.error(f"Benchmark {benchmark} not in price data columns: {list(prices_df.columns)}")
        return {"error": f"Unable to fetch benchmark data for {benchmark}"}

    # Compute daily portfolio value
    portfolio_value = pd.Series(0.0, index=prices_df.index)
    included_holdings = []

    for h in valid_holdings:
        ticker_upper = h.ticker.upper()
        if ticker_upper in prices_df.columns:
            portfolio_value += prices_df[ticker_upper] * h.shares
            included_holdings.append(h.ticker)
        else:
            logger.warning(f"Skipping {h.ticker}: no price data available")

    if not included_holdings:
        logger.error("No holdings had available price data")
        return {"error": "No price data available for any holdings"}

    logger.info(f"Calculating returns for {len(included_holdings)}/{len(valid_holdings)} holdings")

    # Check for zero initial value
    if portfolio_value.iloc[0] == 0 or pd.isna(portfolio_value.iloc[0]):
        logger.error("Initial portfolio value is zero or NaN")
        return {"error": "Initial portfolio value is zero - check holdings data"}

    portfolio_returns = (portfolio_value / portfolio_value.iloc[0] - 1) * 100
    benchmark_returns = (prices_df[benchmark_upper] / prices_df[benchmark_upper].iloc[0] - 1) * 100

    dates = prices_df.index.strftime("%Y-%m-%d").tolist()

    result = {
        "dates": dates,
        "portfolio_returns": portfolio_returns.round(2).tolist(),
        "benchmark_returns": benchmark_returns.round(2).tolist(),
        "benchmark": benchmark,
        "period": period,
        "final_portfolio_return": round(float(portfolio_returns.iloc[-1]), 2),
        "final_benchmark_return": round(float(benchmark_returns.iloc[-1]), 2),
        "holdings_included": len(included_holdings),
        "holdings_total": len(valid_holdings),
        "missing_tickers": list(missing_tickers) if missing_tickers else [],
    }

    logger.info(f"Analysis complete: portfolio={result['final_portfolio_return']}%, benchmark={result['final_benchmark_return']}%")
    return result