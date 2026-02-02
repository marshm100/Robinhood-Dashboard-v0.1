import pandas as pd
from datetime import date
from typing import List
from collections import defaultdict

from api.models.portfolio import Holding, Transaction
from .price_service import get_historical_prices, get_historical_prices_by_date


# ── Legacy: static-holdings approach (no transaction timing) ──────────

def calculate_portfolio_returns(
    holdings: List[Holding],
    benchmark: str = "SPY",
    period: str = "1y",
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


# ── New: transaction-aware cumulative-shares approach ─────────────────

def calculate_portfolio_returns_from_transactions(
    transactions: List[Transaction],
    benchmark: str = "SPY",
    track_to_present: bool = True,
) -> dict:
    """Build a value series that reflects actual DCA timing.

    Algorithm:
      1. Sort transactions by activity_date.
      2. Determine date range: first transaction → today (or last txn date).
      3. Fetch prices for all portfolio tickers + benchmark over that range.
      4. Walk through each trading day:
         - apply any transactions on or before that day (cumulative shares).
         - value = Σ cum_shares[ticker] × close[ticker].
      5. Trim leading zeros (days before the first buy hit a trading day).
      6. Normalise to percentage returns from first non-zero value.
    """
    if not transactions:
        return {"error": "No transactions"}

    sorted_txns = sorted(transactions, key=lambda t: t.activity_date)

    tickers = list({t.ticker for t in sorted_txns})
    all_tickers = tickers + ([benchmark] if benchmark not in tickers else [])

    start_date = sorted_txns[0].activity_date
    end_date = date.today() if track_to_present else sorted_txns[-1].activity_date

    print(f"DCA analysis: {len(sorted_txns)} txns, {len(tickers)} tickers, "
          f"{start_date} → {end_date}, benchmark={benchmark}")

    prices_df = get_historical_prices_by_date(all_tickers, start_date, end_date)
    if prices_df.empty or benchmark not in prices_df.columns:
        print("Price fetch returned empty — insufficient data")
        return {"error": "Insufficient price data"}

    # ── Group transactions by date for efficient walk-through ──
    txn_events = defaultdict(list)
    for t in sorted_txns:
        txn_events[t.activity_date].append((t.ticker, t.quantity))

    event_dates = sorted(txn_events.keys())

    # ── Walk trading days, accumulate shares, compute value ──
    cum_shares = defaultdict(float)
    evt_idx = 0
    portfolio_values = []

    for ts in prices_df.index:
        trade_date = ts.date() if hasattr(ts, "date") else ts

        # Apply all transaction events up to and including this trading day
        while evt_idx < len(event_dates) and event_dates[evt_idx] <= trade_date:
            for ticker, qty in txn_events[event_dates[evt_idx]]:
                cum_shares[ticker] += qty
            evt_idx += 1

        # Portfolio value for this day
        value = 0.0
        for ticker in tickers:
            shares = cum_shares.get(ticker, 0.0)
            if shares != 0 and ticker in prices_df.columns:
                price = prices_df.at[ts, ticker]
                if pd.notna(price):
                    value += shares * price

        portfolio_values.append(value)

    portfolio_value = pd.Series(portfolio_values, index=prices_df.index)

    # ── Trim leading zeros (before first buy takes effect) ──
    first_nonzero = portfolio_value.ne(0).idxmax()
    if portfolio_value.loc[first_nonzero] == 0:
        return {"error": "Portfolio value is always zero"}

    portfolio_value = portfolio_value.loc[first_nonzero:]
    prices_df = prices_df.loc[first_nonzero:]

    if portfolio_value.iloc[0] == 0:
        return {"error": "Initial portfolio value is zero"}

    # ── Returns ──
    portfolio_returns = (portfolio_value / portfolio_value.iloc[0] - 1) * 100
    benchmark_returns = (prices_df[benchmark] / prices_df[benchmark].iloc[0] - 1) * 100

    dates = prices_df.index.strftime("%Y-%m-%d").tolist()

    return {
        "dates": dates,
        "portfolio_returns": portfolio_returns.round(2).tolist(),
        "benchmark_returns": benchmark_returns.round(2).tolist(),
        "benchmark": benchmark,
        "period": f"{start_date} to {end_date}",
        "final_portfolio_return": round(portfolio_returns.iloc[-1], 2),
        "final_benchmark_return": round(benchmark_returns.iloc[-1], 2),
    }
