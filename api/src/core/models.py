import sqlite3
from typing import Optional

STOCKR_DB_PATH = 'stock_prices.db'

def get_close_price(symbol: str, date: str) -> Optional[float]:
      try:
          conn = sqlite3.connect(STOCKR_DB_PATH)
          cursor = conn.cursor()
          cursor.execute("SELECT close FROM prices WHERE symbol = ? AND date = ?", (symbol, date))
          result = cursor.fetchone()
          conn.close()
          return result[0] if result else None
      except Exception as e:
          print(f"DB error: {e}")
          return None  # Fallback to CSV price or average
