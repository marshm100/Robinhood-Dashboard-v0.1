"""
Portfolio calculation services
"""

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta, date
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
import json
import time
from io import StringIO

from ..models import Transaction, StockPrice
from .stock_price_service import stock_price_service

# Sector mapping for common stocks and ETFs (50+ entries)
SECTOR_MAPPING = {
    # Broad ETFs
    "SPY": "Large Cap Blend",
    "VOO": "Large Cap Blend",
    "VTI": "Total Market",
    "DIA": "Large Cap Value",
    "IWM": "Small Cap",
    "QQQ": "Technology",
    "EEM": "Emerging Markets",
    "EFA": "International Developed",
    "VNQ": "Real Estate",
    # Sector ETFs
    "XLK": "Technology",
    "XLF": "Financials",
    "XLV": "Healthcare",
    "XLE": "Energy",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLU": "Utilities",
    "XLI": "Industrials",
    "XLB": "Materials",
    "XLC": "Communication Services",
    # Leveraged / Thematic ETFs
    "TQQQ": "Technology",
    "SQQQ": "Technology",
    "TECL": "Technology",
    "TECS": "Technology",
    "SOXL": "Technology",
    "SOXS": "Technology",
    "LABU": "Healthcare",
    "LABD": "Healthcare",
    "SPXL": "Large Cap Blend",
    "SPXS": "Large Cap Blend",
    "BITU": "Cryptocurrency",
    "BITO": "Cryptocurrency",
    "AGQ": "Materials",
    "SILJ": "Materials",
    "GDX": "Materials",
    "GLD": "Materials",
    "SLV": "Materials",
    "USO": "Energy",
    "UNG": "Energy",
    # Technology
    "AAPL": "Technology",
    "MSFT": "Technology",
    "GOOGL": "Technology",
    "AMZN": "Technology",
    "NVDA": "Technology",
    "META": "Technology",
    "TSLA": "Consumer Discretionary",
    "AMD": "Technology",
    "INTC": "Technology",
    "ADBE": "Technology",
    "CRM": "Technology",
    # Financials
    "JPM": "Financials",
    "BAC": "Financials",
    "WFC": "Financials",
    "GS": "Financials",
    "MS": "Financials",
    "V": "Financials",
    "MA": "Financials",
    "PYPL": "Financials",
    "SQ": "Financials",
    # Healthcare
    "JNJ": "Healthcare",
    "PFE": "Healthcare",
    "UNH": "Healthcare",
    "ABBV": "Healthcare",
    "MRK": "Healthcare",
    "ABT": "Healthcare",
    # Consumer
    "WMT": "Consumer Staples",
    "COST": "Consumer Staples",
    "KO": "Consumer Staples",
    "PEP": "Consumer Staples",
    "HD": "Consumer Discretionary",
    "MCD": "Consumer Discretionary",
    "NKE": "Consumer Discretionary",
    "DIS": "Communication Services",
    "SBUX": "Consumer Discretionary",
    # Energy
    "XOM": "Energy",
    "CVX": "Energy",
    "SLB": "Energy",
    # Industrials
    "BA": "Industrials",
    "CAT": "Industrials",
    "DE": "Industrials",
    "UPS": "Industrials",
    "FDX": "Industrials",
    # Materials
    "LIN": "Materials",
    "FCX": "Materials",
    # Communication Services
    "T": "Communication Services",
    "VZ": "Communication Services",
    "TMUS": "Communication Services",
    # Utilities
    "DUK": "Utilities",
    "SO": "Utilities",
    "NEE": "Utilities",
    # Real Estate
    "AMT": "Real Estate",
    "PLD": "Real Estate",
}

# Simple in-memory cache
_cache = {}
_cache_ttl = {}

def _get_cache(key: str, ttl_seconds: int = 1800):
    """Simple in-memory cache with TTL"""
    if key in _cache:
        cached_time, cached_value = _cache_ttl.get(key, (0, None))
        if time.time() - cached_time < ttl_seconds:
            return cached_value
        else:
            del _cache[key]
            del _cache_ttl[key]
    return None

def _set_cache(key: str, value, ttl_seconds: int = 1800):
    """Set cache value with TTL"""
    _cache[key] = value
    _cache_ttl[key] = (time.time(), value)

