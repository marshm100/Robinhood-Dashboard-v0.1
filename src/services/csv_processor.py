"""
CSV processing service for Robinhood transaction data
"""

import pandas as pd
from io import StringIO
from typing import Dict, Any
import re
from datetime import datetime


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

    Expected CSV columns:
    - Activity Date: MM/DD/YYYY format
    - Instrument: Stock ticker or empty
    - Trans Code: Buy, Sell, Dividend, Transfer, etc.
    - Quantity: Number of shares
    - Price: Price per share
    - Amount: Total transaction amount
    """
    try:
        # Read CSV content with error handling
        try:
            df = pd.read_csv(StringIO(csv_content), on_bad_lines='skip', engine='python')
        except Exception as e:
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

        # Clean and format data
        processed_data = []

        for _, row in df.iterrows():
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
                print(f"Error processing row: {row.to_dict()}, Error: {e}")
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


def validate_csv_structure(csv_content: str) -> Dict[str, Any]:
    """
    Validate CSV structure and return information about the data
    """
    try:
        # Use the same robust parsing as process_robinhood_csv
        df = pd.read_csv(StringIO(csv_content), on_bad_lines='skip', engine='python')

        validation_result = {
            'is_valid': True,
            'row_count': len(df),
            'columns': list(df.columns),
            'missing_required': [],
            'warnings': []
        }

        # Check required columns
        required_columns = ['Activity Date', 'Trans Code', 'Amount']
        missing_required = [col for col in required_columns if col not in df.columns]
        if missing_required:
            validation_result['missing_required'] = missing_required
            validation_result['is_valid'] = False

        # Check for data issues
        if len(df) == 0:
            validation_result['warnings'].append("CSV file appears to be empty")

        # Check date column
        if 'Activity Date' in df.columns:
            date_sample = df['Activity Date'].dropna().head(5)
            invalid_dates = []
            for date_val in date_sample:
                formatted = format_date_for_database(str(date_val))
                if formatted == str(date_val) and formatted != '':
                    invalid_dates.append(str(date_val))
            if invalid_dates:
                validation_result['warnings'].append(f"Some dates may be in unexpected format: {invalid_dates[:3]}")

        return validation_result

    except Exception as e:
        return {
            'is_valid': False,
            'error': str(e),
            'row_count': 0,
            'columns': [],
            'missing_required': [],
            'warnings': []
        }
