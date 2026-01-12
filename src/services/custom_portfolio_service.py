"""
Custom Portfolio Service
Handles creation, backtesting, and comparison of hypothetical portfolios
"""

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import json
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
import logging

from ..models import CustomPortfolio, PortfolioSnapshot, Transaction
from .stock_price_service import stock_price_service
from .portfolio_calculator import PortfolioCalculator


class CustomPortfolioService:
    """Service for managing custom portfolios and comparisons"""

    def __init__(self, db: Session):
        self.db = db
        self.portfolio_calculator = PortfolioCalculator(db)

    def create_portfolio(
        self,
        name: str,
        asset_allocation: Dict[str, float],
        description: Optional[str] = None,
        strategy: str = "lump_sum",
        monthly_investment: Optional[float] = None
    ) -> CustomPortfolio:
        """
        Create a new custom portfolio
        
        Args:
            name: Portfolio name
            asset_allocation: Dict of ticker -> weight (e.g., {"AAPL": 0.5, "MSFT": 0.5})
            description: Optional description
            strategy: "lump_sum" or "dca" (dollar cost averaging)
            monthly_investment: Monthly investment amount for DCA strategy
        
        Returns:
            Created CustomPortfolio object
        """
        # Validate weights sum to 1.0 (within tolerance)
        total_weight = sum(asset_allocation.values())
        if abs(total_weight - 1.0) > 0.01:
            raise ValueError(f"Asset allocation weights must sum to 1.0, got {total_weight}")

        portfolio = CustomPortfolio(
            name=name,
            description=description,
            asset_allocation=json.dumps(asset_allocation),
            strategy=strategy,
            monthly_investment=monthly_investment
        )
        
        self.db.add(portfolio)
        self.db.commit()
        self.db.refresh(portfolio)
        
        return portfolio

    def get_portfolio(self, portfolio_id: int) -> Optional[CustomPortfolio]:
        """Get portfolio by ID"""
        return self.db.query(CustomPortfolio).filter(CustomPortfolio.id == portfolio_id).first()

    def list_portfolios(self) -> List[CustomPortfolio]:
        """List all custom portfolios"""
        return self.db.query(CustomPortfolio).order_by(CustomPortfolio.created_at.desc()).all()

    def delete_portfolio(self, portfolio_id: int) -> bool:
        """Delete a portfolio and its snapshots"""
        portfolio = self.get_portfolio(portfolio_id)
        if not portfolio:
            return False
        
        # Delete snapshots
        self.db.query(PortfolioSnapshot).filter(
            PortfolioSnapshot.portfolio_id == portfolio_id
        ).delete()
        
        # Delete portfolio
        self.db.delete(portfolio)
        self.db.commit()
        
        return True

    def backtest_portfolio(
        self,
        portfolio_id: int,
        start_date: str,
        end_date: str,
        initial_investment: float = 10000.0
    ) -> Dict[str, Any]:
        """
        Backtest a custom portfolio over a date range
        
        Args:
            portfolio_id: Portfolio ID
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            initial_investment: Initial investment amount
        
        Returns:
            Dict with backtest results including:
            - history: List of date/value pairs
            - total_return: Total return percentage
            - final_value: Final portfolio value
            - sharpe_ratio: Sharpe ratio if calculable
            - max_drawdown: Maximum drawdown
        """
        portfolio = self.get_portfolio(portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio {portfolio_id} not found")

        asset_allocation = json.loads(portfolio.asset_allocation)
        strategy = portfolio.strategy
        monthly_investment = portfolio.monthly_investment or 0

        # Generate date range
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        dates = pd.date_range(start, end, freq='D')
        
        history = []
        current_value = initial_investment
        previous_value = initial_investment
        max_value = initial_investment
        max_drawdown = 0.0
        daily_returns = []

        for date in dates:
            date_str = date.strftime("%Y-%m-%d")
            
            # Skip weekends
            if date.weekday() >= 5:
                continue

            # Calculate portfolio value at this date
            portfolio_value = 0.0
            holdings = {}

            if strategy == "dca" and monthly_investment > 0:
                # Dollar cost averaging: invest monthly
                if date.day == 1:  # First day of month
                    # Add monthly investment
                    current_value += monthly_investment
                
                # Calculate current allocation based on total invested
                total_invested = initial_investment + (monthly_investment * ((date.year - start.year) * 12 + (date.month - start.month)))
                
                for ticker, weight in asset_allocation.items():
                    price = self._get_price_at_date(ticker, date_str)
                    if price and price > 0:
                        # Calculate shares based on weight of total invested
                        shares = (total_invested * weight) / price
                        holdings[ticker] = shares
                        portfolio_value += shares * price
            else:
                # Lump sum: initial investment allocated by weights
                for ticker, weight in asset_allocation.items():
                    price = self._get_price_at_date(ticker, date_str)
                    if price and price > 0:
                        shares = (initial_investment * weight) / self._get_price_at_date(ticker, start_date) if self._get_price_at_date(ticker, start_date) else 0
                        if shares > 0:
                            holdings[ticker] = shares
                            portfolio_value += shares * price

            if portfolio_value > 0:
                current_value = portfolio_value
                
                # Calculate daily return
                if previous_value > 0:
                    daily_return = (current_value - previous_value) / previous_value
                    daily_returns.append(daily_return)
                
                # Track max drawdown
                if current_value > max_value:
                    max_value = current_value
                
                drawdown = (max_value - current_value) / max_value if max_value > 0 else 0
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
                
                history.append({
                    "date": date_str,
                    "value": round(current_value, 2),
                    "holdings": holdings.copy()
                })
                
                previous_value = current_value

        # Calculate metrics
        total_return = ((current_value - initial_investment) / initial_investment * 100) if initial_investment > 0 else 0
        
        # Calculate Sharpe ratio (annualized)
        sharpe_ratio = None
        if len(daily_returns) > 1:
            returns_array = np.array(daily_returns)
            mean_return = np.mean(returns_array)
            std_return = np.std(returns_array)
            if std_return > 0:
                # Annualize (252 trading days)
                sharpe_ratio = (mean_return / std_return) * np.sqrt(252)

        return {
            "portfolio_id": portfolio_id,
            "portfolio_name": portfolio.name,
            "start_date": start_date,
            "end_date": end_date,
            "initial_investment": initial_investment,
            "final_value": round(current_value, 2),
            "total_return": round(total_return, 2),
            "max_drawdown": round(max_drawdown * 100, 2),
            "sharpe_ratio": round(sharpe_ratio, 3) if sharpe_ratio else None,
            "history": history
        }

    def get_robinhood_portfolio_history(
        self,
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        """
        Get Robinhood portfolio history for comparison
        
        Returns:
            Dict with history and metrics similar to backtest_portfolio
        """
        # Get date range from transactions
        first_tx = self.db.query(Transaction).order_by(Transaction.activity_date).first()
        last_tx = self.db.query(Transaction).order_by(Transaction.activity_date.desc()).first()
        
        if not first_tx or not last_tx:
            return {
                "portfolio_type": "robinhood",
                "history": [],
                "total_return": 0,
                "final_value": 0
            }

        # Use portfolio calculator to get history
        history_df = self.portfolio_calculator.get_portfolio_value_history(start_date, end_date)
        
        # Convert DataFrame to list of dicts
        filtered_history = []
        if not history_df.empty:
            for _, row in history_df.iterrows():
                filtered_history.append({
                    "date": str(row.get("date", "")),
                    "value": round(float(row.get("portfolio_value", 0)), 2)
                })

        # Calculate metrics
        if filtered_history:
            start_value = filtered_history[0].get("value", 0)
            end_value = filtered_history[-1].get("value", 0)
            total_return = ((end_value - start_value) / start_value * 100) if start_value > 0 else 0
        else:
            start_value = 0
            end_value = 0
            total_return = 0

        return {
            "portfolio_type": "robinhood",
            "portfolio_name": "Your Robinhood Portfolio",
            "start_date": start_date,
            "end_date": end_date,
            "initial_investment": start_value,
            "final_value": round(end_value, 2),
            "total_return": round(total_return, 2),
            "history": filtered_history
        }

    def get_benchmark_history(
        self,
        benchmark_ticker: str,
        start_date: str,
        end_date: str,
        initial_investment: float = 10000.0
    ) -> Dict[str, Any]:
        """
        Get benchmark (e.g., SPY) history for comparison
        
        Args:
            benchmark_ticker: Ticker symbol (e.g., "SPY")
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            initial_investment: Initial investment amount
        
        Returns:
            Dict with benchmark history and metrics
        """
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        dates = pd.date_range(start, end, freq='D')
        
        history = []
        start_price = None
        end_price = None
        
        for date in dates:
            date_str = date.strftime("%Y-%m-%d")
            
            # Skip weekends
            if date.weekday() >= 5:
                continue

            price = self._get_price_at_date(benchmark_ticker, date_str)
            if price and price > 0:
                if start_price is None:
                    start_price = price
                
                end_price = price
                shares = initial_investment / start_price if start_price > 0 else 0
                value = shares * price
                
                history.append({
                    "date": date_str,
                    "value": round(value, 2),
                    "price": round(price, 2)
                })

        # Calculate metrics
        total_return = 0
        if start_price and end_price and start_price > 0:
            total_return = ((end_price - start_price) / start_price * 100)

        final_value = history[-1]["value"] if history else initial_investment

        return {
            "portfolio_type": "benchmark",
            "portfolio_name": f"{benchmark_ticker} Benchmark",
            "ticker": benchmark_ticker,
            "start_date": start_date,
            "end_date": end_date,
            "initial_investment": initial_investment,
            "final_value": round(final_value, 2),
            "total_return": round(total_return, 2),
            "history": history
        }

    def compare_portfolios(
        self,
        portfolio_ids: List[int],
        benchmark_tickers: Optional[List[str]] = None,
        include_robinhood: bool = True,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        initial_investment: float = 10000.0
    ) -> Dict[str, Any]:
        """
        Compare multiple portfolios, benchmarks, and optionally Robinhood portfolio
        
        Args:
            portfolio_ids: List of custom portfolio IDs to compare
            benchmark_tickers: List of benchmark tickers (e.g., ["SPY", "QQQ"])
            include_robinhood: Whether to include Robinhood portfolio
            start_date: Start date (if None, uses earliest available)
            end_date: End date (if None, uses latest available)
            initial_investment: Initial investment for backtesting
        
        Returns:
            Dict with comparison data including all portfolios' histories and metrics
        """
        # Determine date range
        if not start_date or not end_date:
            first_tx = self.db.query(Transaction).order_by(Transaction.activity_date).first()
            last_tx = self.db.query(Transaction).order_by(Transaction.activity_date.desc()).first()
            
            if first_tx and last_tx:
                start_date = start_date or first_tx.activity_date
                end_date = end_date or last_tx.activity_date
            else:
                # Default to last year if no transactions
                end = datetime.now()
                start = end - timedelta(days=365)
                start_date = start_date or start.strftime("%Y-%m-%d")
                end_date = end_date or end.strftime("%Y-%m-%d")

        comparison_data = {
            "start_date": start_date,
            "end_date": end_date,
            "initial_investment": initial_investment,
            "portfolios": []
        }

        # Add custom portfolios
        for portfolio_id in portfolio_ids:
            try:
                backtest = self.backtest_portfolio(portfolio_id, start_date, end_date, initial_investment)
                comparison_data["portfolios"].append(backtest)
            except Exception as e:
                print(f"Error backtesting portfolio {portfolio_id}: {e}")

        # Add Robinhood portfolio
        if include_robinhood:
            try:
                robinhood = self.get_robinhood_portfolio_history(start_date, end_date)
                comparison_data["portfolios"].append(robinhood)
            except Exception as e:
                print(f"Error getting Robinhood portfolio: {e}")

        # Add benchmarks
        if benchmark_tickers:
            for ticker in benchmark_tickers:
                try:
                    benchmark = self.get_benchmark_history(ticker, start_date, end_date, initial_investment)
                    comparison_data["portfolios"].append(benchmark)
                except Exception as e:
                    print(f"Error getting benchmark {ticker}: {e}")

        return comparison_data

    def _get_price_at_date(self, ticker: str, date: str) -> Optional[float]:
        """Helper to get price at date using stock_price_service"""
        try:
            price_data = stock_price_service.get_price_at_date(ticker, date)
            if price_data and 'close' in price_data:
                return price_data['close']
            return None
        except Exception as e:
            print(f"Error getting price for {ticker} on {date}: {e}")
            return None

    def run_scenario(
        self,
        portfolio_id: Optional[int],
        scenario_type: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run what-if scenario analysis on a portfolio.
        
        Args:
            portfolio_id: Portfolio ID (None for Robinhood portfolio)
            scenario_type: "rebalance", "add_asset", "reduce_position", "market_change"
            params: Scenario-specific parameters
        
        Returns:
            Dict with original metrics, scenario metrics, and differences
        """
        try:
            # Get original portfolio metrics
            if portfolio_id:
                portfolio = self.get_portfolio(portfolio_id)
                if not portfolio:
                    raise ValueError(f"Portfolio {portfolio_id} not found")
                original_allocation = json.loads(portfolio.asset_allocation)
            else:
                # Use Robinhood portfolio
                original_allocation = {}
                weights = self.portfolio_calculator.calculate_position_weights()
                for ticker, weight in weights.items():
                    original_allocation[ticker] = weight / 100.0
            
            # Calculate original metrics
            original_metrics = self._calculate_portfolio_metrics(original_allocation)
            
            # Apply scenario modifications
            scenario_allocation = original_allocation.copy()
            
            if scenario_type == "rebalance":
                # Apply new target weights
                new_weights = params.get("weights", {})
                for ticker, weight in new_weights.items():
                    scenario_allocation[ticker] = weight
                # Normalize
                total = sum(scenario_allocation.values())
                if total > 0:
                    scenario_allocation = {k: v/total for k, v in scenario_allocation.items()}
            
            elif scenario_type == "add_asset":
                # Add new ticker with specified weight
                new_ticker = params.get("ticker", "").upper()
                new_weight = params.get("weight", 0.1)
                if new_ticker:
                    # Reduce others proportionally
                    reduction_factor = 1 - new_weight
                    scenario_allocation = {k: v * reduction_factor for k, v in scenario_allocation.items()}
                    scenario_allocation[new_ticker] = new_weight
            
            elif scenario_type == "reduce_position":
                # Reduce specific ticker, redistribute to others
                ticker = params.get("ticker", "").upper()
                reduction = params.get("reduction", 0.5)  # Reduce by 50% default
                if ticker in scenario_allocation:
                    original_weight = scenario_allocation[ticker]
                    new_weight = original_weight * (1 - reduction)
                    freed_weight = original_weight - new_weight
                    
                    scenario_allocation[ticker] = new_weight
                    
                    # Redistribute freed weight to others proportionally
                    other_total = sum(v for k, v in scenario_allocation.items() if k != ticker)
                    if other_total > 0:
                        for k in scenario_allocation:
                            if k != ticker:
                                scenario_allocation[k] += freed_weight * (scenario_allocation[k] / other_total)
            
            elif scenario_type == "market_change":
                # Apply uniform % change - affects returns, not allocation
                market_change = params.get("change", 0)  # e.g., -10 for 10% decline
                # This affects the projected returns
                scenario_metrics = self._calculate_portfolio_metrics(scenario_allocation)
                scenario_metrics["return"] = scenario_metrics["return"] + market_change
                
                return {
                    "original": original_metrics,
                    "scenario": scenario_metrics,
                    "difference": {
                        "return": round(scenario_metrics["return"] - original_metrics["return"], 2),
                        "risk": round(scenario_metrics["risk"] - original_metrics["risk"], 2),
                        "sharpe": round(scenario_metrics["sharpe"] - original_metrics["sharpe"], 3)
                    },
                    "scenario_type": scenario_type,
                    "params": params
                }
            
            # Calculate scenario metrics
            scenario_metrics = self._calculate_portfolio_metrics(scenario_allocation)
            
            return {
                "original": original_metrics,
                "scenario": scenario_metrics,
                "difference": {
                    "return": round(scenario_metrics["return"] - original_metrics["return"], 2),
                    "risk": round(scenario_metrics["risk"] - original_metrics["risk"], 2),
                    "sharpe": round(scenario_metrics["sharpe"] - original_metrics["sharpe"], 3)
                },
                "scenario_type": scenario_type,
                "params": params,
                "original_allocation": original_allocation,
                "scenario_allocation": scenario_allocation
            }
            
        except Exception as e:
            print(f"Error running scenario: {e}")
            import traceback
            traceback.print_exc()
            return {
                "original": {"return": 0, "risk": 0, "sharpe": 0},
                "scenario": {"return": 0, "risk": 0, "sharpe": 0},
                "difference": {"return": 0, "risk": 0, "sharpe": 0},
                "error": str(e)
            }

    def _calculate_portfolio_metrics(self, allocation: Dict[str, float]) -> Dict[str, float]:
        """
        Calculate return, risk, and Sharpe ratio for a given allocation.
        """
        try:
            if not allocation:
                return {"return": 0, "risk": 0, "sharpe": 0}
            
            # Get date range
            first_tx = self.db.query(Transaction).order_by(Transaction.activity_date).first()
            last_tx = self.db.query(Transaction).order_by(Transaction.activity_date.desc()).first()
            
            if not first_tx or not last_tx:
                return {"return": 0, "risk": 0, "sharpe": 0}
            
            start_date = first_tx.activity_date
            end_date = last_tx.activity_date
            
            if hasattr(start_date, 'strftime'):
                start_date = start_date.strftime('%Y-%m-%d')
            if hasattr(end_date, 'strftime'):
                end_date = end_date.strftime('%Y-%m-%d')
            
            # Calculate weighted return and risk
            total_return = 0
            total_variance = 0
            
            for ticker, weight in allocation.items():
                try:
                    start_price = self._get_price_at_date(ticker, start_date)
                    end_price = self._get_price_at_date(ticker, end_date)
                    
                    if start_price and end_price and start_price > 0:
                        ticker_return = ((end_price - start_price) / start_price) * 100
                        total_return += weight * ticker_return
                        
                        # Estimate volatility from price history
                        history = stock_price_service.get_price_history(ticker, start_date, end_date)
                        if not history.empty and len(history) > 10:
                            returns = history['close'].pct_change().dropna()
                            volatility = returns.std() * np.sqrt(252) * 100
                            total_variance += (weight ** 2) * (volatility ** 2)
                except Exception:
                    continue
            
            risk = np.sqrt(total_variance) if total_variance > 0 else 0
            risk_free_rate = 2.0  # Assume 2% risk-free rate
            sharpe = (total_return - risk_free_rate) / risk if risk > 0 else 0
            
            return {
                "return": round(total_return, 2),
                "risk": round(risk, 2),
                "sharpe": round(sharpe, 3)
            }
            
        except Exception as e:
            print(f"Error calculating portfolio metrics: {e}")
            return {"return": 0, "risk": 0, "sharpe": 0}

