import pandas as pd
from src.core.models import get_close_price

df = pd.read_csv('test.csv')
for index, row in df.iterrows():
    close = get_close_price(row['Instrument'], row['Activity Date']) or row['Price']
    print(f"{row['Instrument']} on {row['Activity Date']}: Value = {row['Quantity'] * close}")

print("Demo: Run db_populator.py, then uvicorn, upload test.csv, check dashboard.")