from src.models import get_close_price

def process_batch(data):
    for row in data:
        row['value'] = row['quantity'] * (get_close_price(row['instrument'], row['activity_date']) or row['price'])
    return data
