"""
Portfolio analysis service.

Provides time-weighted performance calculation using transaction replay,
comparing against benchmarks like SPY, QQQ, etc.

Handles partial/missing price data gracefully for leveraged/newer ETFs.
"""
import logging
from datetime import date, timedelta
from typing import List, Dict, Optional
from decimal import Decimal

import pandas as pd
import numpy as np
from sqlalchemy.orm import Session

from api.models.portfolio import Holding, Transaction
from api.database import SessionLocal
from .price_service import get_historical_prices, PriceResult

logger = logging.getLogger(__name__)


def calculate_time_weighted_performance(
    portfolio_id: int,
    benchmark: str = "SPY",
    db: Session = None
) -> dict:
    """
    Calculate accurate time-weighted portfolio performance using transaction replay.

    Handles partial/missing price data gracefully:
    - Uses latest available price for tickers with limited history
    - Fills forward from last known price
    - Uses cost basis as fallback estimate
    - Always returns a result (never fails on partial data)

    Args:
        portfolio_id: Portfolio ID to analyze
        benchmark: Benchmark ticker (default SPY)
        db: Optional database session

    Returns:
        Dict with dates, portfolio values, returns, metrics, and data quality info
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        # Load transactions sorted by date
        transactions = db.query(Transaction).filter(
            Transaction.portfolio_id == portfolio_id
        ).order_by(Transaction.date.asc()).all()

        if not transactions:
            logger.warning(f"No transactions found for portfolio {portfolio_id}")
            return {"error": "No transaction history available. Upload a Robinhood CSV to enable time-weighted analysis."}

        logger.info(f"Loaded {len(transactions)} transactions for portfolio {portfolio_id}")

        # Determine date range
        start_date = transactions[0].date
        end_date = date.today()

        # Get all unique tickers from transactions
        tickers = set()
        for t in transactions:
            if t.ticker:
                tickers.add(t.ticker)

        tickers = list(tickers)
        all_tickers = tickers + [benchmark.upper()]

        logger.info(f"Fetching prices for {len(all_tickers)} tickers from {start_date} to {end_date}")

        # Fetch historical prices with metadata
        price_result = get_historical_prices(all_tickers, period="5y", return_metadata=True)
        prices_df = price_result.df

        # Track data quality issues
        partial_tickers = price_result.partial_tickers.copy()
        failed_tickers = price_result.failed_tickers.copy()
        missing_prices: Dict[str, List[date]] = {}

        if prices_df.empty:
            return {
                "error": "Unable to fetch any price data",
                "failed_tickers": failed_tickers,
                "partial_tickers": partial_tickers,
            }

        # Check benchmark availability
        benchmark_upper = benchmark.upper()
        if benchmark_upper not in prices_df.columns:
            logger.error(f"Benchmark {benchmark} not available")
            return {
                "error": f"Benchmark {benchmark} not available",
                "failed_tickers": failed_tickers,
                "partial_tickers": partial_tickers,
            }

        # Build price lookup: ticker -> date -> price
        price_lookup: Dict[str, Dict[date, float]] = {}

        for ticker in all_tickers:
            if ticker in prices_df.columns:
                price_lookup[ticker] = {}
                for dt, price in prices_df[ticker].items():
                    if pd.notna(price):
                        price_lookup[ticker][dt.date()] = float(price)

        # Generate daily date range (business days)
        date_range = pd.date_range(start=start_date, end=end_date, freq='B')
        dates = [d.date() for d in date_range]

        # Initialize replay state
        cash = 0.0
        positions: Dict[str, float] = {}  # ticker -> shares
        cost_basis: Dict[str, float] = {}  # ticker -> total cost

        # Build transaction index by date
        trans_by_date: Dict[date, List[Transaction]] = {}
        for t in transactions:
            if t.date not in trans_by_date:
                trans_by_date[t.date] = []
            trans_by_date[t.date].append(t)

        # Replay daily
        daily_values = []
        daily_cash = []
        daily_position_values = []

        last_known_prices: Dict[str, float] = {}  # For fallback

        for current_date in dates:
            # Apply transactions on this date
            if current_date in trans_by_date:
                for t in trans_by_date[current_date]:
                    # Adjust cash
                    cash += t.amount

                    # Adjust positions
                    if t.ticker and t.quantity:
                        if t.trans_type in ["BUY", "CDIV"]:
                            positions[t.ticker] = positions.get(t.ticker, 0) + t.quantity
                            cost_basis[t.ticker] = cost_basis.get(t.ticker, 0) + abs(t.amount)
                        elif t.trans_type == "SELL":
                            if t.ticker in positions:
                                positions[t.ticker] = max(0, positions[t.ticker] - t.quantity)
                        elif t.trans_type == "SPLIT":
                            positions[t.ticker] = t.quantity

            # Value positions
            position_value = 0.0
            for ticker, shares in positions.items():
                if shares <= 0:
                    continue

                price = None

                # Try exact date
                if ticker in price_lookup and current_date in price_lookup[ticker]:
                    price = price_lookup[ticker][current_date]
                    last_known_prices[ticker] = price

                # Try nearby dates (forward fill)
                if price is None and ticker in price_lookup:
                    for days_back in range(1, 10):
                        lookup_date = current_date - timedelta(days=days_back)
                        if lookup_date in price_lookup[ticker]:
                            price = price_lookup[ticker][lookup_date]
                            last_known_prices[ticker] = price
                            break

                # Fallback to last known price
                if price is None and ticker in last_known_prices:
                    price = last_known_prices[ticker]

                # Last resort: use cost basis estimate
                if price is None:
                    if ticker not in missing_prices:
                        missing_prices[ticker] = []
                    missing_prices[ticker].append(current_date)

                    if ticker in cost_basis and positions.get(ticker, 0) > 0:
                        price = cost_basis[ticker] / positions[ticker]
                        logger.debug(f"Using cost basis for {ticker}: ${price:.2f}")

                if price:
                    position_value += shares * price

            total_value = cash + position_value
            daily_values.append(total_value)
            daily_cash.append(cash)
            daily_position_values.append(position_value)

        # Convert to numpy for calculations
        values = np.array(daily_values)
        cash_values = np.array(daily_cash)

        # Handle edge cases
        if len(values) == 0:
            return {"error": "No data points generated"}

        # Filter out leading zeros (before first deposit)
        first_nonzero = 0
        for i, v in enumerate(values):
            if v > 0:
                first_nonzero = i
                break

        values = values[first_nonzero:]
        cash_values = cash_values[first_nonzero:]
        dates = dates[first_nonzero:]

        if len(values) < 2 or values[0] == 0:
            return {"error": "Insufficient data for performance calculation"}

        # Calculate portfolio returns
        portfolio_returns = (values / values[0] - 1) * 100

        # Get benchmark returns
        benchmark_prices = [price_lookup.get(benchmark_upper, {}).get(d) for d in dates]

        # Forward fill missing benchmark prices
        last_price = None
        for i in range(len(benchmark_prices)):
            if benchmark_prices[i] is None:
                benchmark_prices[i] = last_price
            else:
                last_price = benchmark_prices[i]

        # Filter to valid dates
        valid_indices = [i for i, p in enumerate(benchmark_prices) if p is not None]
        if not valid_indices:
            return {
                "error": f"No benchmark data available for {benchmark}",
                "partial_tickers": partial_tickers,
                "failed_tickers": failed_tickers,
            }

        first_valid = valid_indices[0]
        benchmark_prices = benchmark_prices[first_valid:]
        benchmark_arr = np.array([p for p in benchmark_prices if p is not None])

        if len(benchmark_arr) == 0:
            return {"error": "No benchmark prices available"}

        benchmark_returns = (benchmark_arr / benchmark_arr[0] - 1) * 100

        # Align lengths
        min_len = min(len(portfolio_returns), len(benchmark_returns))
        portfolio_returns = portfolio_returns[:min_len]
        benchmark_returns = benchmark_returns[:min_len]
        dates = dates[:min_len]
        values = values[:min_len]
        cash_values = cash_values[:min_len]

        # Calculate metrics
        final_portfolio_return = float(portfolio_returns[-1])
        final_benchmark_return = float(benchmark_returns[-1])
        alpha = round(final_portfolio_return - final_benchmark_return, 2)

        # CAGR calculation
        years = len(dates) / 252
        if years > 0 and values[0] > 0:
            cagr = ((values[-1] / values[0]) ** (1 / years) - 1) * 100
        else:
            cagr = 0

        # Max drawdown
        peak = values[0]
        max_drawdown = 0
        for v in values:
            if v > peak:
                peak = v
            drawdown = (peak - v) / peak * 100 if peak > 0 else 0
            max_drawdown = max(max_drawdown, drawdown)

        # Cash drag
        cash_percentages = []
        for i in range(len(values)):
            if values[i] > 0:
                cash_percentages.append(cash_values[i] / values[i] * 100)
        avg_cash_drag = np.mean(cash_percentages) if cash_percentages else 0

        # Count missing price days
        total_missing = sum(len(dates_list) for dates_list in missing_prices.values())
        missing_tickers_list = list(set(list(missing_prices.keys()) + failed_tickers))

        # Determine earliest data date
        earliest_data = None
        if dates:
            earliest_data = dates[0].isoformat()

        # Format for response
        dates_str = [d.isoformat() for d in dates]

        result = {
            "dates": dates_str,
            "portfolio_values": [round(v, 2) for v in values.tolist()],
            "portfolio_returns": [round(r, 2) for r in portfolio_returns.tolist()],
            "benchmark_returns": [round(r, 2) for r in benchmark_returns.tolist()],
            "cash_values": [round(c, 2) for c in cash_values.tolist()],
            "benchmark": benchmark,
            "final_portfolio_return": round(final_portfolio_return, 2),
            "final_benchmark_return": round(final_benchmark_return, 2),
            "alpha": alpha,
            "cagr": round(cagr, 2),
            "max_drawdown": round(max_drawdown, 2),
            "avg_cash_drag": round(avg_cash_drag, 2),
            "current_value": round(float(values[-1]), 2),
            "current_cash": round(float(cash_values[-1]), 2),
            "transactions_replayed": len(transactions),
            "trading_days": len(dates),
            "has_transaction_history": True,
            # Data quality info
            "missing_price_days": total_missing,
            "missing_tickers": missing_tickers_list[:10],
            "partial_tickers": partial_tickers,
            "failed_tickers": failed_tickers,
            "is_partial": bool(partial_tickers or failed_tickers or total_missing > 0),
            "earliest_data": earliest_data,
        }

        logger.info(
            f"Time-weighted analysis complete: {len(transactions)} transactions, "
            f"portfolio={final_portfolio_return:.2f}%, benchmark={final_benchmark_return:.2f}%, "
            f"alpha={alpha:.2f}%, partial={len(partial_tickers)}, failed={len(failed_tickers)}"
        )

        return result

    except Exception as e:
        logger.error(f"Time-weighted performance error: {e}")
        import traceback
        traceback.print_exc()
        return {"error": f"Analysis failed: {str(e)}"}

    finally:
        if close_db:
            db.close()


def calculate_portfolio_returns(
    holdings: List[Holding],
    benchmark: str = "SPY",
    period: str = "1y"
) -> dict:
    """
    Calculate portfolio time-series returns vs benchmark using current holdings snapshot.

    Handles partial/missing price data gracefully for leveraged/newer ETFs.

    Args:
        holdings: List of Holding objects with ticker, shares, cost_basis
        benchmark: Benchmark ticker symbol (default: SPY)
        period: Time period (1mo, 3mo, 6mo, 1y, 2y)

    Returns:
        Dict with dates, portfolio_returns, benchmark_returns, stats, and data quality info
    """
    # Validate holdings
    valid_holdings = [h for h in holdings if h.shares and h.shares > 0]
    if not valid_holdings:
        logger.warning("No valid holdings provided")
        return {"error": "No valid holdings"}

    tickers = [h.ticker.upper() for h in valid_holdings]
    all_tickers = tickers + [benchmark.upper()]

    logger.info(f"Snapshot analysis: {len(tickers)} tickers, benchmark={benchmark}, period={period}")

    # Fetch price data with metadata
    price_result = get_historical_prices(all_tickers, period=period, return_metadata=True)
    prices_df = price_result.df

    # Track data quality
    partial_tickers = price_result.partial_tickers.copy()
    failed_tickers = price_result.failed_tickers.copy()

    if prices_df.empty:
        return {
            "error": "Unable to fetch any price data",
            "failed_tickers": failed_tickers,
            "partial_tickers": partial_tickers,
        }

    # Check which tickers we got
    available_tickers = set(prices_df.columns)
    missing_tickers = list(set(tickers) - available_tickers)
    if missing_tickers:
        logger.warning(f"Missing price data for tickers: {missing_tickers}")

    benchmark_upper = benchmark.upper()
    if benchmark_upper not in prices_df.columns:
        logger.error(f"Benchmark {benchmark} not in price data columns: {list(prices_df.columns)}")
        return {
            "error": f"Unable to fetch benchmark data for {benchmark}",
            "failed_tickers": failed_tickers,
            "partial_tickers": partial_tickers,
        }

    # Compute daily portfolio value
    portfolio_value = pd.Series(0.0, index=prices_df.index)
    included_holdings = []
    skipped_holdings = []
    total_cost_basis = Decimal("0")

    for h in valid_holdings:
        ticker_upper = h.ticker.upper()
        if ticker_upper in prices_df.columns:
            portfolio_value += prices_df[ticker_upper] * h.shares
            included_holdings.append(h.ticker)
            if h.cost_basis:
                total_cost_basis += Decimal(str(h.cost_basis))
        else:
            skipped_holdings.append(h.ticker)
            logger.warning(f"Skipping {h.ticker}: no price data available")

    if not included_holdings:
        return {
            "error": "No price data available for any holdings",
            "skipped_holdings": skipped_holdings,
            "failed_tickers": failed_tickers,
            "partial_tickers": partial_tickers,
        }

    # Handle zero initial value by finding first non-zero
    first_valid_idx = 0
    for i, val in enumerate(portfolio_value):
        if val > 0 and not pd.isna(val):
            first_valid_idx = i
            break

    if first_valid_idx > 0:
        portfolio_value = portfolio_value.iloc[first_valid_idx:]
        prices_df = prices_df.iloc[first_valid_idx:]

    if portfolio_value.iloc[0] == 0 or pd.isna(portfolio_value.iloc[0]):
        return {
            "error": "Initial portfolio value is zero - check holdings data",
            "skipped_holdings": skipped_holdings,
        }

    # Calculate returns
    portfolio_returns = (portfolio_value / portfolio_value.iloc[0] - 1) * 100
    benchmark_returns = (prices_df[benchmark_upper] / prices_df[benchmark_upper].iloc[0] - 1) * 100

    # Format dates
    dates = prices_df.index.strftime("%Y-%m-%d").tolist()

    # Calculate metrics
    final_portfolio_return = round(float(portfolio_returns.iloc[-1]), 2)
    final_benchmark_return = round(float(benchmark_returns.iloc[-1]), 2)
    alpha = round(final_portfolio_return - final_benchmark_return, 2)

    current_value = round(float(portfolio_value.iloc[-1]), 2)
    initial_value = round(float(portfolio_value.iloc[0]), 2)

    cost_basis_return = None
    if total_cost_basis > 0:
        cost_basis_return = round(
            float((Decimal(str(current_value)) / total_cost_basis - 1) * 100),
            2
        )

    # Determine earliest data date
    earliest_data = dates[0] if dates else None

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
        "has_transaction_history": False,
        # Data quality info
        "missing_tickers": missing_tickers + failed_tickers,
        "partial_tickers": partial_tickers,
        "failed_tickers": failed_tickers,
        "skipped_holdings": skipped_holdings,
        "is_partial": bool(partial_tickers or failed_tickers or missing_tickers),
        "earliest_data": earliest_data,
    }

    logger.info(
        f"Snapshot analysis complete: portfolio={final_portfolio_return}%, "
        f"benchmark={final_benchmark_return}%, alpha={alpha}%, "
        f"partial={len(partial_tickers)}, failed={len(failed_tickers)}"
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

    # Get current prices with metadata
    price_result = get_historical_prices(tickers, period="1mo", return_metadata=True)
    prices_df = price_result.df

    if prices_df.empty:
        return {
            "error": "Unable to fetch current prices",
            "failed_tickers": price_result.failed_tickers,
        }

    holdings_data = []
    total_value = Decimal("0")
    total_cost_basis = Decimal("0")
    missing_holdings = []

    for h in valid_holdings:
        ticker_upper = h.ticker.upper()
        if ticker_upper not in prices_df.columns:
            missing_holdings.append(h.ticker)
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
            "is_partial": ticker_upper in price_result.partial_tickers,
        }

        if h.cost_basis and h.cost_basis > 0:
            gain_loss = position_value - h.cost_basis
            gain_loss_pct = (position_value / h.cost_basis - 1) * 100
            holding_info["gain_loss"] = round(gain_loss, 2)
            holding_info["gain_loss_pct"] = round(gain_loss_pct, 2)
            total_cost_basis += Decimal(str(h.cost_basis))

        total_value += Decimal(str(position_value))
        holdings_data.append(holding_info)

    if not holdings_data:
        return {
            "error": "No holdings with available price data",
            "missing_holdings": missing_holdings,
        }

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
        "missing_holdings": missing_holdings,
        "partial_tickers": price_result.partial_tickers,
    }

    if total_cost_basis > 0:
        result["total_gain_loss"] = round(float(total_value - total_cost_basis), 2)
        result["total_gain_loss_pct"] = round(
            float((total_value / total_cost_basis - 1) * 100),
            2
        )

    return result
