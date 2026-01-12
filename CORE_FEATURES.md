# Core Features Documentation

## Overview

This document describes the **CORE FEATURES** of the Robinhood Portfolio Analysis application. These features are not optional - they are essential components that define the application's purpose and value.

---

## ⭐ Core Feature 1: Custom Portfolio Creation & Backtesting

### What It Is

Custom Portfolio Creation allows users to create hypothetical portfolios with any asset allocation and backtest them against historical data to see how they would have performed.

### Why It's Core

- **Educational Value**: Users can learn about different investment strategies by testing them
- **Strategy Testing**: "What if" scenarios help users understand portfolio optimization
- **Decision Support**: Helps users make informed investment decisions
- **Benchmark Comparison**: Enables comparison against market benchmarks

### How It Works

1. **Create Portfolio**: Users specify asset allocations (e.g., 50% AAPL, 30% MSFT, 20% GOOGL)
2. **Choose Strategy**: Select lump sum or dollar-cost averaging (DCA)
3. **Backtest**: System simulates portfolio performance over historical date range
4. **View Results**: See total return, Sharpe ratio, max drawdown, and value over time

### Technical Implementation

- **Service**: `src/services/custom_portfolio_service.py`
- **Models**: `CustomPortfolio`, `PortfolioSnapshot` in `src/models.py`
- **API Endpoints**: 
  - `POST /api/custom-portfolios` - Create portfolio
  - `POST /api/custom-portfolios/{id}/backtest` - Backtest portfolio
- **Dependency**: Requires **stockr_backbone database** for historical price data

### User Interface

- **Page**: `/comparison` (Comparison page)
- **Tab**: "Create Portfolio"
- **Features**: 
  - Asset allocation input with percentage weights
  - Strategy selection (lump sum vs DCA)
  - Monthly investment amount for DCA
  - Portfolio preview

---

## ⭐ Core Feature 2: Portfolio Comparison

### What It Is

Portfolio Comparison allows users to compare multiple portfolios side-by-side, including:
- Custom portfolios (hypothetical)
- Actual Robinhood portfolio
- Market benchmarks (SPY, QQQ, etc.)

### Why It's Core

- **Performance Analysis**: See how different strategies compare
- **Benchmark Comparison**: Understand how your portfolio performs vs market
- **Optimization**: Identify which allocations would have performed best
- **Learning Tool**: Visual comparison helps understand investment concepts

### How It Works

1. **Select Portfolios**: Choose two or more portfolios to compare
2. **Automatic Benchmarks**: System automatically includes Robinhood portfolio and SPY benchmark
3. **Calculate Metrics**: System calculates performance metrics for each portfolio
4. **Visual Comparison**: Charts show value over time, returns, and risk metrics

### Technical Implementation

- **Service**: `src/services/custom_portfolio_service.py` (compare_portfolios method)
- **API Endpoint**: `POST /api/portfolio-comparison`
- **Benchmark Support**: `GET /api/benchmarks/{ticker}` for benchmark data
- **Dependency**: Requires **stockr_backbone database** for historical price data

### User Interface

- **Page**: `/comparison` (Comparison page)
- **Tab**: "Compare Portfolio"
- **Features**:
  - Portfolio selection dropdowns
  - Automatic inclusion of Robinhood portfolio
  - Automatic inclusion of SPY benchmark
  - Side-by-side performance charts
  - Metrics comparison table

---

## ⭐ Core Component: stockr_backbone Database

### What It Is

**stockr_backbone** is the foundational database system that provides historical stock price data for all core features. It is **NOT** an optional component - it is the **ESSENTIAL CORE** that enables:

1. Portfolio valuation calculations
2. Custom portfolio backtesting
3. Portfolio comparison
4. Benchmark comparison
5. All performance metrics

### Why It's Core

- **Data Foundation**: All price-dependent features require historical stock data
- **Automatic Operation**: Runs continuously in background, no manual intervention
- **Auto-Discovery**: Automatically tracks new stocks as they're encountered
- **Minimizes External Dependencies**: Reduces reliance on rate-limited external APIs

