import pandas as pd
from typing import List
from api.models.portfolio import Holding
from .price_service import get_historical_prices

def compute_drawdown_metrics(value_series: pd.Series) -> dict:
    """
    Compute drawdown metrics from a portfolio value series (indexed by date).
    The series can be raw values or rebased (e.g., starting at 100 or 1.0) — drawdown is invariant.
    Returns metrics and chart data suitable for the frontend.
    """
    if value_series.empty or len(value_series) < 2:
        return {
            "max_drawdown_percent": 0.0,
            "current_drawdown_percent": 0.0,
            "longest_drawdown_days": 0,
            "drawdown_chart_data": []
        }

    # Ensure chronological order
    value_series = value_series.sort_index()

    # Running peak and drawdown series
    peak_series = value_series.cummax()
    drawdown_series = (value_series / peak_series) - 1.0

    max_dd = drawdown_series.min()
    current_dd = drawdown_series.iloc[-1]

    # Chart data (drawdown as percentage, negative values)
    chart_data = [
        {"date": date.isoformat(), "drawdown": round(float(dd) * 100, 2)}
        for date, dd in drawdown_series.items()
    ]

    # Longest drawdown duration in days (time from peak to recovery)
    longest_days = 0
    in_drawdown = False
    start_date = None
    for date, dd in drawdown_series.items():
        if dd < -1e-8 and not in_drawdown:  # start of drawdown
            in_drawdown = True
            start_date = date
        elif dd >= -1e-8 and in_drawdown:  # recovered to new high
            duration = (date - start_date).days
            longest_days = max(longest_days, duration)
            in_drawdown = False

    if in_drawdown:  # still in drawdown at end
        duration = (drawdown_series.index[-1] - start_date).days
        longest_days = max(longest_days, duration)

    return {
        "max_drawdown_percent": round(float(max_dd) * 100, 2),
        "current_drawdown_percent": round(float(current_dd) * 100, 2),
        "longest_drawdown_days": longest_days,
        "drawdown_chart_data": chart_data
    }


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

    print(f"Analysis request: tickers={tickers}, benchmark={benchmark}, period={period}")
    prices_df = get_historical_prices(all_tickers, period=period)
    if prices_df.empty or benchmark not in prices_df.columns:
        print("Price fetch returned empty - insufficient data")
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

    # Compute real drawdown metrics from the portfolio value series
    drawdown_metrics = compute_drawdown_metrics(portfolio_value)

    return {
        "dates": dates,
        "portfolio_returns": portfolio_returns.round(2).tolist(),
        "benchmark_returns": benchmark_returns.round(2).tolist(),
        "benchmark": benchmark,
        "period": period,
        "final_portfolio_return": round(portfolio_returns.iloc[-1], 2),
        "final_benchmark_return": round(benchmark_returns.iloc[-1], 2),
        "drawdown": drawdown_metrics,
    }