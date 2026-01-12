"""
Stock price service for accessing historical price data from stockr_backbone database
"""

import os
import sqlite3
from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime, date
from pathlib import Path
import pandas as pd


class StockPriceService:
    """Service for retrieving stock price data from stockr_backbone database"""

    def __init__(self, stockr_db_path: Optional[str] = None):
        """
        Initialize the stock price service

        Args:
            stockr_db_path: Path to stockr_backbone database. If None, uses default path.
        """
        if stockr_db_path is None:
            # Default path relative to project root
            project_root = Path(__file__).parent.parent.parent
            stockr_db_path = project_root / "stockr_backbone" / "stock_data.db"

        self.db_path = Path(stockr_db_path)
        self._connection = None

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection"""
        if self._connection is None:
            if not self.db_path.exists():
                raise FileNotFoundError(f"Stockr database not found at {self.db_path}")
            self._connection = sqlite3.connect(str(self.db_path))
        return self._connection

    def _execute_query(self, query: str, params: Tuple = ()) -> List[Tuple]:
        """Execute a database query and return results"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()
        except Exception as e:
            print(f"Database query error: {e}")
            return []

    def get_stock_id(self, symbol: str) -> Optional[int]:
        """Get stock ID for a given symbol"""
        result = self._execute_query(
            "SELECT id FROM stocks WHERE symbol = ? AND ephemeral = 0",
            (symbol.upper(),)
        )
        return result[0][0] if result else None

    def get_price_at_date(self, symbol: str, target_date: str) -> Optional[Dict[str, float]]:
        """
        Get stock price data for a specific date
        
        If the stock is not found, it will be automatically added to tracking
        via the stockr_backbone maintenance system.

        Args:
            symbol: Stock ticker symbol (e.g., 'AAPL')
            target_date: Date in YYYY-MM-DD format

        Returns:
            Dict with price data or None if not found
        """
        try:
            stock_id = self.get_stock_id(symbol)
            if not stock_id:
                # Automatically add stock to tracking via stockr_backbone
                # This is a CORE ARCHITECTURAL FEATURE - new stocks are automatically tracked
                print(f"Ticker {symbol} not found in database, adding to stockr_backbone tracking...")
                try:
                    # Import the standalone fetcher (no Celery dependency)
                    import sys
                    from pathlib import Path
                    project_root = Path(__file__).parent.parent.parent
                    stockr_path = project_root / "stockr_backbone"
                    
                    # Add stockr_backbone to path if needed
                    if str(stockr_path) not in sys.path:
                        sys.path.insert(0, str(stockr_path))
                    
                    # Import from stockr_backbone/src/fetcher_standalone
                    import importlib.util
                    fetcher_path = stockr_path / "src" / "fetcher_standalone.py"
                    if fetcher_path.exists():
                        spec = importlib.util.spec_from_file_location("fetcher_standalone", fetcher_path)
                        fetcher_module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(fetcher_module)
                        ensure_stock_tracked = fetcher_module.ensure_stock_tracked
                        
                        # Add stock to tracking and fetch initial data
                        success = ensure_stock_tracked(symbol)
                    else:
                        success = False
                    if success:
                        print(f"Successfully added {symbol} to stockr_backbone tracking")
                        # Try again to get the stock_id
                        stock_id = self.get_stock_id(symbol)
                    else:
                        print(f"Failed to add {symbol} to tracking")
                        return None
                except Exception as e:
                    print(f"Error adding {symbol} to stockr_backbone tracking: {e}")
                    import traceback
                    traceback.print_exc()
                    return None

            if not stock_id:
                return None

            # Try exact date match first
            result = self._execute_query(
                """SELECT date, open, high, low, close, volume
                   FROM historical_prices
                   WHERE stock_id = ? AND date = ?
                   ORDER BY date DESC LIMIT 1""",
                (stock_id, target_date)
            )

            if result:
                date_val, open_price, high, low, close, volume = result[0]
                return {
                    'date': date_val,
                    'open': open_price,
                    'high': high,
                    'low': low,
                    'close': close,
                    'volume': volume
                }

            # If no exact match, find the most recent price before the target date
            result = self._execute_query(
                """SELECT date, open, high, low, close, volume
                   FROM historical_prices
                   WHERE stock_id = ? AND date <= ?
                   ORDER BY date DESC LIMIT 1""",
                (stock_id, target_date)
            )

            if result:
                date_val, open_price, high, low, close, volume = result[0]
                return {
                    'date': date_val,
                    'open': open_price,
                    'high': high,
                    'low': low,
                    'close': close,
                    'volume': volume
                }

            return None

        except Exception as e:
            print(f"Error getting price for {symbol} on {target_date}: {e}")
            return None

    def get_price_history(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Get historical price data for a date range

        Args:
            symbol: Stock ticker symbol
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            DataFrame with price history
        """
        try:
            stock_id = self.get_stock_id(symbol)
            if not stock_id:
                return pd.DataFrame()

            query = """
                SELECT date, open, high, low, close, volume
                FROM historical_prices
                WHERE stock_id = ? AND date BETWEEN ? AND ?
                ORDER BY date ASC
            """

            results = self._execute_query(query, (stock_id, start_date, end_date))

            if not results:
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame(results, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')

            return df

        except Exception as e:
            print(f"Error getting price history for {symbol}: {e}")
            return pd.DataFrame()

    def get_latest_price(self, symbol: str) -> Optional[Dict[str, float]]:
        """Get the most recent price for a stock"""
        try:
            stock_id = self.get_stock_id(symbol)
            if not stock_id:
                return None

            result = self._execute_query(
                """SELECT date, open, high, low, close, volume
                   FROM historical_prices
                   WHERE stock_id = ?
                   ORDER BY date DESC LIMIT 1""",
                (stock_id,)
            )

            if result:
                date_val, open_price, high, low, close, volume = result[0]
                return {
                    'date': date_val,
                    'open': open_price,
                    'high': high,
                    'low': low,
                    'close': close,
                    'volume': volume
                }

            return None

        except Exception as e:
            print(f"Error getting latest price for {symbol}: {e}")
            return None

    def get_available_stocks(self) -> List[Dict[str, str]]:
        """Get list of available stocks in the database"""
        try:
            results = self._execute_query(
                "SELECT symbol, name FROM stocks WHERE ephemeral = 0 ORDER BY symbol"
            )

            return [
                {'symbol': row[0], 'name': row[1] or row[0]}
                for row in results
            ]

        except Exception as e:
            print(f"Error getting available stocks: {e}")
            return []

    def get_prices_batch(self, tickers: List[str], start_date: str, end_date: str) -> Dict[str, pd.DataFrame]:
        """
        Fetch all prices for multiple tickers in one efficient query batch.
        Returns dict of ticker -> DataFrame with price history.
        
        This is much faster than individual get_price_at_date calls.
        """
        if not tickers:
            return {}
        
        try:
            # Get stock IDs for all tickers in one query
            placeholders = ','.join('?' * len(tickers))
            ticker_upper = [t.upper() for t in tickers]
            
            id_results = self._execute_query(
                f"SELECT id, symbol FROM stocks WHERE symbol IN ({placeholders}) AND ephemeral = 0",
                tuple(ticker_upper)
            )
            
            if not id_results:
                return {}
            
            stock_id_map = {row[1]: row[0] for row in id_results}
            stock_ids = list(stock_id_map.values())
            
            if not stock_ids:
                return {}
            
            # Get all prices for all stocks in date range in one query
            id_placeholders = ','.join('?' * len(stock_ids))
            price_results = self._execute_query(
                f"""SELECT s.symbol, hp.date, hp.open, hp.high, hp.low, hp.close, hp.volume
                    FROM historical_prices hp
                    JOIN stocks s ON hp.stock_id = s.id
                    WHERE hp.stock_id IN ({id_placeholders}) 
                    AND hp.date BETWEEN ? AND ?
                    ORDER BY s.symbol, hp.date ASC""",
                tuple(stock_ids) + (start_date, end_date)
            )
            
            if not price_results:
                return {}
            
            # Group results by ticker
            ticker_data: Dict[str, List] = {}
            for row in price_results:
                symbol = row[0]
                if symbol not in ticker_data:
                    ticker_data[symbol] = []
                ticker_data[symbol].append({
                    'date': row[1],
                    'open': row[2],
                    'high': row[3],
                    'low': row[4],
                    'close': row[5],
                    'volume': row[6]
                })
            
            # Convert to DataFrames
            result = {}
            for ticker, data in ticker_data.items():
                df = pd.DataFrame(data)
                df['date'] = pd.to_datetime(df['date'])
                df = df.set_index('date').sort_index()
                result[ticker] = df
            
            return result
            
        except Exception as e:
            print(f"Error in batch price fetch: {e}")
            return {}

    def get_prices_at_dates_batch(self, tickers: List[str], dates: List[str]) -> Dict[str, Dict[str, float]]:
        """
        Get closing prices for multiple tickers at multiple dates efficiently.
        Returns dict of ticker -> {date: close_price}
        
        Uses a single query to fetch all needed data.
        """
        if not tickers or not dates:
            return {}
        
        try:
            # Get min/max dates for range query
            min_date = min(dates)
            max_date = max(dates)
            
            # Fetch all price data in the range
            batch_data = self.get_prices_batch(tickers, min_date, max_date)
            
            if not batch_data:
                return {}
            
            # Build result with prices at specific dates (or nearest prior)
            result: Dict[str, Dict[str, float]] = {}
            
            for ticker, df in batch_data.items():
                result[ticker] = {}
                for date_str in dates:
                    try:
                        target_date = pd.to_datetime(date_str)
                        # Get exact match or most recent price before target
                        available = df[df.index <= target_date]
                        if not available.empty:
                            result[ticker][date_str] = float(available.iloc[-1]['close'])
                    except Exception:
                        continue
            
            return result
            
        except Exception as e:
            print(f"Error in batch date price fetch: {e}")
            return {}

    def validate_database(self) -> Dict[str, any]:
        """Validate that the stockr database is accessible and has data"""
        try:
            # Check if database file exists
            if not self.db_path.exists():
                return {
                    'valid': False,
                    'error': f'Database file not found at {self.db_path}',
                    'stock_count': 0,
                    'price_records': 0
                }

            # Check stocks table
            stock_count = len(self._execute_query("SELECT COUNT(*) FROM stocks WHERE ephemeral = 0"))

            # Check price records
            price_count = len(self._execute_query("SELECT COUNT(*) FROM historical_prices"))

            return {
                'valid': True,
                'stock_count': stock_count,
                'price_records': price_count,
                'database_path': str(self.db_path)
            }

        except Exception as e:
            return {
                'valid': False,
                'error': str(e),
                'stock_count': 0,
                'price_records': 0
            }

    def close(self):
        """Close database connection"""
        if self._connection:
            self._connection.close()
            self._connection = None


# Global instance for easy access
stock_price_service = StockPriceService()
