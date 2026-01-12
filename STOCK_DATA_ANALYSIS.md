# Stock Data Source and Missing Stock Handling Analysis

## Executive Summary

This document explains how the Robinhood Portfolio Analysis application retrieves stock price data and handles cases where transaction data references stocks that don't exist in the database.

## Stock Data Source

### Primary Database: `stockr_backbone`

The application pulls stock price data from a separate SQLite database located at:
```
{project_root}/stockr_backbone/stock_data.db
```

This database contains:
- **`stocks` table**: Stock symbols and metadata (filters out `ephemeral = 1` stocks)
- **`historical_prices` table**: Daily OHLCV (Open, High, Low, Close, Volume) price data

### Service Implementation

The stock price retrieval is handled by `StockPriceService` in `src/services/stock_price_service.py`:

```58:136:src/services/stock_price_service.py
    def get_price_at_date(self, symbol: str, target_date: str) -> Optional[Dict[str, float]]:
        """
        Get stock price data for a specific date

        Args:
            symbol: Stock ticker symbol (e.g., 'AAPL')
            target_date: Date in YYYY-MM-DD format

        Returns:
            Dict with price data or None if not found
        """
        try:
            stock_id = self.get_stock_id(symbol)
            if not stock_id:
                # Try to fetch data for this ticker on-demand
                print(f"Ticker {symbol} not found in database, attempting to fetch data...")
                try:
                    from ...stockr_backbone.src.fetcher import fetch_and_store
                    records_added = fetch_and_store(symbol, incremental=False)
                    if records_added > 0:
                        print(f"Successfully fetched {records_added} records for {symbol}")
                        # Try again to get the stock_id
                        stock_id = self.get_stock_id(symbol)
                    else:
                        print(f"Failed to fetch data for {symbol}")
                        return None
                except Exception as e:
                    print(f"Error fetching data for {symbol}: {e}")
                    return None

            if not stock_id:
                return None

            # Try exact date match first
            result = self._execute_query(
                """SELECT date, open, high, low, close, volume
                   FROM historical_prices
                   WHERE stock_id = ? AND date = ?
                   ORDER BY date DESC LIMIT 1""",
                (stock_id, target_date)
            )

            if result:
                date_val, open_price, high, low, close, volume = result[0]
                return {
                    'date': date_val,
                    'open': open_price,
                    'high': high,
                    'low': low,
                    'close': close,
                    'volume': volume
                }

            # If no exact match, find the most recent price before the target date
            result = self._execute_query(
                """SELECT date, open, high, low, close, volume
                   FROM historical_prices
                   WHERE stock_id = ? AND date <= ?
                   ORDER BY date DESC LIMIT 1""",
                (stock_id, target_date)
            )

            if result:
                date_val, open_price, high, low, close, volume = result[0]
                return {
                    'date': date_val,
                    'open': open_price,
                    'high': high,
                    'low': low,
                    'close': close,
                    'volume': volume
                }

            return None

        except Exception as e:
            print(f"Error getting price for {symbol} on {target_date}: {e}")
            return None
```

### External Data Source: Stooq.com

When a stock is not found in the database, the system attempts to fetch it on-demand using the `fetch_and_store` function from `stockr_backbone/src/fetcher.py`. This function:

1. Fetches historical price data from Stooq.com API: `https://stooq.com/q/d/l/?s={symbol}.us&i=d`
2. Parses the CSV response
3. Stores the data in the `stockr_backbone` database
4. Returns the number of records added

## Missing Stock Handling Process

### Flow Diagram

```
Robinhood CSV Upload
    ↓
Transaction Stored (ticker may be None or any symbol)
    ↓
Portfolio Analysis Requested
    ↓
For each ticker in transactions:
    ↓
    get_stock_price_at_date(ticker, date)
        ↓
        StockPriceService.get_price_at_date()
            ↓
            Check stockr_backbone database
                ↓
                Stock Found?
                    ├─ YES → Return price data
                    └─ NO → Attempt on-demand fetch
                            ↓
                            fetch_and_store() called
                                ↓
                                Fetch from Stooq.com
                                    ↓
                                    Success?
                                        ├─ YES → Store in DB → Return price
                                        └─ NO → Return None
                                            ↓
                                            Portfolio calculation continues
                                            (missing prices skipped)
```

