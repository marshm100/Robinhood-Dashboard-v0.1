import pandas as pd
from typing import List
from api.models.portfolio import Holding
from .price_service import get_historical_prices

def calculate_portfolio_returns(
    holdings: List[Holding],
    benchmark: str = "SPY",
    period: str = "1y"
) -> dict:
    valid_holdings = [h for h in holdings if h.shares > 0]
    if not valid_holdings:
        return {"error": "No valid holdings"}

    tickers = [h.ticker for h in valid_holdings]
    all_tickers = tickers + [benchmark]

    prices_df = get_historical_prices(all_tickers, period=period)
    if prices_df.empty or benchmark not in prices_df.columns:
        return {"error": "Insufficient price data"}

    # Compute daily portfolio value
    portfolio_value = pd.Series(0.0, index=prices_df.index)
    for h in valid_holdings:
        if h.ticker in prices_df.columns:
            portfolio_value += prices_df[h.ticker] * h.shares

    if portfolio_value.iloc[0] == 0:
        return {"error": "Initial portfolio value is zero"}

    portfolio_returns = (portfolio_value / portfolio_value.iloc[0] - 1) * 100
    benchmark_returns = (prices_df[benchmark] / prices_df[benchmark].iloc[0] - 1) * 100

    dates = prices_df.index.strftime("%Y-%m-%d").tolist()

    return {
        "dates": dates,
        "portfolio_returns": portfolio_returns.round(2).tolist(),
        "benchmark_returns": benchmark_returns.round(2).tolist(),
        "benchmark": benchmark,
        "period": period,
        "final_portfolio_return": round(portfolio_returns.iloc[-1], 2),
        "final_benchmark_return": round(benchmark_returns.iloc[-1], 2),
    }