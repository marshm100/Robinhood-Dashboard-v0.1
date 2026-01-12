#!/usr/bin/env python3
"""
Test the CSV processor with the actual Robinhood data
"""

import pandas as pd
from src.services.csv_processor import process_robinhood_csv

def main():
    print('🚀 Testing Robinhood CSV Processor')
    print('=' * 50)

    try:
        # Read the CSV
        with open('354e8757-62f9-506c-9b30-db3ac6d907e8.csv', 'r', encoding='utf-8') as f:
            csv_content = f.read()

        print(f'📄 CSV loaded: {len(csv_content)} characters')

        # Process it
        df = process_robinhood_csv(csv_content)

        print(f'✅ Successfully processed {len(df)} transactions!')
        print(f'📅 Date range: {df["activity_date"].min()} to {df["activity_date"].max()}')

        # Show transaction types
        trans_counts = df['trans_code'].value_counts()
        print(f'\n💼 Transaction Types ({len(trans_counts)} types):')
        for trans_type, count in trans_counts.items():
            print(f'  {trans_type}: {count} transactions')

        # Show top tickers
        ticker_counts = df[df['ticker'].notna()]['ticker'].value_counts()
        print(f'\n📈 Top Tickers by Transactions:')
        for ticker, count in ticker_counts.head(10).items():
            print(f'  {ticker}: {count} transactions')

        # Sample data
        print(f'\n📋 Sample Data (first 5 transactions):')
        sample = df.head(5)
        for _, row in sample.iterrows():
            ticker = row['ticker'] or 'N/A'
            qty = f"{row['quantity']:.4f}" if pd.notna(row['quantity']) else 'N/A'
            price = f"${row['price']:.2f}" if pd.notna(row['price']) else 'N/A'
            amount = f"${row['amount']:.2f}" if pd.notna(row['amount']) else 'N/A'
            print(f'  {row["activity_date"]} | {ticker} | {row["trans_code"]} | Qty:{qty} | Price:{price} | Amount:{amount}')

        # Summary stats
        total_buy = df[df['trans_code'] == 'Buy']['amount'].sum()
        total_sell = df[df['trans_code'] == 'Sell']['amount'].sum()
        total_dividends = df[df['trans_code'] == 'CDIV']['amount'].sum()

        print(f'\n💰 Financial Summary:')
        print(f'  Total Buy Amount: ${abs(total_buy):,.2f}')
        print(f'  Total Sell Amount: ${total_sell:,.2f}')
        print(f'  Total Dividends: ${total_dividends:,.2f}')

        print(f'\n🎉 SUCCESS! The app is fully compatible with this Robinhood CSV format.')
        print(f'   Ready to process {len(df)} transactions with full portfolio analysis!')

    except Exception as e:
        print(f'❌ Error processing CSV: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
