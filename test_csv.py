#!/usr/bin/env python3
"""
Test CSV processing for the specific Robinhood format
"""

import pandas as pd
from io import StringIO
from src.services.csv_processor import process_robinhood_csv, validate_csv_structure

def main():
    print("🔍 Testing Robinhood CSV Processing")
    print("=" * 50)

    # Read the CSV file
    try:
        with open('354e8757-62f9-506c-9b30-db3ac6d907e8.csv', 'r', encoding='utf-8') as f:
            csv_content = f.read()

        print("✅ CSV file loaded successfully")
        print(f"Content length: {len(csv_content)} characters")

        # Show first few lines
        lines = csv_content.split('\n')[:10]
        print("\n📋 First 10 lines of CSV:")
        for i, line in enumerate(lines, 1):
            print(f"  {i}: {line[:100]}..." if len(line) > 100 else f"  {i}: {line}")

        # Validate structure
        print("\n🔍 Validating CSV structure...")
        validation = validate_csv_structure(csv_content)
        print(f"Valid: {validation['is_valid']}")
        print(f"Rows: {validation['row_count']}")
        print(f"Columns: {validation['columns']}")
        if validation['missing_required']:
            print(f"❌ Missing required: {validation['missing_required']}")
        if validation['warnings']:
            print(f"⚠️  Warnings: {validation['warnings']}")

        if validation['is_valid']:
            print("\n🚀 Processing CSV data...")
            df = process_robinhood_csv(csv_content)

            print(f"✅ Successfully processed {len(df)} transactions")

            # Show summary
            print(f"\n📊 Processing Summary:")
            print(f"  Total transactions: {len(df)}")
            print(f"  Date range: {df['activity_date'].min()} to {df['activity_date'].max()}")

            # Transaction types
            trans_types = df['trans_code'].value_counts()
            print(f"\n💼 Transaction Types:")
            for trans_type, count in trans_types.items():
                print(f"  {trans_type}: {count}")

            # Tickers with most transactions
            ticker_counts = df[df['ticker'].notna()]['ticker'].value_counts()
            print(f"\n📈 Top Tickers by Transaction Count:")
            for ticker, count in ticker_counts.head(10).items():
                print(f"  {ticker}: {count} transactions")

            # Sample data
            print(f"\n📋 Sample Processed Data (first 5 rows):")
            sample = df.head(5)
            for _, row in sample.iterrows():
                ticker = row['ticker'] or 'N/A'
                qty = row['quantity'] if pd.notna(row['quantity']) else 'N/A'
                price = row['price'] if pd.notna(row['price']) else 'N/A'
                amount = row['amount'] if pd.notna(row['amount']) else 'N/A'
                print(f"  {row['activity_date']} | {ticker} | {row['trans_code']} | Qty:{qty} | Price:{price} | Amount:{amount}")

        else:
            print("❌ CSV validation failed. Cannot process.")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
