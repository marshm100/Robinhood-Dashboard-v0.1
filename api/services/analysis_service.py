import yfinance as yf
import pandas as pd
import traceback
from datetime import date
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


def _fetch_spot_and_sector(ticker_str: str) -> tuple:
    """
    Fetch spot price and sector for a single ticker.
    Returns (price: float|None, sector: str).
    Never raises — all exceptions are caught and logged.
    """
    price = None
    sector = "Unknown"

    try:
        t = yf.Ticker(ticker_str)
    except Exception as e:
        print(f"[WARN] yf.Ticker({ticker_str}) constructor failed: {e}")
        return None, "Unknown"

    # Method 1: recent history for price (most reliable for leveraged ETFs)
    try:
        hist = t.history(period="2d")
        if not hist.empty and "Close" in hist.columns:
            closes = hist["Close"].dropna()
            if len(closes) > 0:
                val = float(closes.iloc[-1])
                if val > 0:
                    price = val
    except Exception as e:
        print(f"[WARN] history(2d) failed for {ticker_str}: {e}")

    # Method 2: .info for price fallback AND sector
    try:
        info = t.info or {}
        if price is None:
            for key in ("regularMarketPrice", "currentPrice", "previousClose", "lastPrice"):
                val = info.get(key)
                if val is not None:
                    try:
                        price = float(val)
                        if price > 0:
                            break
                        price = None
                    except (ValueError, TypeError):
                        continue
        sector = (
            info.get("sector")
            or info.get("industry")
            or info.get("category")
            or ("Exchange Traded Fund" if info.get("quoteType") == "ETF" else "Unknown")
        )
    except Exception as e:
        print(f"[WARN] .info failed for {ticker_str}: {e}")

    return price, sector