### How It Works

1. **Automatic Startup**: Starts automatically when application starts
2. **Background Maintenance**: Refreshes all tracked stocks every 60 minutes
3. **Auto-Discovery**: When a new ticker is queried, it's automatically added to tracking
4. **Primary Data Source**: First and primary source for all stock price queries

### Technical Implementation

- **Location**: `stockr_backbone/` directory
- **Database**: SQLite database with stocks and historical_prices tables
- **Service**: Background maintenance service runs in daemon thread
- **Integration**: Started automatically in `src/main.py` startup event
- **Status Monitoring**: `/health` and `/api/stockr-status` endpoints

### Status Verification

- **Health Check**: Visit `/health` - should show stockr_backbone status as "ok"
- **Detailed Status**: Visit `/api/stockr-status` for detailed maintenance service information
- **Critical**: If stockr_backbone is not running, portfolio valuations and comparisons will fail

---

## Feature Dependencies

### Dependency Chain

```
stockr_backbone Database
    ↓
Historical Stock Price Data
    ↓
Portfolio Valuation
    ↓
Custom Portfolio Backtesting
    ↓
Portfolio Comparison
    ↓
Benchmark Comparison
```

**All features depend on stockr_backbone database for historical price data.**

---

## API Endpoints Summary

### Custom Portfolio Endpoints
- `POST /api/custom-portfolios` - Create custom portfolio
- `GET /api/custom-portfolios` - List all portfolios
- `GET /api/custom-portfolios/{id}` - Get portfolio details
- `PUT /api/custom-portfolios/{id}` - Update portfolio
- `DELETE /api/custom-portfolios/{id}` - Delete portfolio
- `POST /api/custom-portfolios/{id}/backtest` - Backtest portfolio

### Comparison Endpoints
- `POST /api/portfolio-comparison` - Compare multiple portfolios
- `GET /api/benchmarks/{ticker}` - Get benchmark data

### Status Endpoints
- `GET /health` - Health check (includes stockr_backbone status)
- `GET /api/stockr-status` - Detailed stockr_backbone status

---

## User Workflows

### Workflow 1: Create and Backtest Custom Portfolio

1. Navigate to `/comparison` page
2. Click "Create Portfolio" tab
3. Enter portfolio name and description
4. Add assets with allocation percentages (must total 100%)
5. Choose strategy (lump sum or DCA)
6. Click "Create Portfolio"
7. Portfolio is saved and can be backtested

### Workflow 2: Compare Portfolios

1. Navigate to `/comparison` page
2. Click "Compare Portfolio" tab
3. Select two portfolios from dropdowns
4. System automatically includes:
   - Your Robinhood portfolio
   - SPY benchmark
5. Click "Compare Portfolios"
6. View side-by-side comparison with charts and metrics

### Workflow 3: Compare Against Benchmark

1. Create a custom portfolio or use existing one
2. Go to comparison page
3. Select custom portfolio and Robinhood portfolio
4. System automatically includes SPY benchmark
5. View comparison to see how portfolios performed vs market

---

## Troubleshooting

### Custom Portfolio Creation Fails

- **Check**: stockr_backbone database is running (`/health` endpoint)
- **Check**: Stock tickers exist in stockr_backbone database
- **Check**: Date range has historical data available

### Portfolio Comparison Returns Empty Data

- **Check**: stockr_backbone database is running
- **Check**: Historical price data exists for date range
- **Check**: Portfolios have valid asset allocations

### Benchmarks Not Loading

- **Check**: stockr_backbone database has SPY (or other benchmark) data
- **Check**: Date range is valid
- **Check**: stockr_backbone maintenance service is running

---

## Conclusion

Custom Portfolio Creation, Portfolio Comparison, and the stockr_backbone Database are **CORE FEATURES** that define the application's purpose. They are not optional - they are essential components that work together to provide users with powerful portfolio analysis and comparison capabilities.

**Without stockr_backbone, none of these features would be possible.**

