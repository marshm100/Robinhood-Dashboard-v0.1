# Stockr_Backbone: Core Architecture Documentation

## ⭐ CRITICAL CORE COMPONENT ⭐

**stockr_backbone is NOT an optional feature - it is the FOUNDATIONAL DATABASE CORE of the application architecture.**

This document describes the most important component of the Robinhood Portfolio Analysis application. All planning, design, implementation, and maintenance work must treat stockr_backbone as a **non-negotiable foundation**.

---

## Executive Summary

**stockr_backbone** is the internal stock data maintenance system that serves as the **primary and preferred source** for all stock price information in the application. It runs continuously in the background to maintain an up-to-date database of stock prices, minimizing reliance on external free-tier APIs with strict rate limits.

### Core Functionality Enabled by stockr_backbone:

1. **Portfolio Valuation** - Calculating current and historical portfolio values from Robinhood transactions
2. **Custom Portfolio Backtesting** - Enabling hypothetical portfolio creation and historical performance simulation
3. **Portfolio Comparison** - Comparing custom portfolios against actual Robinhood portfolio
4. **Benchmark Comparison** - Providing historical data for SPY, QQQ, and other market benchmarks
5. **Performance Metrics** - All return calculations, volatility, Sharpe ratio, and risk metrics depend on accurate price data
6. **Historical Analysis** - Rolling returns, drawdown analysis, and time-series calculations

**Without stockr_backbone, none of these core features would be possible.**

### Key Principles

1. **Primary Data Source**: The stockr_backbone database is the FIRST and PRIMARY source for stock data
2. **Automatic Maintenance**: The system automatically tracks and refreshes ALL stocks in the database
3. **Auto-Discovery**: New stocks encountered by the application are automatically added to tracking
4. **Continuous Operation**: The maintenance service runs 24/7 in the background
5. **Minimize External API Calls**: By maintaining an internal database, we reduce dependency on rate-limited external APIs

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                          │
│  (FastAPI, Portfolio Calculator, Stock Price Service)        │
└──────────────────────┬──────────────────────────────────────┘
                        │
                        │ Queries stock data
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              Stockr_Backbone Core System                     │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  Background Maintenance Service (Continuous)         │  │
│  │  - Refreshes all tracked stocks every 60 minutes      │  │
│  │  - Runs independently in background thread           │  │
│  └─────────────────────────────────────────────────────┘  │
│                        │                                     │
│                        │ Maintains                          │
│                        ▼                                     │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  Internal Stock Database (SQLite)                    │  │
│  │  - stocks table: All tracked symbols                 │  │
│  │  - historical_prices table: OHLCV data              │  │
│  └─────────────────────────────────────────────────────┘  │
│                        │                                     │
│                        │ Auto-adds new stocks                │
│                        ▼                                     │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  Fetcher Service (Standalone)                       │  │
│  │  - fetch_and_store(): Core fetching function         │  │
│  │  - ensure_stock_tracked(): Auto-discovery           │  │
│  │  - refresh_all_stocks(): Batch maintenance          │  │
│  └─────────────────────────────────────────────────────┘  │
│                        │                                     │
│                        │ Fetches from                        │
│                        ▼                                     │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  External API (Stooq.com) - Minimal Usage          │  │
│  │  - Only used when stock not in database            │  │
│  │  - Rate limits respected via internal caching       │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Background Maintenance Service

**Location**: `stockr_backbone/src/background_maintenance.py`

**Purpose**: Runs continuously in the background to maintain stock data freshness.

**Key Features**:
- Automatically refreshes all tracked stocks on a schedule (default: every 60 minutes)
- Runs in a separate daemon thread, independent of the main application
- Handles errors gracefully and continues running
- Provides status information via API endpoint

**Integration**: Started automatically during application startup via `src/main.py`

**Configuration**:
- `refresh_interval_minutes`: How often to refresh (default: 60)
- `initial_delay_seconds`: Delay before first refresh (default: 30)
- `batch_size`: Stocks processed per batch (default: 10)

### 2. Standalone Fetcher