def calculate_portfolio_returns(
    holdings: List[Holding],
    benchmark: str = "SPY",
    period: str = "1y",
    db: Optional[Session] = None,
    inception_date: Optional[date] = None,
    track_to_present: bool = True,
    snapshot_date: Optional[date] = None,
) -> dict:
    valid_holdings = [h for h in holdings if h.shares > 0]
    if not valid_holdings:
        return {"error": "No valid holdings"}

    tickers = [h.ticker for h in valid_holdings]
    all_tickers = tickers + [benchmark]

    # Always include a holdings list in the response
    holdings_list = [
        {
            "ticker": h.ticker,
            "shares": round(float(h.shares), 6),
            "avg_cost": round(h.avg_cost, 4) if h.avg_cost else "N/A",
        }
        for h in valid_holdings
    ]

    print(f"Analysis request: tickers={tickers}, benchmark={benchmark}, period={period}, "
          f"inception={inception_date}, track_to_present={track_to_present}, snapshot={snapshot_date}")
    # Map user-facing "all" to yfinance's "max" period
    yf_period = "max" if period == "all" else period
    try:
        prices_df = get_historical_prices(all_tickers, period=yf_period)
    except Exception as e:
        print(f"[ERROR] get_historical_prices failed: {e}")
        prices_df = pd.DataFrame()

    # If main fetch failed entirely, try a short window for spot prices
    if prices_df.empty:
        print("Main fetch empty — trying 5d fallback for spot prices")
        try:
            prices_df = get_historical_prices(all_tickers, period="5d")
        except Exception as e:
            print(f"[ERROR] 5d fallback also failed: {e}")
            prices_df = pd.DataFrame()

    # ── Slice to inception_date if available ──────────────────────────
    if inception_date is not None and not prices_df.empty:
        ts = pd.Timestamp(inception_date)
        sliced = prices_df[prices_df.index >= ts]
        if not sliced.empty:
            prices_df = sliced
            print(f"Sliced prices to inception {inception_date}: {len(prices_df)} rows remain")

    # ── Slice end at snapshot_date when NOT tracking to present ───────
    if not track_to_present and snapshot_date is not None and not prices_df.empty:
        end_ts = pd.Timestamp(snapshot_date)
        sliced = prices_df[prices_df.index <= end_ts]
        if not sliced.empty:
            prices_df = sliced
            print(f"Snapshot mode: sliced to {snapshot_date}, {len(prices_df)} rows remain")

    # ── Compute effective end date for UI ─────────────────────────────
    if not prices_df.empty:
        effective_end_date = prices_df.index[-1].date().isoformat()
    elif not track_to_present and snapshot_date:
        effective_end_date = snapshot_date.isoformat()
    else:
        effective_end_date = date.today().isoformat()

    has_history = (
        not prices_df.empty
        and len(prices_df) >= 2
        and benchmark in prices_df.columns
    )

    # ── Spot prices + sectors via individual per-ticker calls ────────
    # Always fetch individually — bulk yf.download often returns NaN for
    # leveraged / recently-launched ETFs (BITU, AGQ, TECL, TSLL).
    latest_prices: dict = {}
    individual_sectors: dict = {}
    unique_tickers = list(set(all_tickers))
    print(f"Fetching individual spot prices & sectors for: {unique_tickers}")
    for ticker_str in unique_tickers:
        try:
            price, sector = _fetch_spot_and_sector(ticker_str)
            if price is not None:
                latest_prices[ticker_str] = price
            if sector and sector != "Unknown":
                individual_sectors[ticker_str] = sector
        except Exception as e:
            print(f"[ERROR] Unexpected failure fetching {ticker_str}: {e}\n{traceback.format_exc()}")

    current_value = sum(
        latest_prices.get(h.ticker, 0) * h.shares
        for h in valid_holdings
    )
    print(f"Spot prices resolved: {len(latest_prices)}/{len(unique_tickers)} tickers, "
          f"current_value=${current_value:.2f}")

    # ── Cost basis & unrealized P&L ────────────────────────────────────
    cost_basis = sum(
        h.shares * h.avg_cost
        for h in valid_holdings
        if h.avg_cost and h.avg_cost > 0
    )
    if cost_basis > 0:
        unrealized_gain = current_value - cost_basis
        unrealized_pct = (unrealized_gain / cost_basis) * 100
        pnl = {
            "cost_basis": round(cost_basis, 2),
            "unrealized_gain": round(unrealized_gain, 2),
            "unrealized_pct": round(unrealized_pct, 2),
        }
    else:
        pnl = {
            "cost_basis": "N/A",
            "unrealized_gain": "N/A",
            "unrealized_pct": "N/A",
        }

    # ── Sector allocation ─────────────────────────────────────────────
    # Merge DB-cached sectors with individually-fetched ones
    sector_allocation = []
    if latest_prices:
        sector_map: dict = {}
        if db is not None:
            try:
                sector_map = get_sector_map(tickers, db)
            except Exception as e:
                print(f"[ERROR] get_sector_map failed: {e}")
                sector_map = {}
        # Fill gaps with individually-fetched sectors
        for t in tickers:
            if t not in sector_map or sector_map.get(t) in (None, "Unknown"):
                if t in individual_sectors:
                    sector_map[t] = individual_sectors[t]

        total_value = current_value
        sector_totals: dict = {}
        for h in valid_holdings:
            price = latest_prices.get(h.ticker)
            if price:
                value = price * h.shares
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

    # ── Determine warning status ──────────────────────────────────────
    warning = "limited_history" if not has_history else None

    # ── If insufficient history, return partial result ────────────────
    if not has_history:
        print(f"Insufficient history (rows={len(prices_df)}) — returning partial analysis")
        return {
            "dates": [],
            "portfolio_returns": [],
            "benchmark_returns": [],
            "benchmark": benchmark,
            "period": period,
            "final_portfolio_return": None,
            "final_benchmark_return": None,
            "drawdown": {
                "max_drawdown_percent": None,
                "current_drawdown_percent": None,
                "longest_drawdown_days": None,
                "drawdown_chart_data": [],
            },
            "sector_allocation": sector_allocation,
            "risk_metrics": {
                "annualized_return": None,
                "annualized_volatility": None,
                "sharpe_ratio": None,
                "sortino_ratio": None,
            },
            "current_value": round(current_value, 2),
            "has_history": False,
            "warning": warning,
            "holdings_list": holdings_list,
            "pnl": pnl,
            "inception_date": inception_date.isoformat() if inception_date else None,
            "track_to_present": track_to_present,
            "effective_end_date": effective_end_date,
        }

    # ── Full analysis (sufficient history) ────────────────────────────
    # Compute daily portfolio value
    portfolio_value = pd.Series(0.0, index=prices_df.index)
    for h in valid_holdings:
        if h.ticker in prices_df.columns:
            portfolio_value += prices_df[h.ticker] * h.shares

    if portfolio_value.iloc[0] == 0:
        portfolio_value.iloc[0] = portfolio_value[portfolio_value > 0].iloc[0] if (portfolio_value > 0).any() else 1.0

    portfolio_returns = (portfolio_value / portfolio_value.iloc[0] - 1) * 100
    benchmark_returns = (prices_df[benchmark] / prices_df[benchmark].iloc[0] - 1) * 100

    dates = prices_df.index.strftime("%Y-%m-%d").tolist()

    # Compute real drawdown metrics from the portfolio value series
    drawdown_metrics = compute_drawdown_metrics(portfolio_value)

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
        "current_value": round(float(portfolio_value.iloc[-1]), 2),
        "has_history": True,
        "warning": warning,
        "holdings_list": holdings_list,
        "pnl": pnl,
        "inception_date": inception_date.isoformat() if inception_date else None,
        "track_to_present": track_to_present,
        "effective_end_date": effective_end_date,
    }