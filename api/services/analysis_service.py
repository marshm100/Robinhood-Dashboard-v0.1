import pandas as pd
import numpy as np
import requests
import zipfile
import io
from typing import List
from api.models.portfolio import Holding
from .price_service import get_historical_prices

FF_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip"

def _fetch_ff_factors() -> pd.DataFrame | None:
    """Download and parse Fama-French 3-factor monthly data.

    Returns DataFrame indexed by period (YYYYMM int) with columns:
    Mkt-RF, SMB, HML, RF  (all in percent, e.g. 1.5 means 1.5%).
    Returns None on failure.
    """
    try:
        resp = requests.get(FF_URL, timeout=30)
        resp.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            csv_name = [n for n in zf.namelist() if n.endswith(".CSV") or n.endswith(".csv")][0]
            raw = zf.read(csv_name).decode("utf-8")

        # Parse the monthly section (stop before annual section)
        lines = raw.splitlines()
        data_rows = []
        header_found = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if header_found:
                    break  # blank line after data = end of monthly section
                continue
            # Detect the header row by looking for "Mkt-RF"
            if "Mkt-RF" in stripped and not header_found:
                header_found = True
                continue
            if header_found:
                parts = stripped.split(",")
                if len(parts) < 4:
                    break
                period_str = parts[0].strip()
                # Monthly rows are 6 digits (YYYYMM); skip annual (4 digits)
                if not period_str.isdigit() or len(period_str) != 6:
                    break
                try:
                    vals = [float(x.strip()) for x in parts[1:5]]
                    data_rows.append([int(period_str)] + vals)
                except ValueError:
                    break

        if not data_rows:
            return None

        df = pd.DataFrame(data_rows, columns=["period", "Mkt-RF", "SMB", "HML", "RF"])
        df = df.set_index("period")
        return df
    except Exception as e:
        print(f"FF factor fetch failed: {e}")
        return None

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

    # --- Fama-French 3-Factor Regression ---
    factor_regression = None
    try:
        # Resample daily portfolio value to monthly returns
        pv_dt = portfolio_value.copy()
        pv_dt.index = pd.to_datetime(pv_dt.index)
        monthly_pv = pv_dt.resample("ME").last()
        monthly_port_ret = monthly_pv.pct_change().dropna() * 100  # in percent

        if len(monthly_port_ret) >= 24:
            ff_df = _fetch_ff_factors()
            if ff_df is not None:
                # Build YYYYMM period index for portfolio monthly returns
                port_periods = (monthly_port_ret.index.year * 100 +
                                monthly_port_ret.index.month).astype(int)
                port_monthly = pd.DataFrame({
                    "period": port_periods.values,
                    "port_ret": monthly_port_ret.values,
                })
                port_monthly = port_monthly.set_index("period")

                # Inner join on period
                merged = port_monthly.join(ff_df, how="inner")
                merged = merged.dropna()

                if len(merged) >= 24:
                    # Excess return = portfolio return - risk-free rate
                    y = (merged["port_ret"] - merged["RF"]).values
                    X = merged[["Mkt-RF", "SMB", "HML"]].values
                    # Add intercept column
                    X_int = np.column_stack([np.ones(len(X)), X])

                    # OLS via numpy least squares
                    beta, residuals, rank, sv = np.linalg.lstsq(X_int, y, rcond=None)
                    alpha_monthly = beta[0]
                    mkt_beta = beta[1]
                    smb_beta = beta[2]
                    hml_beta = beta[3]

                    # R-squared
                    y_hat = X_int @ beta
                    ss_res = np.sum((y - y_hat) ** 2)
                    ss_tot = np.sum((y - np.mean(y)) ** 2)
                    r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

                    # t-statistics for coefficients
                    n = len(y)
                    k = X_int.shape[1]
                    if n > k:
                        mse = ss_res / (n - k)
                        var_beta = mse * np.linalg.inv(X_int.T @ X_int)
                        se_beta = np.sqrt(np.diag(var_beta))
                        t_stats = beta / se_beta
                    else:
                        t_stats = np.full(k, np.nan)

                    # Period covered
                    start_period = int(merged.index.min())
                    end_period = int(merged.index.max())
                    start_str = f"{start_period // 100}-{start_period % 100:02d}"
                    end_str = f"{end_period // 100}-{end_period % 100:02d}"

                    factor_regression = {
                        "alpha_annualized": round(float(alpha_monthly * 12), 2),
                        "alpha_t_stat": round(float(t_stats[0]), 2),
                        "market_beta": round(float(mkt_beta), 2),
                        "market_t_stat": round(float(t_stats[1]), 2),
                        "size_beta": round(float(smb_beta), 2),
                        "size_t_stat": round(float(t_stats[2]), 2),
                        "value_beta": round(float(hml_beta), 2),
                        "value_t_stat": round(float(t_stats[3]), 2),
                        "r_squared": round(float(r_squared), 3),
                        "num_months": int(len(merged)),
                        "period": f"{start_str} to {end_str}",
                    }
    except Exception as e:
        print(f"Factor regression failed: {e}")
        factor_regression = None

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
        "factor_regression": factor_regression,
    }
