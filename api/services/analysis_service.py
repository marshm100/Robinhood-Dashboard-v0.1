"""
Portfolio analysis service.

Provides time-series performance calculation for portfolios,
comparing against benchmarks like SPY, QQQ, etc.
"""
import logging
from typing import List, Dict, Optional
from decimal import Decimal

import pandas as pd

from api.models.portfolio import Holding
from .price_service import get_historical_prices

logger = logging.getLogger(__name__)


def calculate_portfolio_returns(
    holdings: List[Holding],
    benchmark: str = "SPY",
    period: str = "1y"
) -> dict:
    """
    Calculate portfolio time-series returns vs benchmark.

    Uses current holdings snapshot to compute historical performance,
    assuming positions were held for the entire period.

    Args:
        holdings: List of Holding objects with ticker, shares, cost_basis
        benchmark: Benchmark ticker symbol (default: SPY)
        period: Time period (1mo, 3mo, 6mo, 1y, 2y)

    Returns:
        Dict with dates, portfolio_returns, benchmark_returns, and stats
    """
    # Validate holdings
    valid_holdings = [h for h in holdings if h.shares and h.shares > 0]
    if not valid_holdings:
        logger.warning("No valid holdings provided")
        return {"error": "No valid holdings"}

    tickers = [h.ticker.upper() for h in valid_holdings]
    all_tickers = tickers + [benchmark.upper()]

    logger.info(f"Analysis request: {len(tickers)} tickers, benchmark={benchmark}, period={period}")

    # Fetch price data
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

    # Compute daily portfolio value using share weights
    portfolio_value = pd.Series(0.0, index=prices_df.index)
    included_holdings = []
    total_cost_basis = Decimal("0")

    for h in valid_holdings:
        ticker_upper = h.ticker.upper()
        if ticker_upper in prices_df.columns:
            portfolio_value += prices_df[ticker_upper] * h.shares
            included_holdings.append(h.ticker)
            if h.cost_basis:
                total_cost_basis += Decimal(str(h.cost_basis))
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

    # Calculate percentage returns from start of period
    portfolio_returns = (portfolio_value / portfolio_value.iloc[0] - 1) * 100
    benchmark_returns = (prices_df[benchmark_upper] / prices_df[benchmark_upper].iloc[0] - 1) * 100

    # Format dates
    dates = prices_df.index.strftime("%Y-%m-%d").tolist()

    # Calculate additional metrics
    final_portfolio_return = round(float(portfolio_returns.iloc[-1]), 2)
    final_benchmark_return = round(float(benchmark_returns.iloc[-1]), 2)
    alpha = round(final_portfolio_return - final_benchmark_return, 2)

    # Current portfolio value
    current_value = round(float(portfolio_value.iloc[-1]), 2)
    initial_value = round(float(portfolio_value.iloc[0]), 2)

    # Calculate vs cost basis if available
    cost_basis_return = None
    if total_cost_basis > 0:
        cost_basis_return = round(
            float((Decimal(str(current_value)) / total_cost_basis - 1) * 100),
            2
        )

    result = {
        "dates": dates,
        "portfolio_returns": portfolio_returns.round(2).tolist(),
        "benchmark_returns": benchmark_returns.round(2).tolist(),
        "benchmark": benchmark,
        "period": period,
        "final_portfolio_return": final_portfolio_return,
        "final_benchmark_return": final_benchmark_return,
        "alpha": alpha,
        "current_value": current_value,
        "initial_value": initial_value,
        "cost_basis_return": cost_basis_return,
        "holdings_included": len(included_holdings),
        "holdings_total": len(valid_holdings),
        "missing_tickers": list(missing_tickers) if missing_tickers else [],
    }

    logger.info(
        f"Analysis complete: portfolio={final_portfolio_return}%, "
        f"benchmark={final_benchmark_return}%, alpha={alpha}%"
    )
    return result


def calculate_portfolio_metrics(holdings: List[Holding]) -> dict:
    """
    Calculate current portfolio metrics (value, allocation, etc).

    Args:
        holdings: List of Holding objects

    Returns:
        Dict with current value, allocation breakdown, cost basis totals
    """
    valid_holdings = [h for h in holdings if h.shares and h.shares > 0]
    if not valid_holdings:
        return {"error": "No valid holdings"}

    tickers = [h.ticker.upper() for h in valid_holdings]

    # Get current prices (use 1mo to get recent data)
    prices_df = get_historical_prices(tickers, period="1mo")

    if prices_df.empty:
        return {"error": "Unable to fetch current prices"}

    holdings_data = []
    total_value = Decimal("0")
    total_cost_basis = Decimal("0")

    for h in valid_holdings:
        ticker_upper = h.ticker.upper()
        if ticker_upper not in prices_df.columns:
            continue

        # Get most recent price
        current_price = float(prices_df[ticker_upper].iloc[-1])
        position_value = current_price * h.shares

        holding_info = {
            "ticker": h.ticker,
            "shares": h.shares,
            "current_price": round(current_price, 2),
            "position_value": round(position_value, 2),
            "cost_basis": h.cost_basis,
        }

        if h.cost_basis and h.cost_basis > 0:
            gain_loss = position_value - h.cost_basis
            gain_loss_pct = (position_value / h.cost_basis - 1) * 100
            holding_info["gain_loss"] = round(gain_loss, 2)
            holding_info["gain_loss_pct"] = round(gain_loss_pct, 2)
            total_cost_basis += Decimal(str(h.cost_basis))

        total_value += Decimal(str(position_value))
        holdings_data.append(holding_info)

    # Calculate allocation percentages
    for h in holdings_data:
        h["allocation_pct"] = round(
            float(Decimal(str(h["position_value"])) / total_value * 100),
            2
        )

    # Sort by position value descending
    holdings_data.sort(key=lambda x: x["position_value"], reverse=True)

    result = {
        "total_value": round(float(total_value), 2),
        "total_cost_basis": round(float(total_cost_basis), 2) if total_cost_basis > 0 else None,
        "holdings_count": len(holdings_data),
        "holdings": holdings_data,
    }

    if total_cost_basis > 0:
        result["total_gain_loss"] = round(float(total_value - total_cost_basis), 2)
        result["total_gain_loss_pct"] = round(
            float((total_value / total_cost_basis - 1) * 100),
            2
        )

    return result


def get_sector_allocation(holdings: List[Holding]) -> dict:
    """
    Get sector allocation breakdown for portfolio.
    Note: This is a placeholder - would need sector data source.

    Args:
        holdings: List of Holding objects

    Returns:
        Dict with sector breakdown
    """
    # TODO: Integrate sector data from yfinance or other source
    return {
        "message": "Sector allocation coming soon",
        "holdings_count": len([h for h in holdings if h.shares and h.shares > 0])
    }
