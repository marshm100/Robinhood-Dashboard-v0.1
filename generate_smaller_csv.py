import csv
import random
from datetime import datetime, timedelta

def generate_csv(file_name, num_rows=10000):
    tickers = ['AAPL', 'TSLA', 'GOOG', 'AMZN', 'MSFT']  # Common Robinhood tickers for testing
    activities = ['Buy', 'Sell', 'Dividend']

    with open(file_name, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Date', 'Activity', 'Ticker', 'Quantity', 'Price', 'Amount'])  # Adjust columns if your app expects different ones
        current_date = datetime.now()
        for _ in range(num_rows):
            date = current_date - timedelta(days=random.randint(0, 365*5))  # Spread over up to 5 years
            activity = random.choice(activities)
            ticker = random.choice(tickers)
            quantity = random.randint(1, 100)
            price = round(random.uniform(50, 500), 2)
            amount = round(quantity * price if activity != 'Dividend' else random.uniform(1, 50), 2)
            writer.writerow([date.strftime('%Y-%m-%d'), activity, ticker, quantity, price, amount])

if __name__ == '__main__':
    generate_csv('small_transactions.csv')
