import pandas as pd
from typing import List, Optional
from sqlalchemy.orm import Session
from api.models.portfolio import Holding
from .price_service import get_historical_prices, get_sector_map

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
    period: str = "1y",
    db: Optional[Session] = None
) -> dict:
    valid_holdings = [h for h in holdings if h.shares > 0]
    if not valid_holdings:
        return {"error": "No valid holdings"}

    tickers = [h.ticker for h in valid_holdings]
    all_tickers = tickers + [benchmark]

    print(f"Analysis request: tickers={tickers}, benchmark={benchmark}, period={period}")
    # Map user-facing "all" to yfinance's "max" period
    yf_period = "max" if period == "all" else period
    prices_df = get_historical_prices(all_tickers, period=yf_period)
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

    # Compute sector allocation from current (latest) holdings values
    sector_allocation = []
    if db is not None:
        sector_map = get_sector_map(tickers, db)
        last_prices = prices_df.iloc[-1]
        total_value = float(portfolio_value.iloc[-1])

        sector_totals: dict = {}
        for h in valid_holdings:
            if h.ticker in last_prices:
                value = float(last_prices[h.ticker]) * h.shares
                sector = sector_map.get(h.ticker, "Unknown")
                sector_totals[sector] = sector_totals.get(sector, 0.0) + value

        if total_value > 0:
            sector_allocation = sorted(
                [
                    {
                        "sector": sector,
                        "percentage": round(val / total_value * 100, 2),
                        "value": round(val, 2),
                    }
                    for sector, val in sector_totals.items()
                ],
                key=lambda x: x["percentage"],
                reverse=True,
            )

    # Compute risk metrics from daily returns
    daily_returns = portfolio_value.pct_change().dropna()

    if len(daily_returns) < 30:
        risk_metrics = {
            "annualized_return": None,
            "annualized_volatility": None,
            "sharpe_ratio": None,
            "sortino_ratio": None,
        }
    else:
        total_days = (portfolio_value.index[-1] - portfolio_value.index[0]).days
        total_return = portfolio_value.iloc[-1] / portfolio_value.iloc[0] - 1
        ann_return = (
            ((1 + total_return) ** (365 / total_days) - 1) * 100
            if total_days > 0
            else 0.0
        )

        ann_vol = float(daily_returns.std(ddof=0)) * (252 ** 0.5) * 100

        risk_free = 4.0  # approximate current T-bill rate
        sharpe = (ann_return - risk_free) / ann_vol if ann_vol > 0 else 0.0

        downside = daily_returns[daily_returns < 0]
        downside_dev = (
            float(downside.std(ddof=0)) * (252 ** 0.5) * 100
            if len(downside) > 0
            else 0.0
        )
        sortino = (ann_return - risk_free) / downside_dev if downside_dev > 0 else 0.0

        risk_metrics = {
            "annualized_return": round(float(ann_return), 2),
            "annualized_volatility": round(float(ann_vol), 2),
            "sharpe_ratio": round(float(sharpe), 2),
            "sortino_ratio": round(float(sortino), 2),
        }

    return {
        "dates": dates,
        "portfolio_returns": portfolio_returns.round(2).tolist(),
        "benchmark_returns": benchmark_returns.round(2).tolist(),
        "benchmark": benchmark,
        "period": period,
        "final_portfolio_return": round(portfolio_returns.iloc[-1], 2),
        "final_benchmark_return": round(benchmark_returns.iloc[-1], 2),
        "drawdown": drawdown_metrics,
        "sector_allocation": sector_allocation,
        "risk_metrics": risk_metrics,
    }