import pandas as pd
from faker import Faker
import random
from datetime import datetime, timedelta

fake = Faker()

# Define possible transaction codes (based on typical Robinhood CSVs)
trans_codes = ['Buy', 'Sell', 'Dividend', 'Split', 'Deposit', 'Withdrawal']

# Generate random stock symbols (e.g., AAPL, TSLA, etc.)
def random_symbol():
    return fake.lexify(text='???').upper() + random.choice(['', '.', fake.lexify(text='?')])

# Generate dataset
num_rows = 50000  # Adjust for larger/smaller tests
data = {
    'Activity Date': [],
    'Trans Code': [],
    'Quantity': [],
    'Price': [],
    'Amount': [],
    'Ticker': [],  # Assuming 'Ticker' or 'Symbol' column
    # Add more columns if your CSV processor requires them (e.g., 'Description', 'Currency')
}

start_date = datetime(2010, 1, 1)
end_date = datetime.now()

for _ in range(num_rows):
    trans_date = fake.date_between(start_date=start_date, end_date=end_date)
    data['Activity Date'].append(trans_date.strftime('%Y-%m-%d'))
    data['Trans Code'].append(random.choice(trans_codes))
    data['Quantity'].append(round(random.uniform(0.1, 1000), 4) if random.random() > 0.2 else 0)  # Some zero for non-trades
    data['Price'].append(round(random.uniform(0.01, 2000), 2))
    data['Amount'].append(round(random.uniform(-50000, 50000), 2))  # Positive/negative for buys/sells
    data['Ticker'].append(random_symbol())

# Create DataFrame and save to CSV
df = pd.DataFrame(data)
df.to_csv('large_transactions.csv', index=False)
print(f"Generated large_transactions.csv with {num_rows} rows.")
