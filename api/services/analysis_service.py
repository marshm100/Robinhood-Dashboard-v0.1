import pandas as pd
import numpy as np
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

    # --- Rolling Returns (1Y, 2Y, 3Y CAGR) ---
    rolling_returns = {}
    windows = {"1y": 252, "2y": 504, "3y": 756}
    for label, window in windows.items():
        if len(portfolio_value) > window:
            rolling_cagr = (
                (portfolio_value / portfolio_value.shift(window)) ** (252 / window) - 1
            ) * 100
            # Drop NaN values from the shift
            valid = rolling_cagr.dropna()
            rolling_returns[label] = [
                {"date": d.strftime("%Y-%m-%d"), "value": round(float(v), 2)}
                for d, v in valid.items()
                if np.isfinite(v)
            ]
        else:
            rolling_returns[label] = []

    # --- Annual Returns (portfolio vs benchmark, by calendar year) ---
    annual_returns = []
    pv = portfolio_value.copy()
    bv = prices_df[benchmark].copy()
    pv.index = pd.to_datetime(pv.index)
    bv.index = pd.to_datetime(bv.index)

    years = sorted(pv.index.year.unique())
    for year in years:
        pv_year = pv[pv.index.year == year]
        bv_year = bv[bv.index.year == year]
        if len(pv_year) < 2 or len(bv_year) < 2:
            continue
        port_ret = (pv_year.iloc[-1] / pv_year.iloc[0] - 1) * 100
        bench_ret = (bv_year.iloc[-1] / bv_year.iloc[0] - 1) * 100
        annual_returns.append({
            "year": int(year),
            "portfolio": round(float(port_ret), 2),
            "benchmark": round(float(bench_ret), 2),
        })

    # --- Drawdown (underwater chart) ---
    peak = portfolio_value.cummax()
    drawdown = (portfolio_value / peak - 1) * 100
    drawdown_data = [
        {"date": d.strftime("%Y-%m-%d"), "drawdown": round(float(v), 2)}
        for d, v in drawdown.items()
    ]
    max_drawdown = round(float(drawdown.min()), 2)

    # --- Monte Carlo Simulation (10-year forward projection) ---
    monte_carlo = None
    daily_returns = portfolio_value.pct_change().dropna()
    if len(daily_returns) >= 30:
        mean_daily = float(daily_returns.mean())
        std_daily = float(daily_returns.std())
        simulations = 10000
        mc_years = 10
        days = mc_years * 252
        rng = np.random.default_rng(seed=42)
        sim_returns = rng.normal(mean_daily, std_daily, (days, simulations))
        sim_paths = np.cumprod(1 + sim_returns, axis=0) * float(portfolio_value.iloc[-1])
        percentiles = [5, 25, 50, 75, 95]
        # Sample at yearly intervals for chart data (every 252 days)
        yearly_indices = [i for i in range(251, days, 252)]  # end of year 1..10
        yearly_indices = [0] + yearly_indices  # prepend day 0 for start
        monte_carlo = {
            "current_value": round(float(portfolio_value.iloc[-1]), 2),
            "percentiles": percentiles,
            "years": list(range(0, mc_years + 1)),
            "data": {},
        }
        for p in percentiles:
            pct_line = np.percentile(sim_paths, p, axis=1)
            # year 0 = current value, then yearly snapshots
            values = [round(float(portfolio_value.iloc[-1]), 2)]
            for idx in yearly_indices[1:]:
                values.append(round(float(pct_line[idx]), 2))
            monte_carlo["data"][str(p)] = values

    return {
        "dates": dates,
        "portfolio_returns": portfolio_returns.round(2).tolist(),
        "benchmark_returns": benchmark_returns.round(2).tolist(),
        "benchmark": benchmark,
        "period": period,
        "final_portfolio_return": round(portfolio_returns.iloc[-1], 2),
        "final_benchmark_return": round(benchmark_returns.iloc[-1], 2),
        "rolling_returns": rolling_returns,
        "annual_returns": annual_returns,
        "drawdown_data": drawdown_data,
        "max_drawdown": max_drawdown,
        "monte_carlo": monte_carlo,
    }