### Step-by-Step Process

#### 1. CSV Upload Phase
**Location**: `src/routes/api.py` - `upload_csv()` endpoint

- Transactions are stored **regardless** of whether the stock exists in the stock database
- The ticker field is stored as-is from the CSV (can be `None` for non-stock transactions)
- No validation is performed against the stock database at upload time

```173:194:src/routes/api.py
        for i in range(0, len(transactions_df), batch_size):
            batch = transactions_df.iloc[i:i+batch_size]

            # Prepare batch data for bulk insert
            batch_data = []
            for _, row in batch.iterrows():
                batch_data.append({
                    'activity_date': row['activity_date'],
                    'ticker': row.get('ticker'),
                    'trans_code': row['trans_code'],
                    'quantity': row.get('quantity'),
                    'price': row.get('price'),
                    'amount': row['amount']
                })

            # Bulk insert
            db.execute(Transaction.__table__.insert(), batch_data)
            transactions_saved += len(batch_data)

            # Commit batch
            db.commit()
```

#### 2. Price Lookup Phase
**Location**: `src/services/portfolio_calculator.py` - `get_stock_price_at_date()`

When portfolio calculations need a stock price:

```105:118:src/services/portfolio_calculator.py
    def get_stock_price_at_date(self, ticker: str, date: str) -> Optional[float]:
        """
        Get stock price for ticker at specific date
        Uses stockr_backbone database for price data
        """
        try:
            price_data = stock_price_service.get_price_at_date(ticker, date)
            if price_data and 'close' in price_data:
                return price_data['close']
            return None

        except Exception as e:
            print(f"Error getting price for {ticker} on {date}: {e}")
            return None
```

#### 3. On-Demand Fetch Attempt
**Location**: `src/services/stock_price_service.py` - `get_price_at_date()` lines 70-86

If a stock is not found:

```70:86:src/services/stock_price_service.py
            stock_id = self.get_stock_id(symbol)
            if not stock_id:
                # Try to fetch data for this ticker on-demand
                print(f"Ticker {symbol} not found in database, attempting to fetch data...")
                try:
                    from ...stockr_backbone.src.fetcher import fetch_and_store
                    records_added = fetch_and_store(symbol, incremental=False)
                    if records_added > 0:
                        print(f"Successfully fetched {records_added} records for {symbol}")
                        # Try again to get the stock_id
                        stock_id = self.get_stock_id(symbol)
                    else:
                        print(f"Failed to fetch data for {symbol}")
                        return None
                except Exception as e:
                    print(f"Error fetching data for {symbol}: {e}")
                    return None
```

**Note**: The `fetch_and_store` function is a Celery task that may not work correctly in the current MVP setup (Celery was removed during cleanup). This could cause the on-demand fetch to fail silently.

#### 4. Graceful Degradation

When a price cannot be found (even after fetch attempt), the system handles it gracefully:

**In Portfolio Value Calculations**:
```89:103:src/services/portfolio_calculator.py
    def get_portfolio_value_at_date(self, date: str, holdings: Optional[Dict[str, float]] = None) -> float:
        """
        Calculate portfolio value at a specific date
        """
        if holdings is None:
            holdings = self.get_current_holdings()

        total_value = 0.0

        for ticker, quantity in holdings.items():
            price = self.get_stock_price_at_date(ticker, date)
            if price and price > 0:
                total_value += quantity * price

        return total_value
```

- Missing prices are **skipped** (not included in calculations)
- Portfolio value is calculated only for stocks with available prices
- No errors are raised; calculations proceed with available data

**In Portfolio History**:
```239:244:src/services/portfolio_calculator.py
                # Calculate portfolio value at this date
                portfolio_value = 0.0
                for ticker, quantity in current_holdings.items():
                    price = self.get_stock_price_at_date(ticker, date)
                    if price and price > 0:
                        portfolio_value += quantity * price
```

