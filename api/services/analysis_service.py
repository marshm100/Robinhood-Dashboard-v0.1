import pandas as pd
import numpy as np
import requests
import zipfile
import io
from typing import List
from api.models.portfolio import Holding
from .price_service import get_historical_prices

FF_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip"
CPI_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL"

def _fetch_cpi_series() -> pd.Series | None:
    """Download monthly CPI-U from FRED and return as a date-indexed Series.

    Returns None on failure.
    """
    try:
        resp = requests.get(CPI_URL, timeout=30)
        resp.raise_for_status()
        lines = resp.text.strip().splitlines()
        # First line is header: DATE,CPIAUCSL
        rows = []
        for line in lines[1:]:
            parts = line.split(",")
            if len(parts) != 2:
                continue
            try:
                date = pd.Timestamp(parts[0].strip())
                value = float(parts[1].strip())
                rows.append((date, value))
            except (ValueError, TypeError):
                continue
        if not rows:
            return None
        cpi = pd.Series(
            [r[1] for r in rows],
            index=pd.DatetimeIndex([r[0] for r in rows]),
            name="CPI",
        )
        return cpi.sort_index()
    except Exception as e:
        print(f"CPI fetch failed: {e}")
        return None

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
    period: str = "1y",
    inflation_adjusted: bool = False,
    rebalance: str = "none",
) -> dict:
    valid_holdings = [h for h in holdings if h.shares > 0]
    if not valid_holdings:
        return {"error": "No valid holdings"}

    tickers = [h.ticker for h in valid_holdings]
    all_tickers = tickers + [benchmark]

    print(f"Analysis request: tickers={tickers}, benchmark={benchmark}, period={period}, inflation_adjusted={inflation_adjusted}, rebalance={rebalance}")
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

    # --- Inflation adjustment (CPI deflation) ---
    cpi_applied = False
    deflator_values = None
    if inflation_adjusted:
        cpi_monthly = _fetch_cpi_series()
        if cpi_monthly is not None and len(cpi_monthly) > 0:
            # Resample monthly CPI to daily by forward-fill
            cpi_daily = cpi_monthly.reindex(
                pd.to_datetime(prices_df.index)
            ).ffill().bfill()
            if cpi_daily.notna().sum() > 0:
                cpi_latest = float(cpi_daily.iloc[-1])
                deflator = cpi_latest / cpi_daily
                deflator_values = deflator.values
                # Deflate portfolio value and benchmark prices
                portfolio_value = portfolio_value * deflator_values
                prices_df[benchmark] = prices_df[benchmark] * deflator_values
                cpi_applied = True

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

    # --- Timing Comparison (Lump Sum vs DCA) ---
    timing_comparison = None
    try:
        # Estimate total invested per holding from cost_basis (per-share) or
        # fall back to first-date price
        first_prices = prices_df.iloc[0]
        holding_costs = []
        for h in valid_holdings:
            if h.ticker not in prices_df.columns:
                continue
            if h.cost_basis and h.cost_basis > 0:
                # cost_basis is per-share cost
                cost_i = h.cost_basis * h.shares
            else:
                # Fallback: assume bought at first available price
                cost_i = float(first_prices[h.ticker]) * h.shares
            holding_costs.append((h.ticker, h.shares, cost_i))

        total_invested = sum(c for _, _, c in holding_costs)

        if total_invested > 0 and len(holding_costs) > 0:
            # Lump Sum: invest each holding's total cost at day-0 prices
            # lump_sum_shares_i = cost_i / first_price_i
            # lump_sum_value(t) = sum(lump_sum_shares_i * price_i(t))
            lump_sum_value = pd.Series(0.0, index=prices_df.index)
            for ticker, shares, cost_i in holding_costs:
                fp = float(first_prices[ticker])
                if fp > 0:
                    lump_shares = cost_i / fp
                    lump_sum_value += prices_df[ticker] * lump_shares

            # DCA value is the actual portfolio_value (already computed,
            # possibly inflation-adjusted above)
            dca_final = float(portfolio_value.iloc[-1])
            ls_final = float(lump_sum_value.iloc[-1])
            timing_penalty = round((dca_final / ls_final - 1) * 100, 2) if ls_final > 0 else None

            timing_comparison = {
                "dca_value": [round(float(v), 2) for v in portfolio_value],
                "lump_sum_value": [round(float(v), 2) for v in lump_sum_value],
                "total_invested": round(total_invested, 2),
                "lump_sum_final": round(ls_final, 2),
                "dca_final": round(dca_final, 2),
                "timing_penalty_pct": timing_penalty,
            }
    except Exception as e:
        print(f"Timing comparison failed: {e}")
        timing_comparison = None

    # --- Asset Correlation Matrix ---
    correlation_matrix = None
    # Include holdings tickers that exist in prices_df + benchmark
    corr_tickers = [t for t in tickers if t in prices_df.columns]
    if benchmark in prices_df.columns and benchmark not in corr_tickers:
        corr_tickers.append(benchmark)
    if len(corr_tickers) >= 3:
        asset_returns = prices_df[corr_tickers].pct_change().dropna()
        if len(asset_returns) >= 20:
            corr_df = asset_returns.corr().round(2)
            correlation_matrix = {
                "tickers": corr_tickers,
                "matrix": corr_df.values.tolist(),
            }

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

    # --- Rebalance Frequency Simulation ---
    rebalance_simulation = None
    if rebalance != "none":
        try:
            freq_map = {"monthly": "ME", "quarterly": "QE", "annual": "YE"}
            pd_freq = freq_map.get(rebalance)
            reb_tickers = [h.ticker for h in valid_holdings if h.ticker in prices_df.columns]

            if pd_freq and len(reb_tickers) >= 2:
                dt_index = pd.to_datetime(prices_df.index)

                # Compute initial target weights from day-0 allocation
                initial_values = {}
                initial_shares = {}
                for h in valid_holdings:
                    if h.ticker in prices_df.columns:
                        initial_values[h.ticker] = float(prices_df[h.ticker].iloc[0]) * h.shares
                        initial_shares[h.ticker] = h.shares
                total_initial = sum(initial_values.values())

                if total_initial > 0:
                    target_weights = {t: v / total_initial for t, v in initial_values.items()}

                    # Generate rebalance dates using pandas frequency
                    rebal_dates = pd.date_range(
                        start=dt_index[0], end=dt_index[-1], freq=pd_freq
                    )
                    # Map each rebalance date to the last trading day on or before it
                    rebal_positions = set()
                    for rd in rebal_dates:
                        candidates = dt_index[dt_index <= rd]
                        if len(candidates) > 0:
                            pos = dt_index.get_loc(candidates[-1])
                            rebal_positions.add(pos)

                    # Simulate rebalanced portfolio
                    current_shares = dict(initial_shares)
                    rebalanced_values = []

                    for i in range(len(prices_df)):
                        # Daily value
                        val = sum(
                            current_shares[t] * float(prices_df[t].iloc[i])
                            for t in current_shares
                        )
                        rebalanced_values.append(val)

                        # Rebalance at end of day if this is a rebalance date
                        if i in rebal_positions and i < len(prices_df) - 1:
                            total_val = val
                            for t in current_shares:
                                price = float(prices_df[t].iloc[i])
                                if price > 0:
                                    current_shares[t] = (
                                        total_val * target_weights.get(t, 0)
                                    ) / price

                    rebalanced_series = pd.Series(rebalanced_values, index=prices_df.index)

                    # Apply inflation deflator if active
                    if deflator_values is not None:
                        rebalanced_series = rebalanced_series * deflator_values

                    no_rebal_final = float(portfolio_value.iloc[-1])
                    rebal_final = float(rebalanced_series.iloc[-1])
                    rebal_diff = (
                        round((rebal_final / no_rebal_final - 1) * 100, 2)
                        if no_rebal_final > 0
                        else None
                    )

                    rebalance_simulation = {
                        "frequency": rebalance,
                        "rebalance_count": len(rebal_positions),
                        "target_weights": {
                            t: round(w * 100, 2) for t, w in target_weights.items()
                        },
                        "no_rebalance_value": [round(float(v), 2) for v in portfolio_value],
                        "rebalanced_value": [
                            round(float(v), 2) for v in rebalanced_series
                        ],
                        "no_rebalance_final": round(no_rebal_final, 2),
                        "rebalanced_final": round(rebal_final, 2),
                        "rebalance_diff_pct": rebal_diff,
                    }
        except Exception as e:
            print(f"Rebalance simulation failed: {e}")
            rebalance_simulation = None

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
        "correlation_matrix": correlation_matrix,
        "factor_regression": factor_regression,
        "timing_comparison": timing_comparison,
        "rebalance_simulation": rebalance_simulation,
        "rebalance": rebalance,
        "inflation_adjusted": inflation_adjusted and cpi_applied,
    }