**Location**: `stockr_backbone/src/fetcher_standalone.py`

**Purpose**: Core function for fetching and storing stock data. **No Celery dependency**.

**Key Functions**:

#### `fetch_and_store(symbol, incremental=True, ephemeral=False)`
- Fetches stock data from Stooq.com API
- Stores data in internal database
- Supports incremental updates (only new data) or full refresh
- Returns number of records added

#### `ensure_stock_tracked(symbol)`
- **Auto-discovery function** - called when new ticker is encountered
- Checks if stock exists in database
- If not, automatically adds it and fetches initial data
- Marks stock as permanently tracked (non-ephemeral)

#### `refresh_all_stocks(incremental=True)`
- Refreshes data for ALL tracked stocks
- Called by background maintenance service
- Returns summary of refresh operation

### 3. Stock Price Service Integration

**Location**: `src/services/stock_price_service.py`

**Integration Point**: When `get_price_at_date()` is called and stock is not found:

1. Automatically calls `ensure_stock_tracked(symbol)`
2. Stock is added to tracking
3. Initial data is fetched
4. Price lookup proceeds with newly added stock

**This ensures zero manual intervention** - new stocks are automatically discovered and tracked.

### 4. Database Schema

**Location**: `stockr_backbone/stock_data.db` (SQLite)

**Tables**:

#### `stocks`
- `id`: Primary key
- `symbol`: Stock ticker (unique, indexed)
- `name`: Stock name (optional)
- `ephemeral`: 0 = permanently tracked, 1 = temporary

#### `historical_prices`
- `id`: Primary key
- `stock_id`: Foreign key to stocks
- `date`: Price date
- `open`, `high`, `low`, `close`: OHLC prices
- `volume`: Trading volume
- Unique constraint on (stock_id, date)

---

## Data Flow

### Normal Operation (Stock in Database)

```
1. Application requests price for "AAPL" on "2024-01-15"
2. StockPriceService.get_price_at_date("AAPL", "2024-01-15")
3. Query stockr_backbone database
4. Return price data (no external API call)
```

### Auto-Discovery (New Stock)

```
1. Application requests price for "XYZ" on "2024-01-15"
2. StockPriceService.get_price_at_date("XYZ", "2024-01-15")
3. Stock not found in database
4. Automatically call ensure_stock_tracked("XYZ")
5. Fetch initial data from Stooq.com
6. Store in database
7. Mark as permanently tracked
8. Return price data
9. Background service will now maintain "XYZ" automatically
```

### Background Maintenance

```
1. Background service wakes up (every 60 minutes)
2. Get list of all tracked stocks (ephemeral=0)
3. For each stock:
   a. Call fetch_and_store(symbol, incremental=True)
   b. Only fetch new data since last update
   c. Store new records in database
4. Log summary of refresh operation
5. Sleep until next refresh interval
```

---

## API Endpoints

### `/api/stockr-status`

**Purpose**: Get status of stockr_backbone maintenance service

**Response**:
```json
{
  "status": "ok",
  "stockr_backbone": {
    "maintenance_service": {
      "running": true,
      "refresh_interval_minutes": 60,
      "refresh_count": 42,
      "last_refresh": "2024-01-15T14:30:00",
      "tracked_stocks_count": 150,
      "thread_alive": true
    },
    "description": "Core architectural component for maintaining stock database",
    "importance": "CRITICAL - This service maintains the internal stock database"
  }
}
```

---

## Startup Integration

**Location**: `src/main.py` - `startup_event()`

The maintenance service is started automatically when the application starts:

```python
@app.on_event("startup")
def startup_event():
    # ... database initialization ...
    
    # Start stockr_backbone maintenance service
    start_maintenance_service(refresh_interval_minutes=60)
```

**Shutdown**: Service is stopped gracefully on application shutdown.

---

## Error Handling

The system is designed to be resilient:

1. **Network Errors**: Retry with exponential backoff (via tenacity)
2. **Database Errors**: Logged but don't stop the service
3. **Invalid Symbols**: Skipped with warning
4. **API Rate Limits**: Handled by maintaining internal database (minimal external calls)
5. **Service Failures**: Logged but application continues to function

