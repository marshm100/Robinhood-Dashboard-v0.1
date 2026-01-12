import pandas as pd

data = {'Activity Date': ['2024-01-02', '2024-01-03'], 'Instrument': ['AAPL', 'TSLA'], 'Trans Code': ['BUY', 'SELL'], 'Quantity': [10, -5], 'Price': [185.0, 248.0], 'Amount': [1850.0, -1240.0]}
df = pd.DataFrame(data)
df.to_csv('test.csv', index=False)
print("test.csv created")
