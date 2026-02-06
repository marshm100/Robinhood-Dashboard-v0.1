import logging
from typing import List

import pandas as pd

from api.models.portfolio import Holding
from .price_service import get_cached_history, get_fetch_errors

log = logging.getLogger(__name__)


def calculate_portfolio_returns(
    holdings: List[Holding],
    benchmark: str = "SPY",
    period: str = "1y",
) -> dict:
    valid_holdings = [h for h in holdings if h.shares and h.shares > 0]
    if not valid_holdings:
        return {"error": "No valid holdings"}

    tickers = list({h.ticker for h in valid_holdings})
    all_tickers = tickers + [benchmark]

    log.info("Analysis: tickers=%s benchmark=%s period=%s", tickers, benchmark, period)

    # Fetch each ticker through the cache
    series_map: dict[str, pd.Series] = {}
    for t in all_tickers:
        try:
            s = get_cached_history(t, period=period)
            if not s.empty:
                series_map[t] = s
        except Exception:
            log.warning("Failed to get history for %s", t, exc_info=True)

    benchmark_available = benchmark in series_map

    missing = [t for t in tickers if t not in series_map]
    if missing:
        log.warning("Missing price data for: %s", missing)

    available_tickers = [t for t in tickers if t in series_map]
    if not available_tickers:
        return {"error": "No price data for any holdings"}

    # Determine common start/end across available series (holdings + benchmark if available)
    relevant_series = {t: series_map[t] for t in available_tickers}
    if benchmark_available:
        relevant_series[benchmark] = series_map[benchmark]

    common_start = max(s.index.min() for s in relevant_series.values())
    common_end = min(s.index.max() for s in relevant_series.values())

    if common_start >= common_end:
        return {"error": "No overlapping date range across holdings" + (" and benchmark" if benchmark_available else "")}

    # Build common business-day index
    common_idx = pd.bdate_range(common_start, common_end)

    # Reindex all series and forward-fill
    aligned = {}
    for t, s in relevant_series.items():
        aligned[t] = s.reindex(common_idx).ffill().bfill()

    # Portfolio value series
    portfolio_value = pd.Series(0.0, index=common_idx)
    for h in valid_holdings:
        if h.ticker in aligned:
            portfolio_value += aligned[h.ticker] * h.shares

    if portfolio_value.iloc[0] == 0:
        return {"error": "Initial portfolio value is zero"}

    portfolio_returns = ((portfolio_value / portfolio_value.iloc[0]) - 1) * 100
    dates = common_idx.strftime("%Y-%m-%d").tolist()

    result = {
        "dates": dates,
        "portfolio_returns": portfolio_returns.round(2).tolist(),
        "benchmark": benchmark,
        "period": period,
        "final_portfolio_return": round(float(portfolio_returns.iloc[-1]), 2),
        "common_start": common_start.strftime("%Y-%m-%d"),
        "missing_tickers": missing,
        "benchmark_unavailable": not benchmark_available,
    }

    if benchmark_available:
        bench_series = aligned[benchmark]
        benchmark_returns = ((bench_series / bench_series.iloc[0]) - 1) * 100
        result["benchmark_returns"] = benchmark_returns.round(2).tolist()
        result["final_benchmark_return"] = round(float(benchmark_returns.iloc[-1]), 2)
    else:
        log.warning("Benchmark %s unavailable; returning portfolio-only chart", benchmark)
        result["benchmark_returns"] = []
        result["final_benchmark_return"] = None

    # Include any fetch errors for API consumers
    priming_errors = get_fetch_errors()
    if priming_errors:
        result["priming_errors"] = priming_errors

    return result