---

## Performance Considerations

### Minimizing External API Calls

- **Primary Source**: Internal database (no API call)
- **Incremental Updates**: Only fetch new data, not entire history
- **Batch Processing**: Process stocks in batches to avoid overwhelming API
- **Caching**: All data stored locally, reducing repeat API calls

### Database Performance

- Indexed on `symbol` and `date` for fast lookups
- Unique constraints prevent duplicate data
- SQLite is sufficient for MVP scale

---

## Monitoring and Observability

### Logs

All operations are logged via `config/logging_config.py`:
- Stock additions
- Refresh operations
- Errors and warnings
- Performance metrics

### Status Endpoint

Monitor service health via `/api/stockr-status`

### Metrics Tracked

- Number of tracked stocks
- Refresh count
- Last refresh time
- Success/failure rates

---

## Testing

### Manual Testing

1. **Start Application**: Verify maintenance service starts
2. **Check Status**: Call `/api/stockr-status`
3. **Add New Stock**: Request price for unknown ticker
4. **Verify Auto-Add**: Check that stock is now tracked
5. **Wait for Refresh**: Verify background refresh updates data

### Test Scenarios

- ✅ Service starts on application startup
- ✅ New stocks are automatically added
- ✅ Background refresh maintains data
- ✅ Service handles errors gracefully
- ✅ Status endpoint provides accurate information

---

## Configuration

### Environment Variables

- `DATABASE_URL`: Database connection string (defaults to SQLite)
- `SQL_ECHO`: Enable SQL query logging (for debugging)

### Runtime Configuration

- `refresh_interval_minutes`: Set via `start_maintenance_service()`
- Default: 60 minutes (configurable)

---

## Dependencies

### Required

- `requests`: HTTP client for API calls
- `sqlalchemy`: Database ORM
- `tenacity`: Retry logic with exponential backoff
- `loguru`: Structured logging

### Not Required (Removed)

- ❌ `celery`: Removed - using standalone functions
- ❌ `redis`: Not needed for MVP

---

## Future Enhancements

While the current implementation is fully functional, potential improvements:

1. **PostgreSQL Support**: For larger scale deployments
2. **Multiple Data Sources**: Add backup data sources if Stooq fails
3. **Real-time Updates**: WebSocket support for live price updates
4. **Data Validation**: Validate fetched data quality
5. **Metrics Dashboard**: Visual monitoring of service health

---

## Troubleshooting

### Service Not Starting

**Symptoms**: No logs about maintenance service starting

**Solutions**:
1. Check Python path includes `stockr_backbone`
2. Verify all dependencies installed
3. Check database file exists and is writable
4. Review startup logs for errors

### Stocks Not Being Added

**Symptoms**: New tickers return `None` for prices

**Solutions**:
1. Check `ensure_stock_tracked()` is being called
2. Verify Stooq.com API is accessible
3. Check logs for fetch errors
4. Verify database is writable

### Background Refresh Not Working

**Symptoms**: Data becomes stale

**Solutions**:
1. Check service status via `/api/stockr-status`
2. Verify thread is alive
3. Check logs for refresh errors
4. Verify refresh interval is appropriate

---

## Conclusion

**stockr_backbone is the CORE ARCHITECTURAL FOUNDATION** of this application. It:

- ✅ Maintains internal stock database automatically
- ✅ Minimizes external API dependencies
- ✅ Auto-discovers and tracks new stocks
- ✅ Runs continuously without manual intervention
- ✅ Provides reliable, fast stock data access

**All planning, design, and implementation work must prioritize the reliable operation of this system.**

---

## Related Documentation

- `STOCK_DATA_ANALYSIS.md`: Detailed analysis of stock data flow
- `MVP_CLEANUP_REPORT.md`: Cleanup work performed
- `stockr_backbone/README.md`: Stockr backbone specific documentation

---

**Last Updated**: 2024-01-15  
**Status**: ✅ Fully Operational  
**Priority**: 🔴 CRITICAL - Core Architecture

