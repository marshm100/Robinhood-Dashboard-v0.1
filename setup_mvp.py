# setup_mvp.py - Save and run this
import os
import subprocess
import sqlite3
import yfinance as yf
from datetime import datetime
import pandas as pd

# 1. Install yfinance if needed
subprocess.run(["pip", "install", "yfinance"], check=True)

# 2. Populate DB
def fetch_historical_prices(tickers, start_date='2024-01-01', end_date=datetime.now().strftime('%Y-%m-%d')):
    data = []
    for ticker in tickers:
        try:
            df = yf.download(ticker, start=start_date, end=end_date)
            if df.empty:
                print(f"No data for {ticker}")
                continue
            df['symbol'] = ticker
            df['date'] = df.index.strftime('%Y-%m-%d')
            data.append(df[['symbol', 'date', 'Open', 'High', 'Low', 'Close', 'Volume']])
        except Exception as e:
            print(f"Error: {e}")
    return pd.concat(data) if data else pd.DataFrame()

df = fetch_historical_prices(['AAPL', 'TSLA', 'GOOGL'])
if not df.empty:
    df.columns = ['symbol', 'date', 'open', 'high', 'low', 'close', 'volume']
    conn = sqlite3.connect('stock_prices.db')
    df.to_sql('prices', conn, if_exists='replace', index=False)
    conn.close()
    print("DB populated")

# 3. Add to models.py
models_code = """
import sqlite3
from typing import Optional

STOCKR_DB_PATH = 'stock_prices.db'

def get_close_price(symbol: str, date: str) -> Optional[float]:
    try:
        conn = sqlite3.connect(STOCKR_DB_PATH)
        cursor = conn.cursor()
        cursor.execute(\"SELECT close FROM prices WHERE symbol = ? AND date = ?\", (symbol, date))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        print(f\"DB error: {e}\")
        return None
"""
with open('src/models.py', 'a') as f:
    f.write(models_code)

# 4. Update batch_processor.py
batch_code = """
from src.models import get_close_price

def process_batch(data):
    for row in data:
        row['value'] = row['quantity'] * (get_close_price(row['instrument'], row['activity_date']) or row['price'])
    return data
"""
with open('src/services/batch_processor.py', 'a') as f:
    f.write(batch_code)

# 5. Start app
subprocess.Popen(["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"])

# 6. Create/test CSV
pd.DataFrame({'Activity Date': ['2024-01-02'], 'Instrument': ['AAPL'], 'Quantity': [10], 'Price': [185.0]}).to_csv('test.csv', index=False)
subprocess.run(["powershell", "Invoke-WebRequest -Uri http://localhost:8000/upload -Method POST -InFile test.csv -ContentType 'multipart/form-data'"])

# 7. Test price
os.system("python -c \"from src.models import get_close_price; print(get_close_price('AAPL', '2024-01-02'))\"")

# 8. Edit README
with open('README.md', 'a') as f:
    f.write("\n## Free MVP Pricing\nRun db_populator.py for local DB (yfinance free fetch).")

# 9. Create demo.py
demo_code = """
import pandas as pd
from src.models import get_close_price
from src.services.batch_processor import process_batch

data = pd.read_csv('test.csv')
processed = process_batch(data)
print(processed)
print(get_close_price('AAPL', '2024-01-02'))
"""
with open('demo.py', 'w') as f:
    f.write(demo_code)

print("MVP ready. Run demo.py.")