class PortfolioCalculator:
    """Core portfolio calculation engine"""

    def __init__(self, db: Session):
        self.db = db
        # Instance-level price cache: Dict[ticker, Dict[date_str, price]]
        # Preloaded once and reused across all calculations for efficiency
        self._price_cache: Dict[str, Dict[str, float]] = {}
        self._price_cache_loaded: bool = False

    def _preload_price_cache(self, tickers: Optional[List[str]] = None, 
                              start_date: Optional[str] = None, 
                              end_date: Optional[str] = None) -> None:
        """
        Preload price cache for all tickers in the date range.
        Uses batch query for efficiency - prices fetched once and reused.
        
        Args:
            tickers: List of tickers to cache. If None, uses all tickers from transactions.
            start_date: Start date in YYYY-MM-DD format. If None, uses first transaction date.
            end_date: End date in YYYY-MM-DD format. If None, uses today's date.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Get tickers from transactions if not provided
            if tickers is None:
                transactions = self.db.query(Transaction.ticker).filter(
                    Transaction.ticker.isnot(None)
                ).distinct().all()
                tickers = [t[0] for t in transactions if t[0]]
            
            if not tickers:
                logger.debug("[PriceCache] No tickers to cache")
                return
            
            # Get date range from transactions if not provided
            if not start_date or not end_date:
                first_tx = self.db.query(Transaction).order_by(Transaction.activity_date).first()
                last_tx = self.db.query(Transaction).order_by(Transaction.activity_date.desc()).first()
                
                if first_tx and not start_date:
                    start_date = first_tx.activity_date
                    if isinstance(start_date, (datetime, date)):
                        start_date = start_date.strftime('%Y-%m-%d')
                
                if not end_date:
                    end_date = datetime.now().strftime('%Y-%m-%d')
            
            if not start_date or not end_date:
                logger.warning("[PriceCache] Could not determine date range for cache preload")
                return
            
            logger.info(f"[PriceCache] Preloading prices for {len(tickers)} tickers from {start_date} to {end_date}")
            
            # Batch fetch all prices using the efficient batch method
            batch_data = stock_price_service.get_prices_batch(tickers, start_date, end_date)
            
            # Populate the instance cache from batch data
            for ticker, df in batch_data.items():
                if ticker not in self._price_cache:
                    self._price_cache[ticker] = {}
                
                # Extract close prices by date
                if not df.empty and 'close' in df.columns:
                    for idx, row in df.iterrows():
                        # idx is the date (from DatetimeIndex)
                        date_str = idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx)[:10]
                        if pd.notna(row['close']) and row['close'] > 0:
                            self._price_cache[ticker][date_str] = float(row['close'])
            
            self._price_cache_loaded = True
            total_prices = sum(len(dates) for dates in self._price_cache.values())
            logger.info(f"[PriceCache] Cached {total_prices} prices for {len(self._price_cache)} tickers")
            
        except Exception as e:
            logger.error(f"[PriceCache] Error preloading price cache: {e}")
            # Don't fail - cache is an optimization, not a requirement

    def _get_cached_price(self, ticker: str, date_str: str) -> Optional[float]:
        """
        Get price from instance cache with forward-fill logic.
        
        If exact date not in cache, looks for the most recent prior date.
        Returns None if no cached price available (will fall back to regular lookup).
        
        Args:
            ticker: Stock ticker symbol
            date_str: Date in YYYY-MM-DD format
            
        Returns:
            Cached price if available, None otherwise
        """
        if ticker not in self._price_cache:
            return None
        
        ticker_cache = self._price_cache[ticker]
        
        # Try exact date first
        if date_str in ticker_cache:
            return ticker_cache[date_str]
        
        # Forward-fill: find most recent price before the target date
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            closest_price = None
            closest_date = None
            
            for cached_date_str, price in ticker_cache.items():
                try:
                    cached_date = datetime.strptime(cached_date_str, '%Y-%m-%d').date()
                    if cached_date <= target_date:
                        if closest_date is None or cached_date > closest_date:
                            closest_date = cached_date
                            closest_price = price
                except (ValueError, TypeError):
                    continue
            
            return closest_price
        except (ValueError, TypeError):
            return None

    def _sample_dates(self, start_date: date, end_date: date, 
                      transaction_dates: Optional[List[date]] = None) -> List[date]:
        """
        Sample dates for portfolios with long histories to reduce data points.
        
        Sampling logic:
        - >3 years = monthly (first of each month)
        - >1 year = weekly (every Monday)
        - else = daily (no sampling)
        
        Always includes: first date, last date, and all transaction dates.
        
        Args:
            start_date: Start date of the range
            end_date: End date of the range
            transaction_dates: List of transaction dates to always include
            
        Returns:
            List of dates to use for portfolio calculations
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Ensure dates are date objects
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        elif isinstance(start_date, datetime):
            start_date = start_date.date()
            
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        elif isinstance(end_date, datetime):
            end_date = end_date.date()
        
        # Calculate the date range in days
        date_range_days = (end_date - start_date).days
        
        # Determine sampling frequency based on range length
        # >3 years (1095 days) = monthly, >1 year (365 days) = weekly, else daily
        if date_range_days > 1095:  # >3 years
            sampling_mode = 'monthly'
            logger.info(f"[DateSampling] Using monthly sampling for {date_range_days} day range")
        elif date_range_days > 365:  # >1 year
            sampling_mode = 'weekly'
            logger.info(f"[DateSampling] Using weekly sampling for {date_range_days} day range")
        else:
            sampling_mode = 'daily'
            logger.debug(f"[DateSampling] Using daily (no sampling) for {date_range_days} day range")
        
        # Generate sampled dates based on mode
        sampled_dates = set()
        
        # Always include first and last dates
        sampled_dates.add(start_date)
        sampled_dates.add(end_date)
        
        # Always include transaction dates
        if transaction_dates:
            for tx_date in transaction_dates:
                if isinstance(tx_date, str):
                    try:
                        tx_date = datetime.strptime(tx_date, '%Y-%m-%d').date()
                    except (ValueError, TypeError):
                        continue
                elif isinstance(tx_date, datetime):
                    tx_date = tx_date.date()
                if start_date <= tx_date <= end_date:
                    sampled_dates.add(tx_date)
        
        # Generate sampled dates based on frequency
        if sampling_mode == 'daily':
            # No sampling - include all business days
            current = start_date
            while current <= end_date:
                # Skip weekends (Saturday=5, Sunday=6)
                if current.weekday() < 5:
                    sampled_dates.add(current)
                current += timedelta(days=1)
                
        elif sampling_mode == 'weekly':
            # Weekly sampling - every Monday
            current = start_date
            # Find first Monday
            while current.weekday() != 0:  # 0 = Monday
                current += timedelta(days=1)
            while current <= end_date:
                sampled_dates.add(current)
                current += timedelta(days=7)
                
        elif sampling_mode == 'monthly':
            # Monthly sampling - first business day of each month
            current = start_date.replace(day=1)
            while current <= end_date:
                # Find first business day of month
                first_of_month = current
                while first_of_month.weekday() >= 5:  # Skip weekends
                    first_of_month += timedelta(days=1)
                if start_date <= first_of_month <= end_date:
                    sampled_dates.add(first_of_month)
                # Move to next month
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1)
                else:
                    current = current.replace(month=current.month + 1)
        
        # Sort and return as list
        result = sorted(sampled_dates)
        logger.info(f"[DateSampling] Sampled {len(result)} dates from {date_range_days} day range ({sampling_mode})")
        return result

    def get_current_holdings(self) -> Dict[str, float]:
        """
        Calculate current holdings based on all transactions
        Handles Buy, Sell, and other transaction types that affect positions
        Returns dict of ticker -> quantity
        """
        cache_key = "current_holdings"
        cached = _get_cache(cache_key)
        if cached is not None:
            return cached

        try:
            # Get all transactions ordered by date
            transactions = self.db.query(Transaction).filter(
                Transaction.ticker.isnot(None)
            ).order_by(Transaction.activity_date).all()

            holdings = {}

            for tx in transactions:
                ticker = tx.ticker
                trans_code = tx.trans_code
                quantity = tx.quantity or 0

                if ticker not in holdings:
                    holdings[ticker] = 0

                # Handle different transaction types
                if trans_code == 'Buy':
                    holdings[ticker] += quantity
                elif trans_code == 'Sell':
                    holdings[ticker] -= quantity
                # Add other transaction types that might affect holdings if needed
                # (e.g., stock splits, mergers, etc.)

            # Remove positions that are effectively zero (dust)
            holdings = {ticker: qty for ticker, qty in holdings.items() if abs(qty) > 0.000001}

            _set_cache(cache_key, holdings)
            return holdings

        except Exception as e:
            print(f"Error calculating current holdings: {e}")
            return {}

    def get_portfolio_value_at_date(self, date: str, holdings: Optional[Dict[str, float]] = None) -> float:
        """
        Calculate portfolio value at a specific date
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            if holdings is None:
                holdings = self.get_current_holdings()

            if not holdings:
                return 0.0

            total_value = 0.0
            missing_prices = []

            for ticker, quantity in holdings.items():
                try:
                    price = self.get_stock_price_at_date(ticker, date)
                    if price and price > 0:
                        total_value += quantity * price
                    else:
                        missing_prices.append(ticker)
                except Exception as e:
                    logger.debug(f"[PortfolioCalculator] Error getting price for {ticker} on {date}: {e}")
                    missing_prices.append(ticker)

            if missing_prices:
                logger.debug(f"[PortfolioCalculator] Missing prices for {missing_prices} on {date}")

            return total_value
        except Exception as e:
            logger.error(f"[PortfolioCalculator] Error calculating portfolio value at date {date}: {e}", exc_info=True)
            return 0.0

    def get_stock_price_at_date(self, ticker: str, date: str) -> Optional[float]:
        """
        Get stock price for ticker at specific date
        Uses instance cache, stockr_backbone database, and transaction fallback.
        
        Priority:
        1. Instance price cache (preloaded, fastest)
        2. stockr_backbone historical prices (primary source)
        3. Transaction price fallback (if stockr unavailable)
        
        Returns 0.0 if stock didn't exist (explicit zero), None only for errors.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Check instance cache first (fastest path)
            cached_price = self._get_cached_price(ticker, date)
            if cached_price is not None and cached_price > 0:
                return cached_price
            
            # Try stockr_backbone (primary source)
            price_data = stock_price_service.get_price_at_date(ticker, date)
            if price_data and 'close' in price_data:
                close_price = price_data['close']
                # Cache the result for future lookups
                if ticker not in self._price_cache:
                    self._price_cache[ticker] = {}
                if close_price is not None:
                    self._price_cache[ticker][date] = float(close_price)
                # Return 0.0 if stock didn't exist (explicit zero), None only for errors
                if close_price is not None and close_price > 0:
                    return close_price
            
            # Fallback: use transaction price if stockr_backbone has no data
            fallback_price = self._get_transaction_price_fallback(ticker, date)
            if fallback_price is not None and fallback_price > 0:
                logger.info(f"[PriceFallback] Using transaction price for {ticker} on {date}: ${fallback_price:.2f}")
                # Cache the fallback price too
                if ticker not in self._price_cache:
                    self._price_cache[ticker] = {}
                self._price_cache[ticker][date] = fallback_price
                return fallback_price
            
            # If stockr returned explicit 0 (stock didn't exist), return 0
            if price_data and price_data.get('close') == 0.0:
                return 0.0
                
            return None

        except Exception as e:
            logger.error(f"Error getting price for {ticker} on {date}: {e}")
            return None

    def _get_transaction_price_fallback(self, ticker: str, target_date: str) -> Optional[float]:
        """
        Get price from transaction history as fallback when stockr_backbone has no data.
        
        Looks for transactions of the ticker and returns the price from the
        closest transaction to the target date (preferring earlier transactions).
        
        Args:
            ticker: Stock ticker symbol
            target_date: Date in YYYY-MM-DD format
            
        Returns:
            Transaction price if found, None otherwise
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Parse target date
            if isinstance(target_date, str):
                target_dt = datetime.strptime(target_date, '%Y-%m-%d').date()
            else:
                target_dt = target_date
            
            # Query transactions for this ticker that have a price
            transactions = self.db.query(Transaction).filter(
                and_(
                    Transaction.ticker == ticker.upper(),
                    Transaction.price.isnot(None),
                    Transaction.price > 0
                )
            ).all()
            
            if not transactions:
                return None
            
            # Find the closest transaction to the target date
            closest_tx = None
            min_days_diff = float('inf')
            
            for tx in transactions:
                tx_date = tx.activity_date
                if isinstance(tx_date, str):
                    tx_date = datetime.strptime(tx_date, '%Y-%m-%d').date()
                elif isinstance(tx_date, datetime):
                    tx_date = tx_date.date()
                
                days_diff = abs((tx_date - target_dt).days)
                
                # Prefer transactions on or before the target date
                if tx_date <= target_dt:
                    # Prioritize earlier transactions (more accurate historical price)
                    if days_diff < min_days_diff:
                        min_days_diff = days_diff
                        closest_tx = tx
                elif closest_tx is None:
                    # If no earlier transaction, consider later ones
                    if days_diff < min_days_diff:
                        min_days_diff = days_diff
                        closest_tx = tx
            
            if closest_tx and closest_tx.price and closest_tx.price > 0:
                logger.debug(f"[PriceFallback] Found transaction price for {ticker}: "
                           f"${closest_tx.price:.2f} from {closest_tx.activity_date} "
                           f"({min_days_diff} days from target {target_date})")
                return float(closest_tx.price)
            
            return None
            
        except Exception as e:
            logger.warning(f"[PriceFallback] Error getting transaction price for {ticker}: {e}")
            return None

    def calculate_total_return(self) -> Dict[str, float]:
        """
        Calculate total portfolio return metrics
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            holdings = self.get_current_holdings()

            if not holdings:
                logger.debug("[PortfolioCalculator] No holdings found for total return calculation")
                return {"total_return": 0, "total_value": 0, "start_value": 0, "start_date": "", "end_date": ""}

            # Get date range from transactions
            try:
                first_tx = self.db.query(Transaction).order_by(Transaction.activity_date).first()
                last_tx = self.db.query(Transaction).order_by(Transaction.activity_date.desc()).first()

                if not first_tx or not last_tx:
                    logger.warning("[PortfolioCalculator] No transactions found for total return calculation")
                    return {"total_return": 0, "total_value": 0, "start_value": 0, "start_date": "", "end_date": ""}

                start_date = first_tx.activity_date
                end_date = last_tx.activity_date

                # Ensure dates are strings in YYYY-MM-DD format
                if isinstance(start_date, (datetime, date)):
                    start_date = start_date.strftime('%Y-%m-%d')
                if isinstance(end_date, (datetime, date)):
                    end_date = end_date.strftime('%Y-%m-%d')
            except Exception as e:
                logger.error(f"[PortfolioCalculator] Error getting transaction dates: {e}", exc_info=True)
                return {"total_return": 0, "total_value": 0, "start_value": 0, "start_date": "", "end_date": ""}

            # Calculate values with error handling
            try:
                start_value = self.get_portfolio_value_at_date(start_date, holdings)
            except Exception as e:
                logger.warning(f"[PortfolioCalculator] Error calculating start value: {e}")
                start_value = 0

            try:
                end_value = self.get_portfolio_value_at_date(end_date, holdings)
            except Exception as e:
                logger.warning(f"[PortfolioCalculator] Error calculating end value: {e}")
                end_value = 0

            if start_value == 0:
                total_return = 0
            else:
                total_return = (end_value - start_value) / start_value

            return {
                "total_return": round(total_return * 100, 2),  # As percentage
                "total_value": round(end_value, 2),
                "start_value": round(start_value, 2),
                "start_date": start_date,
                "end_date": end_date
            }

        except Exception as e:
            logger.error(f"[PortfolioCalculator] Error calculating total return: {e}", exc_info=True)
            return {"total_return": 0, "total_value": 0, "start_value": 0, "start_date": "", "end_date": ""}

    def calculate_cagr(self, start_date: str, end_date: str, start_value: float, end_value: float) -> float:
        """
        Calculate Compound Annual Growth Rate (CAGR)
        """
        try:
            if start_value <= 0 or end_value <= 0:
                return 0.0

            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            years = (end_dt - start_dt).days / 365.25

            if years <= 0:
                return 0.0

            cagr = (end_value / start_value) ** (1 / years) - 1
            return round(cagr * 100, 2)  # Return as percentage

        except Exception as e:
            print(f"Error calculating CAGR: {e}")
            return 0.0

    def get_portfolio_value_history(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Get portfolio value over time as a DataFrame
        
        Handles missing price data gracefully by:
        - Continuing processing even if some prices are missing
        - Using last known price when available
        - Returning partial data instead of failing completely
        """
        import logging
        logger = logging.getLogger(__name__)
        
        cache_key = f"portfolio_history:{start_date}:{end_date}"
        cached = _get_cache(cache_key)
        if cached is not None:
            return cached
        
        # Preload price cache for efficiency (if not already loaded)
        if not self._price_cache_loaded:
            self._preload_price_cache(start_date=start_date, end_date=end_date)

        try:
            logger.info(f"[PortfolioCalculator] Getting portfolio value history from {start_date} to {end_date}")
            
            # Validate date range if provided
            if start_date and end_date:
                try:
                    start_dt = datetime.strptime(start_date, '%Y-%m-%d') if isinstance(start_date, str) else start_date
                    end_dt = datetime.strptime(end_date, '%Y-%m-%d') if isinstance(end_date, str) else end_date
                    if start_dt > end_dt:
                        logger.warning(f"[PortfolioCalculator] Invalid date range: {start_date} > {end_date}")
                        return pd.DataFrame()
                except (ValueError, TypeError) as e:
                    logger.warning(f"[PortfolioCalculator] Invalid date format: {e}")
                    return pd.DataFrame()
            
            # Get date range from transactions if not specified
            if not start_date or not end_date:
                first_tx = self.db.query(Transaction).order_by(Transaction.activity_date).first()
                last_tx = self.db.query(Transaction).order_by(Transaction.activity_date.desc()).first()

                if not first_tx or not last_tx:
                    logger.warning("[PortfolioCalculator] No transactions found in database")
                    return pd.DataFrame()

                start_date = start_date or first_tx.activity_date
                end_date = end_date or last_tx.activity_date
                logger.info(f"[PortfolioCalculator] Using date range: {start_date} to {end_date}")

            # Ensure dates are strings in YYYY-MM-DD format
            if isinstance(start_date, (datetime, date)):
                start_date = start_date.strftime('%Y-%m-%d')
            if isinstance(end_date, (datetime, date)):
                end_date = end_date.strftime('%Y-%m-%d')

            # Validate date strings are in correct format
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
                datetime.strptime(end_date, '%Y-%m-%d')
            except (ValueError, TypeError) as e:
                logger.error(f"[PortfolioCalculator] Invalid date format after conversion: {e}")
                return pd.DataFrame()

            # Get all transactions in date range
            try:
                transactions = self.db.query(Transaction).filter(
                    Transaction.activity_date.between(start_date, end_date)
                ).order_by(Transaction.activity_date).all()
            except Exception as e:
                logger.error(f"[PortfolioCalculator] Error querying transactions: {e}", exc_info=True)
                # Return empty DataFrame instead of raising exception
                return pd.DataFrame()
            except AttributeError as e:
                logger.error(f"[PortfolioCalculator] Database session error: {e}", exc_info=True)
                return pd.DataFrame()

            if not transactions:
                logger.warning(f"[PortfolioCalculator] No transactions found in date range {start_date} to {end_date}")
                return pd.DataFrame()

            logger.info(f"[PortfolioCalculator] Processing {len(transactions)} transactions")

            # Calculate portfolio value at each transaction date
            value_history = []
            current_holdings = {}
            last_known_prices = {}  # Cache for last known prices to use when exact date price is missing
            
            # Group transactions by date
            transactions_by_date = {}
            for tx in transactions:
                try:
                    # Ensure date is a string
                    date_str = tx.activity_date
                    if isinstance(date_str, (datetime, date)):
                        date_str = date_str.strftime('%Y-%m-%d')
                    elif not isinstance(date_str, str):
                        date_str = str(date_str)
                    
                    if date_str not in transactions_by_date:
                        transactions_by_date[date_str] = []
                    transactions_by_date[date_str].append(tx)
                except Exception as e:
                    logger.warning(f"[PortfolioCalculator] Error processing transaction date: {e}")
                    continue

            if not transactions_by_date:
                logger.warning("[PortfolioCalculator] No valid transaction dates found")
                return pd.DataFrame()

            # Get sorted transaction dates
            sorted_dates = sorted(transactions_by_date.keys())
            
            # Use intelligent date sampling based on date range length
            # >3 years = monthly, >1 year = weekly, else daily
            # Always includes first, last, and all transaction dates
            start_dt = datetime.strptime(sorted_dates[0], '%Y-%m-%d').date()
            end_dt = datetime.strptime(sorted_dates[-1], '%Y-%m-%d').date()
            transaction_date_list = [datetime.strptime(d, '%Y-%m-%d').date() for d in sorted_dates]
            
            sampled_date_objs = self._sample_dates(start_dt, end_dt, transaction_date_list)
            sampled_dates = [d.strftime('%Y-%m-%d') for d in sampled_date_objs]

            # Pre-fetch all prices in batch for performance
            all_tickers = set()
            for date_str in sorted_dates:
                for tx in transactions_by_date[date_str]:
                    if tx.ticker:
                        all_tickers.add(tx.ticker)
            
            # Batch fetch all prices at once
            batch_prices = {}
            if all_tickers and sampled_dates:
                batch_prices = stock_price_service.get_prices_at_dates_batch(
                    list(all_tickers), 
                    sampled_dates
                )
                logger.info(f"[PortfolioCalculator] Batch fetched prices for {len(batch_prices)} tickers")

            # Process all dates to track holdings, but only calculate values for sampled dates
            for date_str in sorted_dates:
                try:
                    # Apply transactions for this date
                    for tx in transactions_by_date[date_str]:
                        if tx.ticker:
                            if tx.ticker not in current_holdings:
                                current_holdings[tx.ticker] = 0

                            if tx.trans_code == 'Buy':
                                current_holdings[tx.ticker] += tx.quantity or 0
                            elif tx.trans_code == 'Sell':
                                current_holdings[tx.ticker] -= tx.quantity or 0

                    # Remove zero positions
                    current_holdings = {k: v for k, v in current_holdings.items() if abs(v) > 0.000001}

                    # Only calculate portfolio value for sampled dates
                    if date_str not in sampled_dates:
                        continue

                    # Calculate portfolio value at this date using batch prices
                    portfolio_value = 0.0
                    missing_prices = []
                    
                    for ticker, quantity in current_holdings.items():
                        try:
                            # Use batch-fetched price first
                            price = None
                            if ticker in batch_prices and date_str in batch_prices[ticker]:
                                price = batch_prices[ticker][date_str]
                            
                            # Fall back to individual lookup if needed
                            if not price or price <= 0:
                                price = self.get_stock_price_at_date(ticker, date_str)
                            
                            # If still no price, try using last known price
                            if not price or price <= 0:
                                if ticker in last_known_prices:
                                    price = last_known_prices[ticker]
                                else:
                                    missing_prices.append(ticker)
                                    continue
                            
                            # Update last known price cache
                            if price and price > 0:
                                last_known_prices[ticker] = price
                                portfolio_value += quantity * price
                                
                        except Exception as e:
                            logger.warning(f"[PortfolioCalculator] Error getting price for {ticker} on {date_str}: {e}")
                            if ticker in last_known_prices:
                                portfolio_value += quantity * last_known_prices[ticker]
                            else:
                                missing_prices.append(ticker)

                    if missing_prices:
                        logger.debug(f"[PortfolioCalculator] Missing prices for {missing_prices} on {date_str}")

                    # Only add to history if we have some value or holdings
                    if portfolio_value > 0 or current_holdings:
                        value_history.append({
                            'date': date_str,
                            'portfolio_value': portfolio_value,
                            'holdings': current_holdings.copy()
                        })
                except Exception as e:
                    logger.error(f"[PortfolioCalculator] Error processing date {date_str}: {e}", exc_info=True)
                    continue

            if not value_history:
                logger.warning("[PortfolioCalculator] No value history data generated")
                return pd.DataFrame()

            df = pd.DataFrame(value_history)
            _set_cache(cache_key, df)
            logger.info(f"[PortfolioCalculator] Generated {len(df)} history points")
            return df

        except Exception as e:
            logger.error(f"[PortfolioCalculator] Error getting portfolio value history: {e}", exc_info=True)
            return pd.DataFrame()

    def calculate_rolling_returns(self, periods: List[int] = [1, 3, 5, 10]) -> Dict[str, float]:
        """
        Calculate rolling period returns (1Y, 3Y, 5Y, 10Y)
        """
        try:
            value_history = self.get_portfolio_value_history()

            if value_history.empty or len(value_history) < 2:
                return {f"{period}Y": 0.0 for period in periods}

            # Convert date column to datetime if needed
            if not pd.api.types.is_datetime64_any_dtype(value_history['date']):
                value_history['date'] = pd.to_datetime(value_history['date'])

            value_history = value_history.set_index('date')
            value_history = value_history.sort_index()

            rolling_returns = {}

            for years in periods:
                try:
                    # Calculate rolling return over the period
                    end_date = value_history.index[-1]
                    start_date = end_date - pd.DateOffset(years=years)

                    # Find the closest dates we have data for
                    available_dates = value_history.index
                    start_idx = available_dates.get_indexer([start_date], method='nearest')[0]
                    end_idx = len(available_dates) - 1

                    if start_idx >= end_idx:
                        rolling_returns[f"{years}Y"] = 0.0
                        continue

                    start_value = value_history.iloc[start_idx]['portfolio_value']
                    end_value = value_history.iloc[end_idx]['portfolio_value']

                    if start_value > 0:
                        rolling_return = (end_value / start_value) ** (1 / years) - 1
                        rolling_returns[f"{years}Y"] = round(rolling_return * 100, 2)
                    else:
                        rolling_returns[f"{years}Y"] = 0.0

                except Exception as e:
                    print(f"Error calculating {years}Y rolling return: {e}")
                    rolling_returns[f"{years}Y"] = 0.0

            return rolling_returns

        except Exception as e:
            print(f"Error calculating rolling returns: {e}")
            return {f"{period}Y": 0.0 for period in periods}

    def calculate_performance_metrics(self) -> Dict[str, Any]:
        """
        Calculate comprehensive performance metrics
        """
        try:
            value_history = self.get_portfolio_value_history()

            if value_history.empty:
                return {
                    "total_return": 0.0,
                    "cagr": 0.0,
                    "rolling_returns": {},
                    "volatility": 0.0,
                    "max_drawdown": 0.0,
                    "sharpe_ratio": 0.0,
                    "sortino_ratio": 0.0,
                    "calmar_ratio": 0.0,
                    "downside_deviation": 0.0,
                    "recovery_time": None,
                    "underwater_period": None
                }

            # Convert to datetime index
            value_history['date'] = pd.to_datetime(value_history['date'])
            value_history = value_history.set_index('date')
            value_history = value_history.sort_index()

            # Calculate returns
            value_history['returns'] = value_history['portfolio_value'].pct_change()

            # Basic metrics
            start_value = value_history['portfolio_value'].iloc[0]
            end_value = value_history['portfolio_value'].iloc[-1]
            total_return = ((end_value / start_value) - 1) * 100 if start_value > 0 else 0

            # CAGR
            days = (value_history.index[-1] - value_history.index[0]).days
            years = days / 365.25
            cagr = ((end_value / start_value) ** (1 / years) - 1) * 100 if start_value > 0 and years > 0 else 0

            # Volatility (annualized)
            daily_volatility = value_history['returns'].std()
            volatility = daily_volatility * np.sqrt(252) * 100  # Annualized

            # Max drawdown
            cumulative = (1 + value_history['returns']).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max
            max_drawdown = drawdown.min() * 100

            # Sharpe ratio (assuming 2% risk-free rate)
            risk_free_rate = 0.02
            excess_returns = value_history['returns'] - risk_free_rate / 252
            sharpe_ratio = excess_returns.mean() / excess_returns.std() * np.sqrt(252) if excess_returns.std() > 0 else 0

            # Sortino Ratio (downside deviation only)
            downside_returns = value_history['returns'][value_history['returns'] < 0]
            downside_deviation = downside_returns.std() * np.sqrt(252) if not downside_returns.empty else 0
            sortino_ratio = excess_returns.mean() / downside_deviation * np.sqrt(252) if downside_deviation > 0 else 0

            # Calmar Ratio (CAGR / Max Drawdown)
            calmar_ratio = cagr / abs(max_drawdown) if max_drawdown < 0 else 0

            # Downside Deviation (annualized)
            downside_deviation_pct = downside_deviation * 100

            # Calculate drawdown recovery metrics
            recovery_metrics = self._calculate_drawdown_recovery_metrics(drawdown, value_history)

            # Calculate rolling returns
            rolling_returns = self._calculate_rolling_returns(value_history)

            return {
                "total_return": total_return,
                "cagr": cagr,
                "rolling_returns": rolling_returns,
                "volatility": volatility,
                "max_drawdown": max_drawdown,
                "sharpe_ratio": sharpe_ratio,
                "sortino_ratio": sortino_ratio,
                "calmar_ratio": calmar_ratio,
                "downside_deviation": downside_deviation_pct,
                "recovery_time": recovery_metrics.get("recovery_time"),
                "underwater_period": recovery_metrics.get("underwater_period"),
                "worst_drawdown": recovery_metrics.get("worst_drawdown")
            }

            # Rolling returns
            rolling_returns = self.calculate_rolling_returns()

            # Handle NaN values for JSON serialization
            def safe_round(value, decimals=2):
                if pd.isna(value) or (isinstance(value, float) and (value != value)):  # Check for NaN
                    return 0.0
                try:
                    return round(float(value), decimals)
                except (ValueError, TypeError, OverflowError):
                    return 0.0

            return {
                "total_return": safe_round(total_return),
                "cagr": safe_round(cagr),
                "volatility": safe_round(volatility),
                "max_drawdown": safe_round(max_drawdown),
                "sharpe_ratio": safe_round(sharpe_ratio),
                "rolling_returns": {k: safe_round(v) for k, v in rolling_returns.items()},
                "start_value": safe_round(start_value),
                "end_value": safe_round(end_value),
                "period_days": days,
                "period_years": safe_round(years)
            }

        except Exception as e:
            print(f"Error calculating performance metrics: {e}")
            return {
                "total_return": 0.0,
                "cagr": 0.0,
                "rolling_returns": {},
                "volatility": 0.0,
                "max_drawdown": 0.0,
                "sharpe_ratio": 0.0
            }

    def calculate_position_weights(self) -> Dict[str, float]:
        """
        Calculate position weights as percentage of total portfolio value
        """
        try:
            holdings = self.get_current_holdings()
            if not holdings:
                return {}

            # Calculate total portfolio value
            total_value = 0.0
            position_values = {}

            for ticker, quantity in holdings.items():
                price = self.get_stock_price_at_date(ticker, self._get_latest_date())
                if price and price > 0:
                    position_value = quantity * price
                    position_values[ticker] = position_value
                    total_value += position_value

            if total_value == 0:
                return {}

            # Calculate weights as percentages
            weights = {}
            for ticker, position_value in position_values.items():
                weights[ticker] = round((position_value / total_value) * 100, 2)

            return weights

        except Exception as e:
            print(f"Error calculating position weights: {e}")
            return {}

    def calculate_diversification_metrics(self) -> Dict[str, Any]:
        """
        Calculate diversification metrics including concentration risk
        """
        try:
            weights = self.calculate_position_weights()
            if not weights:
                return {
                    "effective_bets": 0,
                    "concentration_ratio": 0.0,
                    "largest_position": 0.0,
                    "diversification_score": 0.0
                }

            positions = list(weights.values())

            # Effective number of bets (inverse Herfindahl-Hirschman Index)
            herfindahl = sum(w ** 2 for w in positions) / 10000  # Convert to decimal
            effective_bets = 1 / herfindahl if herfindahl > 0 else 0

            # Concentration ratio (percentage in largest position)
            largest_position = max(positions) if positions else 0

            # Diversification score (0-100, higher is better diversified)
            # Based on number of positions and weight distribution
            num_positions = len(positions)
            avg_weight = 100 / num_positions if num_positions > 0 else 0

            # Calculate deviation from equal weighting
            weight_deviation = sum(abs(w - avg_weight) for w in positions) / num_positions
            diversification_score = max(0, 100 - (weight_deviation * 2))

            return {
                "effective_bets": round(effective_bets, 2),
                "concentration_ratio": round(largest_position, 2),
                "largest_position": round(largest_position, 2),
                "num_positions": num_positions,
                "diversification_score": round(diversification_score, 2)
            }

        except Exception as e:
            print(f"Error calculating diversification metrics: {e}")
            return {
                "effective_bets": 0,
                "concentration_ratio": 0.0,
                "largest_position": 0.0,
                "diversification_score": 0.0
            }

    def _get_latest_date(self) -> str:
        """Get the latest transaction date"""
        try:
            latest_tx = self.db.query(Transaction).order_by(Transaction.activity_date.desc()).first()
            return latest_tx.activity_date if latest_tx else ""
        except Exception:
            return ""

    def analyze_market_conditions(self) -> Dict[str, Any]:
        """
        Analyze portfolio performance in different market conditions
        """
        try:
            earliest = self._get_earliest_date()
            latest = self._get_latest_date()
            
            if not earliest or not latest:
                print("[CALCULATOR] No date range available for market conditions analysis")
                return {"market_conditions": {}, "regime_analysis": {}}
            
            # Get benchmark performance (SPY)
            spy_history = stock_price_service.get_price_history("SPY", earliest, latest)

            if spy_history.empty:
                print("[CALCULATOR] SPY data not available - ensure SPY is tracked in stockr_backbone")
                return {"market_conditions": {}, "regime_analysis": {}}

            # Calculate market returns
            spy_returns = spy_history.set_index('date')['close'].pct_change().dropna()

            # Define market regimes
            bull_threshold = 0.005  # 0.5% daily return = bull market
            bear_threshold = -0.005  # -0.5% daily return = bear market

            bull_days = (spy_returns > bull_threshold).sum()
            bear_days = (spy_returns < bear_threshold).sum()
            neutral_days = ((spy_returns <= bull_threshold) & (spy_returns >= bear_threshold)).sum()

            total_days = len(spy_returns)
            bull_percentage = (bull_days / total_days) * 100 if total_days > 0 else 0
            bear_percentage = (bear_days / total_days) * 100 if total_days > 0 else 0
            neutral_percentage = (neutral_days / total_days) * 100 if total_days > 0 else 0

            # Get portfolio returns for comparison
            portfolio_history = self.get_portfolio_value_history()
            if not portfolio_history.empty:
                portfolio_returns = portfolio_history.set_index('date')['portfolio_value'].pct_change().dropna()

                # Align dates
                common_dates = portfolio_returns.index.intersection(spy_returns.index)
                if len(common_dates) > 30:  # Need minimum data
                    aligned_portfolio = portfolio_returns.loc[common_dates]
                    aligned_market = spy_returns.loc[common_dates]

                    # Performance in different regimes
                    bull_mask = aligned_market > bull_threshold
                    bear_mask = aligned_market < bear_threshold
                    neutral_mask = (aligned_market <= bull_threshold) & (aligned_market >= bear_threshold)

                    bull_performance = aligned_portfolio[bull_mask].mean() * 252 if bull_mask.sum() > 0 else 0
                    bear_performance = aligned_portfolio[bear_mask].mean() * 252 if bear_mask.sum() > 0 else 0
                    neutral_performance = aligned_portfolio[neutral_mask].mean() * 252 if neutral_mask.sum() > 0 else 0

                    # Market timing ability (beta in different regimes)
                    bull_beta = self._calculate_conditional_beta(aligned_portfolio[bull_mask], aligned_market[bull_mask])
                    bear_beta = self._calculate_conditional_beta(aligned_portfolio[bear_mask], aligned_market[bear_mask])

                    return {
                        "market_conditions": {
                            "bull_market_days": int(bull_days),
                            "bear_market_days": int(bear_days),
                            "neutral_market_days": int(neutral_days),
                            "bull_percentage": round(bull_percentage, 2),
                            "bear_percentage": round(bear_percentage, 2),
                            "neutral_percentage": round(neutral_percentage, 2)
                        },
                        "regime_analysis": {
                            "bull_market_performance": round(bull_performance * 100, 2),
                            "bear_market_performance": round(bear_performance * 100, 2),
                            "neutral_market_performance": round(neutral_performance * 100, 2),
                            "bull_market_beta": round(bull_beta, 4),
                            "bear_market_beta": round(bear_beta, 4)
                        }
                    }

            return {
                "market_conditions": {
                    "bull_market_days": int(bull_days),
                    "bear_market_days": int(bear_days),
                    "neutral_market_days": int(neutral_days),
                    "bull_percentage": round(bull_percentage, 2),
                    "bear_percentage": round(bear_percentage, 2),
                    "neutral_percentage": round(neutral_percentage, 2)
                },
                "regime_analysis": {}
            }

        except Exception as e:
            print(f"Error analyzing market conditions: {e}")
            return {"market_conditions": {}, "regime_analysis": {}}

    def _get_earliest_date(self) -> str:
        """Get the earliest transaction date"""
        try:
            earliest_tx = self.db.query(Transaction).order_by(Transaction.activity_date).first()
            return earliest_tx.activity_date if earliest_tx else ""
        except Exception:
            return ""

    def _calculate_conditional_beta(self, portfolio_returns: pd.Series, market_returns: pd.Series) -> float:
        """Calculate beta for specific market conditions"""
        try:
            if len(portfolio_returns) < 10 or len(market_returns) < 10:
                return 0.0

            covariance = portfolio_returns.cov(market_returns)
            market_variance = market_returns.var()

            return covariance / market_variance if market_variance > 0 else 0.0
        except Exception:
            return 0.0

    def calculate_tracking_error(self, benchmark: str = "SPY") -> float:
        """
        Calculate tracking error against a benchmark
        """
        try:
            # Get portfolio returns
            portfolio_history = self.get_portfolio_value_history()
            if portfolio_history.empty:
                return 0.0

            portfolio_returns = portfolio_history.set_index('date')['portfolio_value'].pct_change().dropna()

            # Get benchmark returns
            benchmark_history = stock_price_service.get_price_history(
                benchmark,
                portfolio_history['date'].min(),
                portfolio_history['date'].max()
            )

            if benchmark_history.empty:
                return 0.0

            benchmark_returns = benchmark_history.set_index('date')['close'].pct_change().dropna()

            # Align dates
            common_dates = portfolio_returns.index.intersection(benchmark_returns.index)
            if len(common_dates) < 30:  # Need minimum data
                return 0.0

            aligned_portfolio = portfolio_returns.loc[common_dates]
            aligned_benchmark = benchmark_returns.loc[common_dates]

            # Calculate excess returns
            excess_returns = aligned_portfolio - aligned_benchmark

            # Tracking error is the standard deviation of excess returns
            tracking_error = excess_returns.std() * (252 ** 0.5)  # Annualized

            return round(tracking_error * 100, 2)  # As percentage

        except Exception as e:
            print(f"Error calculating tracking error: {e}")
            return 0.0

    def calculate_information_ratio(self, benchmark: str = "SPY") -> float:
        """
        Calculate information ratio (excess return / tracking error)
        """
        try:
            tracking_error = self.calculate_tracking_error(benchmark)
            if tracking_error == 0:
                return 0.0

            # Get average excess return
            portfolio_history = self.get_portfolio_value_history()
            if portfolio_history.empty:
                return 0.0

            benchmark_history = stock_price_service.get_price_history(
                benchmark,
                portfolio_history['date'].min(),
                portfolio_history['date'].max()
            )

            if benchmark_history.empty:
                return 0.0

            # Calculate total returns
            portfolio_start = portfolio_history['portfolio_value'].iloc[0]
            portfolio_end = portfolio_history['portfolio_value'].iloc[-1]
            benchmark_start = benchmark_history['close'].iloc[0]
            benchmark_end = benchmark_history['close'].iloc[-1]

            portfolio_return = (portfolio_end / portfolio_start) - 1 if portfolio_start > 0 else 0
            benchmark_return = (benchmark_end / benchmark_start) - 1 if benchmark_start > 0 else 0

            excess_return = portfolio_return - benchmark_return

            # Information ratio
            information_ratio = (excess_return / (tracking_error / 100)) if tracking_error > 0 else 0

            return round(information_ratio, 4)

        except Exception as e:
            print(f"Error calculating information ratio: {e}")
            return 0.0

    def get_sector_allocation(self) -> Dict[str, Any]:
        """
        Get sector allocation based on position weights
        Note: This is a simplified sector mapping - in production you'd want a comprehensive database
        """
        try:
            weights = self.calculate_position_weights()
            if not weights:
                return {"sector_allocation": {}, "sector_weights": {}}

            sector_weights = {}
            total_weight = sum(weights.values())

            for ticker, weight in weights.items():
                sector = SECTOR_MAPPING.get(ticker.upper(), 'Unknown')
                if sector not in sector_weights:
                    sector_weights[sector] = 0
                sector_weights[sector] += weight

            # Sort by weight
            sector_weights = dict(sorted(sector_weights.items(), key=lambda x: x[1], reverse=True))

            return {
                "sector_allocation": sector_weights,
                "sector_count": len(sector_weights),
                "largest_sector": max(sector_weights.items(), key=lambda x: x[1]) if sector_weights else ("None", 0)
            }

        except Exception as e:
            print(f"Error getting sector allocation: {e}")
            return {"sector_allocation": {}, "sector_weights": {}}

    def get_portfolio_optimization_recommendations(self) -> Dict[str, Any]:
        """
        Get portfolio optimization recommendations based on current allocation
        """
        try:
            diversification = self.calculate_diversification_metrics()
            weights = self.calculate_position_weights()
            sector_allocation = self.get_sector_allocation()

            recommendations = []
            risk_level = "unknown"

            # Analyze diversification
            if diversification['effective_bets'] < 3:
                recommendations.append({
                    "type": "diversification",
                    "priority": "high",
                    "message": "Consider increasing diversification. Current effective number of bets is low.",
                    "suggestion": "Add positions in uncorrelated assets or sectors."
                })

            if diversification['concentration_ratio'] > 30:
                recommendations.append({
                    "type": "concentration",
                    "priority": "high",
                    "message": f"Portfolio is heavily concentrated with {diversification['concentration_ratio']}% in the largest position.",
                    "suggestion": "Reduce position sizes in concentrated holdings."
                })

            # Analyze sector allocation
            if sector_allocation['sector_count'] < 3:
                recommendations.append({
                    "type": "sector",
                    "priority": "medium",
                    "message": f"Portfolio spans only {sector_allocation['sector_count']} sectors.",
                    "suggestion": "Consider adding exposure to additional sectors for better diversification."
                })

            largest_sector = sector_allocation.get('largest_sector', ('None', 0))
            if largest_sector[1] > 50:
                recommendations.append({
                    "type": "sector_concentration",
                    "priority": "medium",
                    "message": f"{largest_sector[0]} sector represents {largest_sector[1]}% of portfolio.",
                    "suggestion": "Consider reducing sector concentration for better risk management."
                })

            # Determine risk level
            if diversification['diversification_score'] > 70:
                risk_level = "well_diversified"
            elif diversification['diversification_score'] > 40:
                risk_level = "moderately_diversified"
            else:
                risk_level = "concentrated"

            # Rebalancing suggestions
            rebalance_threshold = 5.0  # 5% deviation threshold
            rebalance_candidates = []
            equal_weight = 100 / len(weights) if weights else 0

            for ticker, weight in weights.items():
                deviation = abs(weight - equal_weight)
                if deviation > rebalance_threshold:
                    rebalance_candidates.append({
                        "ticker": ticker,
                        "current_weight": weight,
                        "target_weight": equal_weight,
                        "deviation": round(deviation, 2)
                    })

            return {
                "risk_level": risk_level,
                "recommendations": recommendations,
                "rebalancing_opportunities": rebalance_candidates,
                "equal_weight_target": round(equal_weight, 2) if equal_weight > 0 else 0
            }

        except Exception as e:
            print(f"Error getting optimization recommendations: {e}")
            return {
                "risk_level": "unknown",
                "recommendations": [],
                "rebalancing_opportunities": []
            }

    def get_advanced_analytics(self) -> Dict[str, Any]:
        """
        Get comprehensive advanced analytics
        """
        print("[CALCULATOR] Starting advanced analytics calculation")

        try:
            # Get basic components
            print("[CALCULATOR] Calculating position weights...")
            weights = self.calculate_position_weights()
            print(f"[CALCULATOR] Position weights calculated: {len(weights)} positions")

            print("[CALCULATOR] Calculating diversification metrics...")
            diversification = self.calculate_diversification_metrics()

            print("[CALCULATOR] Analyzing market conditions...")
            market_conditions = self.analyze_market_conditions()

            print("[CALCULATOR] Calculating tracking error...")
            tracking_error = self.calculate_tracking_error()

            print("[CALCULATOR] Calculating information ratio...")
            information_ratio = self.calculate_information_ratio()

            print("[CALCULATOR] Getting sector allocation...")
            sector_allocation = self.get_sector_allocation()

            print("[CALCULATOR] Getting optimization recommendations...")
            optimization = self.get_portfolio_optimization_recommendations()

            print("[CALCULATOR] Advanced analytics calculation completed")

            return {
                "position_weights": weights,
                "diversification_metrics": diversification,
                "sector_allocation": sector_allocation,
                "market_conditions": market_conditions,
                "benchmarking": {
                    "tracking_error": tracking_error,
                    "information_ratio": information_ratio
                },
                "optimization_recommendations": optimization
            }

        except Exception as e:
            print(f"Error getting advanced analytics: {e}")
            return {
                "position_weights": {},
                "diversification_metrics": {
                    "effective_bets": 0,
                    "concentration_ratio": 0.0,
                    "largest_position": 0.0,
                    "diversification_score": 0.0
                },
                "sector_allocation": {"sector_allocation": {}, "sector_weights": {}},
                "market_conditions": {"market_conditions": {}, "regime_analysis": {}},
                "benchmarking": {
                    "tracking_error": 0.0,
                    "information_ratio": 0.0
                },
                "optimization_recommendations": {
                    "risk_level": "unknown",
                    "recommendations": [],
                    "rebalancing_opportunities": []
                }
            }

        except Exception as e:
            print(f"Error calculating performance metrics: {e}")
            return {
                "total_return": 0.0,
                "cagr": 0.0,
                "rolling_returns": {},
                "volatility": 0.0,
                "max_drawdown": 0.0,
                "sharpe_ratio": 0.0
            }

    def calculate_value_at_risk(self, confidence_level: float = 0.95) -> Dict[str, float]:
        """
        Calculate Value at Risk (VaR) using historical simulation
        """
        try:
            value_history = self.get_portfolio_value_history()

            if value_history.empty or len(value_history) < 30:  # Need minimum data
                return {
                    "var_95": 0.0,
                    "var_99": 0.0,
                    "expected_shortfall": 0.0
                }

            # Calculate daily returns
            value_history['date'] = pd.to_datetime(value_history['date'])
            value_history = value_history.set_index('date')
            value_history = value_history.sort_index()
            value_history['returns'] = value_history['portfolio_value'].pct_change()

            # Remove NaN values
            returns = value_history['returns'].dropna()

            if len(returns) < 30:
                return {
                    "var_95": 0.0,
                    "var_99": 0.0,
                    "expected_shortfall": 0.0
                }

            # Calculate VaR at different confidence levels
            var_95 = np.percentile(returns, (1 - 0.95) * 100)
            var_99 = np.percentile(returns, (1 - 0.99) * 100)

            # Expected Shortfall (CVaR) - average of losses beyond VaR
            cvar_95 = returns[returns <= var_95].mean() if len(returns[returns <= var_95]) > 0 else var_95

            return {
                "var_95": round(var_95 * 100, 2),  # As percentage
                "var_99": round(var_99 * 100, 2),
                "expected_shortfall": round(cvar_95 * 100, 2)
            }

        except Exception as e:
            print(f"Error calculating Value at Risk: {e}")
            return {
                "var_95": 0.0,
                "var_99": 0.0,
                "expected_shortfall": 0.0
            }

    def calculate_correlation_matrix(self) -> pd.DataFrame:
        """
        Calculate correlation matrix between portfolio assets
        """
        try:
            # Get all unique tickers
            tickers = list(set(
                tx.ticker for tx in self.db.query(Transaction.ticker).filter(Transaction.ticker.isnot(None)).all()
            ))

            if len(tickers) < 2:
                return pd.DataFrame()

            # Get price history for each ticker over the portfolio period
            price_data = {}

            # Get date range
            first_tx = self.db.query(Transaction).order_by(Transaction.activity_date).first()
            last_tx = self.db.query(Transaction).order_by(Transaction.activity_date.desc()).first()

            if not first_tx or not last_tx:
                return pd.DataFrame()

            start_date = first_tx.activity_date
            end_date = last_tx.activity_date

            for ticker in tickers:
                history = stock_price_service.get_price_history(ticker, start_date, end_date)
                if not history.empty:
                    # Use close prices
                    price_data[ticker] = history.set_index('date')['close']

            if not price_data:
                return pd.DataFrame()

            # Create DataFrame with all price series
            price_df = pd.DataFrame(price_data)

            # Calculate daily returns
            returns_df = price_df.pct_change().dropna()

            # Calculate correlation matrix
            if not returns_df.empty and len(returns_df.columns) > 1:
                corr_matrix = returns_df.corr()
                return corr_matrix.round(4)
            else:
                return pd.DataFrame()

        except Exception as e:
            print(f"Error calculating correlation matrix: {e}")
            return pd.DataFrame()

    def calculate_beta_coefficient(self, benchmark_ticker: str = "SPY") -> Dict[str, float]:
        """
        Calculate beta coefficient against a benchmark
        """
        try:
            # Get portfolio returns
            value_history = self.get_portfolio_value_history()

            if value_history.empty:
                return {"beta": 0.0, "alpha": 0.0, "r_squared": 0.0}

            portfolio_returns = value_history.set_index('date')['portfolio_value'].pct_change().dropna()

            # Get benchmark returns
            benchmark_history = stock_price_service.get_price_history(
                benchmark_ticker,
                value_history['date'].min(),
                value_history['date'].max()
            )

            if benchmark_history.empty:
                return {"beta": 0.0, "alpha": 0.0, "r_squared": 0.0}

            benchmark_returns = benchmark_history.set_index('date')['close'].pct_change().dropna()

            # Align the data
            combined = pd.DataFrame({
                'portfolio': portfolio_returns,
                'benchmark': benchmark_returns
            }).dropna()

            if len(combined) < 30:  # Need minimum data points
                return {"beta": 0.0, "alpha": 0.0, "r_squared": 0.0}

            # Calculate beta using linear regression
            covariance = combined.cov().iloc[0, 1]
            benchmark_variance = combined['benchmark'].var()

            if benchmark_variance > 0:
                beta = covariance / benchmark_variance

                # Calculate alpha and R-squared
                correlation = combined.corr().iloc[0, 1]
                r_squared = correlation ** 2

                # Simple alpha calculation (excess return over benchmark)
                portfolio_avg_return = combined['portfolio'].mean()
                benchmark_avg_return = combined['benchmark'].mean()
                alpha = portfolio_avg_return - beta * benchmark_avg_return

                return {
                    "beta": round(beta, 4),
                    "alpha": round(alpha * 100, 4),  # As percentage
                    "r_squared": round(r_squared, 4)
                }
            else:
                return {"beta": 0.0, "alpha": 0.0, "r_squared": 0.0}

        except Exception as e:
            print(f"Error calculating beta coefficient: {e}")
            return {"beta": 0.0, "alpha": 0.0, "r_squared": 0.0}

    def calculate_sortino_ratio(self, target_return: float = 0.0) -> float:
        """
        Calculate Sortino ratio (downside deviation only)
        """
        try:
            value_history = self.get_portfolio_value_history()

            if value_history.empty:
                return 0.0

            # Calculate daily returns
            value_history['date'] = pd.to_datetime(value_history['date'])
            value_history = value_history.set_index('date')
            value_history = value_history.sort_index()
            returns = value_history['portfolio_value'].pct_change().dropna()

            # Calculate downside deviation (only negative returns)
            downside_returns = returns[returns < target_return]
            if len(downside_returns) == 0:
                return 0.0

            downside_deviation = np.sqrt(np.mean(downside_returns ** 2))

            # Annualize
            annualized_downside_deviation = downside_deviation * np.sqrt(252)

            # Calculate average return
            avg_return = returns.mean()

            # Sortino ratio
            if annualized_downside_deviation > 0:
                sortino_ratio = (avg_return - target_return) / annualized_downside_deviation
                return round(sortino_ratio, 4)
            else:
                return 0.0

        except Exception as e:
            print(f"Error calculating Sortino ratio: {e}")
            return 0.0

    def get_risk_assessment(self) -> Dict[str, Any]:
        """
        Get comprehensive risk assessment
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            try:
                performance = self.calculate_performance_metrics()
            except Exception as e:
                logger.warning(f"[PortfolioCalculator] Error calculating performance metrics: {e}", exc_info=True)
                performance = {
                    "volatility": 0.0,
                    "max_drawdown": 0.0,
                    "sharpe_ratio": 0.0
                }
            
            try:
                var_metrics = self.calculate_value_at_risk()
            except Exception as e:
                logger.warning(f"[PortfolioCalculator] Error calculating VaR: {e}", exc_info=True)
                var_metrics = {
                    "var_95": 0.0,
                    "var_99": 0.0,
                    "expected_shortfall": 0.0
                }
            
            try:
                beta_metrics = self.calculate_beta_coefficient()
            except Exception as e:
                logger.warning(f"[PortfolioCalculator] Error calculating beta: {e}", exc_info=True)
                beta_metrics = {
                    "beta": 0.0,
                    "alpha": 0.0,
                    "r_squared": 0.0
                }
            
            try:
                sortino_ratio = self.calculate_sortino_ratio()
            except Exception as e:
                logger.warning(f"[PortfolioCalculator] Error calculating Sortino ratio: {e}", exc_info=True)
                sortino_ratio = 0.0

            def safe_value(value, default=0.0):
                if pd.isna(value) or (isinstance(value, float) and (value != value)):  # Check for NaN
                    return default
                try:
                    return float(value)
                except (ValueError, TypeError, OverflowError):
                    return default

            # Get correlation matrix safely
            corr_matrix = self.calculate_correlation_matrix()
            corr_dict = {}
            if not corr_matrix.empty:
                # Convert numpy types to Python types for JSON serialization
                for col in corr_matrix.columns:
                    corr_dict[col] = {}
                    for idx in corr_matrix.index:
                        value = corr_matrix.loc[idx, col]
                        corr_dict[col][idx] = safe_value(value)

            return {
                "volatility": safe_value(performance.get("volatility", 0.0)),
                "max_drawdown": safe_value(performance.get("max_drawdown", 0.0)),
                "sharpe_ratio": safe_value(performance.get("sharpe_ratio", 0.0)),
                "sortino_ratio": safe_value(sortino_ratio),
                "value_at_risk": {
                    "var_95": safe_value(var_metrics.get("var_95", 0.0)),
                    "var_99": safe_value(var_metrics.get("var_99", 0.0)),
                    "expected_shortfall": safe_value(var_metrics.get("expected_shortfall", 0.0))
                },
                "beta_analysis": {
                    "beta": safe_value(beta_metrics.get("beta", 0.0)),
                    "alpha": safe_value(beta_metrics.get("alpha", 0.0)),
                    "r_squared": safe_value(beta_metrics.get("r_squared", 0.0))
                },
                "correlation_matrix": corr_dict
            }

        except Exception as e:
            print(f"Error getting risk assessment: {e}")
            return {
                "volatility": 0.0,
                "max_drawdown": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "value_at_risk": {"var_95": 0.0, "var_99": 0.0, "expected_shortfall": 0.0},
                "beta_analysis": {"beta": 0.0, "alpha": 0.0, "r_squared": 0.0},
                "correlation_matrix": {}
            }

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive portfolio summary
        """
        # Preload price cache for efficiency (if not already loaded)
        if not self._price_cache_loaded:
            self._preload_price_cache()
        
        holdings = self.get_current_holdings()
        total_return_data = self.calculate_total_return()

        # Count transactions
        transaction_count = self.db.query(Transaction).count()

        # Get unique tickers
        unique_tickers = len(set(
            tx.ticker for tx in self.db.query(Transaction.ticker).filter(Transaction.ticker.isnot(None)).all()
        ))

        return {
            "has_data": transaction_count > 0,
            "transaction_count": transaction_count,
            "unique_tickers": unique_tickers,
            "current_holdings_count": len(holdings),
            "holdings": holdings,
            "performance": total_return_data
        }

    def calculate_portfolio_history(self, start_date: Optional[datetime] = None,
                                  end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Calculate portfolio value history over time
        Returns dict with history list containing data points with date and portfolio value
        """
        try:
            # Preload price cache for efficiency (if not already loaded)
            if not self._price_cache_loaded:
                self._preload_price_cache()
            
            # Get all transactions within date range
            query = self.db.query(Transaction).filter(Transaction.ticker.isnot(None))

            if start_date:
                query = query.filter(Transaction.activity_date >= start_date)
            if end_date:
                query = query.filter(Transaction.activity_date <= end_date)

            transactions = query.order_by(Transaction.activity_date).all()

            if not transactions:
                return {"history": []}

            # Calculate portfolio value at each transaction date
            portfolio_history = []
            holdings = {}

            for tx in transactions:
                ticker = tx.ticker
                trans_code = tx.trans_code
                quantity = tx.quantity or 0

                # Update holdings
                if ticker not in holdings:
                    holdings[ticker] = 0

                if trans_code == 'Buy':
                    holdings[ticker] += quantity
                elif trans_code == 'Sell':
                    holdings[ticker] -= quantity

                # Calculate portfolio value at this point
                total_value = 0
                for h_ticker, h_quantity in holdings.items():
                    if h_quantity > 0:
                        price_data = stock_price_service.get_price_at_date(h_ticker, tx.activity_date.strftime('%Y-%m-%d'))
                        if price_data and 'close' in price_data:
                            total_value += price_data['close'] * h_quantity

                portfolio_history.append({
                    'date': tx.activity_date.strftime('%Y-%m-%d'),
                    'portfolio_value': total_value,
                    'transactions': len([t for t in transactions if t.activity_date <= tx.activity_date])
                })

            return {"history": portfolio_history}

        except Exception as e:
            print(f"Error calculating portfolio history: {e}")
            return {"history": []}

    def get_optimization_recommendations(self) -> Dict[str, Any]:
        """
        Get portfolio optimization recommendations
        """
        try:
            holdings = self.get_current_holdings()
            if not holdings:
                return {'recommendations': []}

            recommendations = []
            total_value = 0

            # Calculate current allocation
            for ticker, quantity in holdings.items():
                if quantity > 0:
                    price = stock_price_service.get_historical_price(ticker, datetime.now().strftime('%Y-%m-%d'))
                    if price:
                        value = price * quantity
                        total_value += value

                        # Simple rebalancing recommendation (target 20% max per holding)
                        target_allocation = min(0.20, 1.0 / max(1, len([t for t, q in holdings.items() if q > 0])))
                        current_allocation = value / total_value if total_value > 0 else 0

                        if current_allocation > target_allocation * 1.2:  # 20% over target
                            recommendations.append({
                                'ticker': ticker,
                                'action': 'reduce',
                                'current_allocation': current_allocation,
                                'target_allocation': target_allocation,
                                'suggested_change': target_allocation - current_allocation
                            })

            return {
                'total_value': total_value,
                'recommendations': recommendations,
                'optimization_score': len(recommendations) == 0  # True if no recommendations needed
            }

        except Exception as e:
            print(f"Error getting optimization recommendations: {e}")
            return {'recommendations': [], 'error': str(e)}

    def get_rebalancing_analysis(self, target_allocations: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """
        Analyze portfolio rebalancing needs
        """
        try:
            holdings = self.get_current_holdings()
            if not holdings:
                return {'analysis': {}, 'needs_rebalancing': False}

            total_value = 0
            current_allocations = {}

            # Calculate current allocations
            for ticker, quantity in holdings.items():
                if quantity > 0:
                    price = stock_price_service.get_historical_price(ticker, datetime.now().strftime('%Y-%m-%d'))
                    if price:
                        value = price * quantity
                        total_value += value
                        current_allocations[ticker] = value

            # Normalize to percentages
            for ticker in current_allocations:
                current_allocations[ticker] /= total_value

            # Use provided target allocations or create equal weight targets
            if not target_allocations:
                tickers_with_holdings = [t for t, q in holdings.items() if q > 0]
                equal_weight = 1.0 / len(tickers_with_holdings) if tickers_with_holdings else 0
                target_allocations = {t: equal_weight for t in tickers_with_holdings}

            # Calculate rebalancing trades
            trades = []
            needs_rebalancing = False

            for ticker, target_alloc in target_allocations.items():
                current_alloc = current_allocations.get(ticker, 0)
                deviation = abs(current_alloc - target_alloc)

                if deviation > 0.05:  # 5% deviation threshold
                    needs_rebalancing = True

                    # Calculate trade needed
                    target_value = target_alloc * total_value
                    current_value = current_alloc * total_value
                    trade_value = target_value - current_value

                    if ticker in holdings and holdings[ticker] > 0:
                        price = stock_price_service.get_historical_price(ticker, datetime.now().strftime('%Y-%m-%d'))
                        if price:
                            trade_quantity = trade_value / price
                            trades.append({
                                'ticker': ticker,
                                'action': 'buy' if trade_quantity > 0 else 'sell',
                                'quantity': abs(trade_quantity),
                                'value': abs(trade_value),
                                'current_allocation': current_alloc,
                                'target_allocation': target_alloc
                            })

            return {
                'current_allocations': current_allocations,
                'target_allocations': target_allocations,
                'needs_rebalancing': needs_rebalancing,
                'trades': trades,
                'total_value': total_value,
                'rebalancing_cost_estimate': sum(t['value'] for t in trades) * 0.001  # Rough commission estimate
            }

        except Exception as e:
            print(f"Error in rebalancing analysis: {e}")
            return {'analysis': {}, 'needs_rebalancing': False, 'error': str(e)}

    def get_performance_attribution(self) -> Dict[str, Any]:
        """
        Calculate contribution of each asset to total portfolio return.
        
        Returns:
            Dict with attribution by asset and by period
        """
        try:
            holdings = self.get_current_holdings()
            if not holdings:
                return {"by_asset": {}, "by_period": {}, "total_return": 0}
            
            # Get date range
            first_tx = self.db.query(Transaction).order_by(Transaction.activity_date).first()
            last_tx = self.db.query(Transaction).order_by(Transaction.activity_date.desc()).first()
            
            if not first_tx or not last_tx:
                return {"by_asset": {}, "by_period": {}, "total_return": 0}
            
            start_date = first_tx.activity_date
            end_date = last_tx.activity_date
            
            if isinstance(start_date, (datetime, date)):
                start_date = start_date.strftime('%Y-%m-%d')
            if isinstance(end_date, (datetime, date)):
                end_date = end_date.strftime('%Y-%m-%d')
            
            # Get weights and calculate individual returns
            weights = self.calculate_position_weights()
            by_asset = {}
            total_portfolio_return = 0
            
            for ticker, weight in weights.items():
                try:
                    # Get price at start and end
                    start_price_data = stock_price_service.get_price_at_date(ticker, start_date)
                    end_price_data = stock_price_service.get_price_at_date(ticker, end_date)
                    
                    if start_price_data and end_price_data:
                        start_price = start_price_data.get('close', 0)
                        end_price = end_price_data.get('close', 0)
                        
                        if start_price > 0:
                            asset_return = ((end_price - start_price) / start_price) * 100
                            contribution = (weight / 100) * asset_return
                            
                            # Safe rounding to handle NaN values
                            import math
                            def safe_round_attr(value, decimals=2):
                                if math.isnan(value) or math.isinf(value):
                                    return 0.0
                                return round(float(value), decimals)

                            by_asset[ticker] = {
                                "contribution": safe_round_attr(contribution, 2),
                                "weight": safe_round_attr(weight, 2),
                                "return": safe_round_attr(asset_return, 2)
                            }
                            total_portfolio_return += contribution
                except Exception as e:
                    print(f"Error calculating attribution for {ticker}: {e}")
                    continue
            
            # Calculate quarterly attribution
            by_period = {}
            try:
                # Handle datetime objects with time components
                if isinstance(start_date, str):
                    start_dt = datetime.strptime(start_date.split(' ')[0], '%Y-%m-%d')
                elif hasattr(start_date, 'date'):
                    start_dt = start_date.date()
                start_dt = datetime.combine(start_dt, datetime.min.time())

                if isinstance(end_date, str):
                    end_dt = datetime.strptime(end_date.split(' ')[0], '%Y-%m-%d')
                elif hasattr(end_date, 'date'):
                    end_dt = end_date.date()
                end_dt = datetime.combine(end_dt, datetime.min.time())
                
                current = start_dt
                while current < end_dt:
                    quarter_end = min(current + timedelta(days=90), end_dt)
                    quarter_key = f"{current.year}-Q{(current.month - 1) // 3 + 1}"
                    
                    quarter_start_str = current.strftime('%Y-%m-%d')
                    quarter_end_str = quarter_end.strftime('%Y-%m-%d')
                    
                    # Calculate quarter return
                    q_start_value = self.get_portfolio_value_at_date(quarter_start_str, holdings)
                    q_end_value = self.get_portfolio_value_at_date(quarter_end_str, holdings)
                    
                    if q_start_value > 0:
                        quarter_return = ((q_end_value - q_start_value) / q_start_value) * 100
                        
                        # Find top contributor for this quarter
                        top_contributor = None
                        top_contribution = 0
                        
                        for ticker in holdings.keys():
                            try:
                                q_start_price = stock_price_service.get_price_at_date(ticker, quarter_start_str)
                                q_end_price = stock_price_service.get_price_at_date(ticker, quarter_end_str)
                                
                                if q_start_price and q_end_price:
                                    ticker_return = ((q_end_price.get('close', 0) - q_start_price.get('close', 0)) / q_start_price.get('close', 1)) * 100
                                    ticker_weight = weights.get(ticker, 0) / 100
                                    ticker_contribution = ticker_return * ticker_weight
                                    
                                    if ticker_contribution > top_contribution:
                                        top_contribution = ticker_contribution
                                        top_contributor = ticker
                            except Exception:
                                continue
                        
                        by_period[quarter_key] = {
                            "return": round(quarter_return, 2),
                            "top_contributor": top_contributor or "N/A"
                        }
                    
                    current = quarter_end + timedelta(days=1)
            except Exception as e:
                print(f"Error calculating quarterly attribution: {e}")
            
            return {
                "by_asset": by_asset,
                "by_period": by_period,
                "total_return": round(total_portfolio_return, 2)
            }
            
        except Exception as e:
            print(f"Error in performance attribution: {e}")
            return {"by_asset": {}, "by_period": {}, "total_return": 0}

    def get_drawdown_analysis(self) -> Dict[str, Any]:
        """
        Calculate actual drawdown metrics from portfolio history.
        
        Returns:
            Dict with drawdown series, max drawdown, and recovery analysis
        """
        try:
            value_history = self.get_portfolio_value_history()
            
            if value_history.empty or len(value_history) < 2:
                return {
                    "drawdown_series": [],
                    "max_drawdown": 0,
                    "max_drawdown_date": None,
                    "recovery_time_days": None,
                    "drawdown_periods": []
                }
            
            # Ensure date column is datetime
            if not pd.api.types.is_datetime64_any_dtype(value_history['date']):
                value_history['date'] = pd.to_datetime(value_history['date'])
            
            value_history = value_history.sort_values('date')
            
            # Calculate running maximum (peak)
            values = value_history['portfolio_value'].values
            dates = value_history['date'].values
            
            running_max = np.maximum.accumulate(values)
            drawdowns = (values - running_max) / running_max * 100
            
            # Build drawdown series
            drawdown_series = []
            for i, (d, dd) in enumerate(zip(dates, drawdowns)):
                date_str = pd.Timestamp(d).strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d)[:10]
                drawdown_series.append({
                    "date": date_str,
                    "drawdown": round(float(dd), 2)
                })
            
            # Find max drawdown
            max_dd_idx = np.argmin(drawdowns)
            max_drawdown = float(drawdowns[max_dd_idx])
            max_drawdown_date = pd.Timestamp(dates[max_dd_idx]).strftime('%Y-%m-%d') if max_dd_idx < len(dates) else None
            
            # Identify drawdown periods (start, bottom, recovery)
            drawdown_periods = []
            in_drawdown = False
            period_start = None
            period_bottom = None
            period_bottom_value = 0
            
            for i in range(len(drawdowns)):
                if drawdowns[i] < -1 and not in_drawdown:  # Start of drawdown (>1% decline)
                    in_drawdown = True
                    period_start = pd.Timestamp(dates[i]).strftime('%Y-%m-%d')
                    period_bottom = period_start
                    period_bottom_value = drawdowns[i]
                elif in_drawdown:
                    if drawdowns[i] < period_bottom_value:
                        period_bottom = pd.Timestamp(dates[i]).strftime('%Y-%m-%d')
                        period_bottom_value = drawdowns[i]
                    
                    if drawdowns[i] >= -0.5:  # Recovery (within 0.5% of peak)
                        in_drawdown = False
                        recovery_date = pd.Timestamp(dates[i]).strftime('%Y-%m-%d')
                        
                        drawdown_periods.append({
                            "start": period_start,
                            "bottom": period_bottom,
                            "end": recovery_date,
                            "depth": round(period_bottom_value, 2)
                        })
            
            # If still in drawdown at end
            if in_drawdown and period_start:
                drawdown_periods.append({
                    "start": period_start,
                    "bottom": period_bottom,
                    "end": None,
                    "depth": round(period_bottom_value, 2)
                })
            
            # Calculate recovery time for max drawdown
            recovery_time_days = None
            if max_dd_idx < len(dates) - 1:
                for i in range(max_dd_idx + 1, len(drawdowns)):
                    if drawdowns[i] >= -0.5:
                        recovery_date = pd.Timestamp(dates[i])
                        max_dd_date = pd.Timestamp(dates[max_dd_idx])
                        recovery_time_days = (recovery_date - max_dd_date).days
                        break
            
            return {
                "drawdown_series": drawdown_series,
                "max_drawdown": round(max_drawdown, 2),
                "max_drawdown_date": max_drawdown_date,
                "recovery_time_days": recovery_time_days,
                "drawdown_periods": drawdown_periods[:10]  # Limit to 10 most recent
            }
            
        except Exception as e:
            print(f"Error in drawdown analysis: {e}")
            import traceback
            traceback.print_exc()
            return {
                "drawdown_series": [],
                "max_drawdown": 0,
                "max_drawdown_date": None,
                "recovery_time_days": None,
                "drawdown_periods": []
            }

    def _calculate_drawdown_recovery_metrics(self, drawdown: pd.Series, value_history: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate detailed drawdown recovery metrics like Portfolio Visualizer
        """
        try:
            # Find the maximum drawdown
            max_drawdown_value = drawdown.min()
            max_drawdown_idx = drawdown.idxmin()

            # Calculate recovery time
            recovery_time = None
            underwater_period = None

            if max_drawdown_value < 0:  # Only calculate if there was a drawdown
                # Find when portfolio recovered to within 0.5% of previous peak
                peak_before_drawdown = drawdown[:max_drawdown_idx].max()

                # Find recovery point
                recovery_mask = (drawdown[max_drawdown_idx:] >= peak_before_drawdown - 0.005)
                if recovery_mask.any():
                    recovery_idx = recovery_mask.idxmax()
                    recovery_time = (recovery_idx - max_drawdown_idx).days
                    underwater_period = recovery_time

            return {
                "recovery_time": recovery_time,
                "underwater_period": underwater_period,
                "worst_drawdown": {
                    "depth": max_drawdown_value * 100,
                    "date": max_drawdown_idx.strftime('%Y-%m-%d') if max_drawdown_idx else None
                }
            }

        except Exception as e:
            print(f"Error calculating drawdown recovery metrics: {e}")
            return {
                "recovery_time": None,
                "underwater_period": None,
                "worst_drawdown": {"depth": 0, "date": None}
            }

    def _calculate_rolling_returns(self, value_history: pd.DataFrame, periods: List[int] = [1, 3, 5, 7, 10]) -> Dict[str, Dict[str, float]]:
        """
        Calculate rolling returns for different periods like Portfolio Visualizer
        """
        try:
            if value_history.empty or len(value_history) < 2:
                return {f"{period}y": {"average": 0.0, "high": 0.0, "low": 0.0} for period in periods}

            # Ensure we have datetime index
            if not isinstance(value_history.index, pd.DatetimeIndex):
                value_history.index = pd.to_datetime(value_history.index)

            # Calculate daily returns
            daily_returns = value_history['portfolio_value'].pct_change().dropna()

            rolling_returns = {}

            for period in periods:
                # Convert years to trading days (252 trading days per year)
                trading_days = period * 252

                if len(daily_returns) < trading_days:
                    rolling_returns[f"{period}y"] = {"average": 0.0, "high": 0.0, "low": 0.0}
                    continue

                # Calculate rolling cumulative returns
                rolling_cumulative = (1 + daily_returns).rolling(window=trading_days).apply(lambda x: x.prod() - 1)

                # Convert to annualized returns
                annualized_returns = (rolling_cumulative + 1) ** (252 / trading_days) - 1

                # Calculate statistics
                avg_return = annualized_returns.mean() * 100
                high_return = annualized_returns.max() * 100
                low_return = annualized_returns.min() * 100

                rolling_returns[f"{period}y"] = {
                    "average": round(avg_return, 2) if not pd.isna(avg_return) else 0.0,
                    "high": round(high_return, 2) if not pd.isna(high_return) else 0.0,
                    "low": round(low_return, 2) if not pd.isna(low_return) else 0.0
                }

            return rolling_returns

        except Exception as e:
            print(f"Error calculating rolling returns: {e}")
            return {f"{period}y": {"average": 0.0, "high": 0.0, "low": 0.0} for period in periods}

    def _calculate_individual_asset_metrics(self) -> Dict[str, Any]:
        """
        Calculate individual asset performance metrics like Portfolio Visualizer
        """
        try:
            holdings = self.get_current_holdings()
            if not holdings:
                return {}

            asset_metrics = {}

            for ticker in holdings.keys():
                try:
                    # Get asset price history
                    price_history = self._get_asset_price_history(ticker)
                    if price_history.empty:
                        continue

                    # Calculate returns
                    price_history = price_history.sort_values('date')
                    price_history['returns'] = price_history['close'].pct_change()

                    # Basic metrics
                    start_price = price_history['close'].iloc[0]
                    end_price = price_history['close'].iloc[-1]
                    total_return = ((end_price / start_price) - 1) * 100 if start_price > 0 else 0

                    # CAGR
                    days = (price_history['date'].max() - price_history['date'].min()).days
                    years = days / 365.25
                    cagr = ((end_price / start_price) ** (1 / years) - 1) * 100 if start_price > 0 and years > 0 else 0

                    # Volatility
                    daily_volatility = price_history['returns'].std()
                    volatility = daily_volatility * np.sqrt(252) * 100

                    # Sharpe ratio (assuming 2% risk-free rate)
                    risk_free_rate = 0.02
                    excess_returns = price_history['returns'] - risk_free_rate / 252
                    sharpe_ratio = excess_returns.mean() / excess_returns.std() * np.sqrt(252) if excess_returns.std() > 0 else 0

                    # Best and worst years
                    price_history['year'] = price_history['date'].dt.year
                    yearly_returns = price_history.groupby('year')['returns'].apply(lambda x: (1 + x).prod() - 1)
                    best_year = yearly_returns.max() * 100 if not yearly_returns.empty else 0
                    worst_year = yearly_returns.min() * 100 if not yearly_returns.empty else 0

                    # Max drawdown for asset
                    cumulative = (1 + price_history['returns']).cumprod()
                    running_max = cumulative.expanding().max()
                    drawdown = (cumulative - running_max) / running_max
                    max_drawdown = drawdown.min() * 100

                    # Handle NaN values properly
                    import math
                    def safe_round(value, decimals=2):
                        if math.isnan(value) or math.isinf(value):
                            return 0.0
                        return round(float(value), decimals)

                    asset_metrics[ticker] = {
                        "cagr": safe_round(cagr, 2),
                        "stdev": safe_round(volatility, 2),
                        "best_year": safe_round(best_year, 2),
                        "worst_year": safe_round(worst_year, 2),
                        "max_drawdown": safe_round(max_drawdown, 2),
                        "sharpe_ratio": safe_round(sharpe_ratio, 2),
                        "total_return": safe_round(total_return, 2),
                        "current_holding": holdings[ticker]
                    }

                except Exception as e:
                    print(f"Error calculating metrics for {ticker}: {e}")
                    continue

            return asset_metrics

        except Exception as e:
            print(f"Error calculating individual asset metrics: {e}")
            return {}

    def _get_asset_price_history(self, ticker: str) -> pd.DataFrame:
        """
        Get price history for a specific asset
        """
        try:
            # Query stock prices for this ticker
            prices = self.db.query(StockPrice).filter(
                StockPrice.ticker == ticker.upper()
            ).order_by(StockPrice.date).all()

            if not prices:
                return pd.DataFrame()

            data = [{
                'date': price.date,
                'close': price.close,
                'high': price.high,
                'low': price.low,
                'open': price.open,
                'volume': price.volume
            } for price in prices]

            return pd.DataFrame(data)

        except Exception as e:
            print(f"Error getting price history for {ticker}: {e}")
            return pd.DataFrame()

    def get_monthly_performance_table(self) -> Dict[str, Any]:
        """
        Generate monthly performance table like Portfolio Visualizer
        Returns data structure with monthly returns, balances, and individual asset performance
        """
        try:
            value_history = self.get_portfolio_value_history()

            if value_history.empty:
                return {"monthly_data": [], "summary_stats": {}, "asset_columns": []}

            # Convert to datetime and set as index
            value_history['date'] = pd.to_datetime(value_history['date'])
            value_history = value_history.set_index('date').sort_index()

            # Calculate daily returns
            value_history['returns'] = value_history['portfolio_value'].pct_change()

            # Resample to monthly data
            monthly_value = value_history['portfolio_value'].resample('M').last()
            monthly_returns = value_history['returns'].resample('M').apply(lambda x: (1 + x).prod() - 1)

            # Get holdings for asset-level returns
            holdings = self.get_current_holdings()
            asset_columns = list(holdings.keys())[:5]  # Limit to top 5 holdings for display

            # Create monthly data array similar to Portfolio Visualizer
            monthly_data = []
            years = sorted(monthly_value.index.year.unique())

            for year in years:
                year_mask = monthly_value.index.year == year
                year_values = monthly_value[year_mask]
                year_returns = monthly_returns[year_mask]

                for month in range(1, 13):
                    month_mask = year_values.index.month == month
                    if month_mask.any():
                        month_value = year_values[month_mask].iloc[0]
                        month_return = year_returns[month_mask].iloc[0]

                        row_data = {
                            "year": year,
                            "month": month,
                            "return": round(month_return * 100, 2),
                            "balance": round(month_value, 2)
                        }

                        # Add individual asset returns for this month
                        for ticker in asset_columns:
                            try:
                                asset_return = self._get_asset_monthly_return(ticker, year, month)
                                row_data[ticker] = round(asset_return * 100, 2) if asset_return is not None else None
                            except:
                                row_data[ticker] = None

                        monthly_data.append(row_data)

            # Calculate summary statistics
            all_returns = monthly_returns.dropna()
            summary_stats = {
                "total_months": len(all_returns),
                "positive_months": (all_returns > 0).sum(),
                "negative_months": (all_returns < 0).sum(),
                "best_month": all_returns.max() * 100,
                "worst_month": all_returns.min() * 100,
                "average_month": all_returns.mean() * 100,
                "median_month": all_returns.median() * 100,
                "monthly_volatility": all_returns.std() * 100,
                "win_rate": (all_returns > 0).mean() * 100
            }

            return {
                "monthly_data": monthly_data,
                "summary_stats": summary_stats,
                "asset_columns": asset_columns,
                "years_covered": years.tolist()
            }

        except Exception as e:
            print(f"Error calculating monthly performance table: {e}")
            return {"monthly_data": [], "summary_stats": {}, "asset_columns": []}

    def _get_asset_monthly_return(self, ticker: str, year: int, month: int) -> Optional[float]:
        """
        Get monthly return for a specific asset and month
        """
        try:
            # Get asset price data for the month
            start_date = f"{year}-{month:02d}-01"
            end_date = f"{year}-{month+1:02d}-01" if month < 12 else f"{year+1}-01-01"

            # Query prices for this date range
            prices = self.db.query(StockPrice).filter(
                StockPrice.symbol == ticker.upper(),
                StockPrice.date >= start_date,
                StockPrice.date < end_date
            ).order_by(StockPrice.date).all()

            if len(prices) < 2:
                return None

            # Calculate monthly return
            start_price = prices[0].close
            end_price = prices[-1].close

            if start_price > 0:
                return (end_price / start_price) - 1

            return None

        except Exception as e:
            return None