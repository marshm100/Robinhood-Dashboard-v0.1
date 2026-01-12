import sqlite3
import pandas as pd

conn = sqlite3.connect('stock_prices.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]
print('Tables:', tables)

if 'prices' in tables:
    cursor.execute('SELECT COUNT(*) FROM prices')
    count = cursor.fetchone()[0]
    print(f'Row count in prices table: {count}')
    
    df = pd.read_sql('SELECT * FROM prices LIMIT 5', conn)
    print('\nSample rows:')
    print(df)

conn.close()
