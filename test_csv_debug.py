#!/usr/bin/env python3
"""
Debug script to test CSV processing
"""

import pandas as pd
from io import StringIO
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def format_date_for_database(date_str: str) -> str:
    """
    Format a date string from MM/DD/YYYY to YYYY-MM-DD for storage in the database
    """
    if not date_str or date_str.strip() == '':
        return ''

    try:
        # Split the date string by the '/' character
        parts = date_str.split('/')
        if len(parts) != 3:
            return date_str

        # Get the month, day, and year parts
        month = parts[0].zfill(2)
        day = parts[1].zfill(2)
        year = parts[2]

        # Combine into YYYY-MM-DD format
        return f"{year}-{month}-{day}"
    except Exception as e:
        print(f"Error formatting date: {e}")
        return date_str

def clean_numeric_value(value_str: str) -> float:
    """
    Clean and parse numeric values from CSV, handling currency symbols and parentheses
    """
    if not value_str or value_str.strip() == '':
        return 0.0

    try:
        # Remove currency symbols, commas, and parentheses
        import re
        cleaned = re.sub(r'[$,()]', '', str(value_str).strip())

        # Handle parentheses for negative values
        if '(' in str(value_str) and ')' in str(value_str):
            return -float(cleaned)

        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0

def process_robinhood_csv(csv_content: str) -> pd.DataFrame:
    """
    Process Robinhood CSV content and return cleaned DataFrame
    """
    try:
        # Read CSV content with error handling
        try:
            df = pd.read_csv(StringIO(csv_content), on_bad_lines='skip', engine='python')
        except Exception as e:
            print(f"Initial CSV read failed: {e}")
            # Fallback: try to clean the CSV content
            lines = csv_content.split('\n')
            cleaned_lines = []
            for line in lines:
                # Remove any lines that don't have the right number of quotes
                quote_count = line.count('"')
                if quote_count % 2 == 0:  # Even number of quotes
                    cleaned_lines.append(line)

            cleaned_content = '\n'.join(cleaned_lines)
            df = pd.read_csv(StringIO(cleaned_content), on_bad_lines='skip', engine='python')

        print(f"CSV columns found: {list(df.columns)}")
        print(f"Total rows: {len(df)}")

        # Validate required columns
        required_columns = ['Activity Date', 'Trans Code', 'Amount']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")

        # Rename columns to match database schema
        column_mapping = {
            'Activity Date': 'activity_date',
            'Instrument': 'ticker',
            'Trans Code': 'trans_code',
            'Quantity': 'quantity',
            'Price': 'price',
            'Amount': 'amount'
        }

        # Only rename columns that exist
        existing_mapping = {k: v for k, v in column_mapping.items() if k in df.columns}
        df = df.rename(columns=existing_mapping)

        print("Column mapping applied:", existing_mapping)

        # Clean and format data
        processed_data = []

        for idx, row in df.iterrows():
            try:
                # Format date
                activity_date = format_date_for_database(str(row.get('activity_date', '')))

                # Clean ticker (remove empty strings)
                ticker = str(row.get('ticker', '')).strip()
                if ticker == '':
                    ticker = None

                # Get transaction code
                trans_code = str(row.get('trans_code', '')).strip()

                # Clean numeric values
                quantity = clean_numeric_value(str(row.get('quantity', '')))
                price = clean_numeric_value(str(row.get('price', '')))
                amount = clean_numeric_value(str(row.get('amount', '')))

                processed_data.append({
                    'activity_date': activity_date,
                    'ticker': ticker,
                    'trans_code': trans_code,
                    'quantity': quantity if quantity != 0 else None,
                    'price': price if price != 0 else None,
                    'amount': amount
                })

            except Exception as e:
                print(f"Error processing row {idx}: {row.to_dict()}, Error: {e}")
                continue

        # Create cleaned DataFrame
        result_df = pd.DataFrame(processed_data)

        # Remove rows with invalid dates
        result_df = result_df[result_df['activity_date'] != '']

        # Sort by date
        result_df['activity_date'] = pd.to_datetime(result_df['activity_date'], errors='coerce')
        result_df = result_df.dropna(subset=['activity_date'])
        result_df = result_df.sort_values('activity_date')
        result_df['activity_date'] = result_df['activity_date'].dt.strftime('%Y-%m-%d')

        print(f"Successfully processed {len(result_df)} transactions from CSV")
        return result_df

    except Exception as e:
        print(f"Error processing CSV: {e}")
        raise

def main():
    # Read the CSV file
    try:
        with open('sample_transactions.csv', 'r', encoding='utf-8') as f:
            csv_content = f.read()

        print("=== CSV DEBUG TEST ===")
        print(f"CSV content length: {len(csv_content)} characters")

        # Show first few lines
        lines = csv_content.split('\n')[:5]
        print("First 5 lines of CSV:")
        for i, line in enumerate(lines):
            print(f"  {i+1}: {line[:100]}...")

        print("\nProcessing CSV...")
        df = process_robinhood_csv(csv_content)

        print(f"\n✅ SUCCESS: Processed {len(df)} transactions")
        print("\nSample of processed data:")
        print(df.head())

        print(f"\nTransaction codes found: {df['trans_code'].unique()}")
        print(f"Date range: {df['activity_date'].min()} to {df['activity_date'].max()}")

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