## Current Limitations and Issues

### 1. On-Demand Fetch May Not Work

**Issue**: The `fetch_and_store` function is decorated as a Celery task (`@app.task`), but Celery was removed during MVP cleanup. This means:

- The import may fail if `celery_app` module doesn't exist: `from ...stockr_backbone.src.fetcher import fetch_and_store`
- The function body itself is a regular Python function and can work without Celery, but the decorator requires the Celery app to be initialized
- If the import succeeds, the function can be called directly (not as a task), but the decorator may cause issues

**Impact**: 
- If import fails: Stocks not in the database will return `None` for prices
- If import succeeds but function fails: Same result - missing stocks excluded from calculations
- The on-demand fetch feature is **potentially non-functional** depending on the Celery app setup

### 2. No User Notification

**Issue**: When a stock is missing and cannot be fetched:
- No error is raised to the user
- No warning is displayed in the UI
- The stock is silently excluded from calculations
- Portfolio values may be **understated** if significant positions are missing

### 3. No Fallback to CSV Price

**Issue**: The Robinhood CSV includes a `Price` column for each transaction, but this is not used as a fallback when the stock database lookup fails.

**Current Behavior**:
- Transaction price from CSV is stored in the `Transaction.price` field
- But portfolio calculations use `get_stock_price_at_date()` which only queries the stock database
- CSV prices are not used as a fallback

## Recommendations

### Short-Term Fixes

1. **Add Logging**: Log all missing stock symbols to help identify data gaps
   ```python
   if not stock_id:
       logger.warning(f"Stock {symbol} not found in database and fetch failed")
   ```

2. **Return Missing Stocks List**: Include a list of missing stocks in API responses
   ```python
   {
       "portfolio_value": 10000,
       "missing_stocks": ["XYZ", "ABC"],
       "warnings": ["Some positions excluded due to missing price data"]
   }
   ```

3. **Use CSV Price as Fallback**: When database lookup fails, use the transaction price from CSV if available
   ```python
   price = self.get_stock_price_at_date(ticker, date)
   if not price:
       # Fallback to transaction price from CSV
       price = self._get_transaction_price(ticker, date)
   ```

### Long-Term Improvements

1. **Pre-validate Stocks on Upload**: Check which stocks from the CSV exist in the database and warn users
2. **Batch Fetch Missing Stocks**: After CSV upload, automatically fetch all missing stocks in the background
3. **Fix On-Demand Fetch**: Make `fetch_and_store` work without Celery (direct function call)
4. **Add Stock Validation Endpoint**: Allow users to check which stocks are available before uploading

## Code Locations Summary

| Component | File | Key Functions |
|-----------|------|---------------|
| Stock Price Service | `src/services/stock_price_service.py` | `get_price_at_date()`, `get_stock_id()` |
| Portfolio Calculator | `src/services/portfolio_calculator.py` | `get_stock_price_at_date()`, `get_portfolio_value_at_date()` |
| CSV Upload | `src/routes/api.py` | `upload_csv()` |
| Stock Fetcher | `stockr_backbone/src/fetcher.py` | `fetch_and_store()` (Celery task) |
| Database | `stockr_backbone/stock_data.db` | SQLite database with stocks and historical_prices tables |

## Testing Scenarios

To test missing stock handling:

1. **Upload CSV with unknown ticker**: Include a transaction with a ticker that doesn't exist in `stockr_backbone`
2. **Check portfolio calculations**: Verify the unknown ticker is excluded (portfolio value should be lower)
3. **Check API responses**: Verify no errors are raised, but missing stocks are not included
4. **Check logs**: Look for "Ticker {symbol} not found" messages

## Conclusion

The application handles missing stocks gracefully by:
- Attempting on-demand fetch (currently non-functional due to Celery removal)
- Skipping missing prices in calculations (no errors raised)
- Continuing analysis with available data

However, this creates a **silent data loss** issue where users may not realize some positions are excluded from their portfolio analysis. Improvements should focus on visibility (warnings/notifications) and reliability (working on-demand fetch or CSV price fallback).

