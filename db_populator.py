import sqlite3
import yfinance as yf
from typing import List
from datetime import datetime
import pandas as pd

def fetch_historical_prices(tickers: List[str], start_date: str = '2024-01-01', end_date: str = datetime.now().strftime('%Y-%m-%d')) -> pd.DataFrame:
      all_data = []
      for ticker in tickers:
          try:
              df = yf.download(ticker, start=start_date, end=end_date, progress=False)
              if df.empty:
                  print(f"No data for {ticker}")
                  continue
              
              # Flatten multi-index columns if present
              if isinstance(df.columns, pd.MultiIndex):
                  df.columns = df.columns.get_level_values(0)
              
              # Reset index to make Date a column
              df = df.reset_index()
              
              # Add symbol column
              df['symbol'] = ticker
              
              # Rename Date column to date if it exists
              if 'Date' in df.columns:
                  df = df.rename(columns={'Date': 'date'})
              elif df.index.name == 'Date' or 'Date' not in df.columns:
                  df['date'] = df.index.strftime('%Y-%m-%d') if hasattr(df.index, 'strftime') else pd.to_datetime(df.index).strftime('%Y-%m-%d')
              
              # Normalize column names to lowercase
              df.columns = df.columns.str.lower()
              
              # Select and reorder columns
              required_cols = ['date', 'symbol', 'open', 'high', 'low', 'close', 'volume']
              available_cols = [col for col in required_cols if col in df.columns]
              df = df[available_cols]
              
              all_data.append(df)
          except Exception as e:
              print(f"Error fetching {ticker}: {e}")
      
      if not all_data:
          return pd.DataFrame()
      
      result = pd.concat(all_data, ignore_index=True)
      return result

def populate_db(tickers: List[str], db_path: str = 'stock_prices.db') -> None:
      df = fetch_historical_prices(tickers)
      if df.empty:
          print("No data fetched")
          return

      print("Shape:", df.shape, "Columns:", list(df.columns))
      
      # Ensure columns are in correct order
      required_cols = ['date', 'symbol', 'open', 'high', 'low', 'close', 'volume']
      missing_cols = [col for col in required_cols if col not in df.columns]
      if missing_cols:
          print(f"Warning: Missing columns: {missing_cols}")
      
      # Select only available columns
      available_cols = [col for col in required_cols if col in df.columns]
      df = df[available_cols]

      conn = sqlite3.connect(db_path)
      df.to_sql('prices', conn, if_exists='replace', index=False)
      conn.close()
      print(f"DB populated successfully with {len(df)} rows")

populate_db(['AAPL', 'TSLA', 'GOOGL', 'AMZN', 'MSFT'])
