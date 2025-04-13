# Implementation Steps

## Step 1: Clean up backend/index.js (Focus on Portfolio Value Calculation)

1. Find and remove any hardcoded portfolio values or transactions
2. Ensure the calculatePortfolioValue function only uses transactions from the database
3. Remove any fallback demo data used when CSV isn't uploaded yet

## Step 2: Clean up Financial Metrics Calculations

1. Find and remove dummy data in metrics calculations like:
   - Total Return calculation
   - Annualized Return calculation  
   - Volatility calculation
   - Maximum Drawdown calculation
   - Sharpe Ratio calculation

## Step 3: Clean up Benchmark Comparisons

1. Identify any hardcoded benchmark data
2. Ensure benchmarks are properly fetched from APIs rather than using static test data
3. Remove any fallback visualization data for benchmarks

## Step 4: Clean up Frontend Visualization Components

1. In App.jsx, remove any hardcoded chart data
2. Ensure charts only display data from actual API responses
3. Remove placeholder values in portfolio summary metrics

## Step 5: Implement Proper Empty State Handling

1. Add proper UI messaging when no CSV is uploaded yet
2. Show appropriate loading states while calculations are processing
3. Replace dummy chart data with empty state visualizations

## Step 6: Verify Data Flow

1. Confirm transactions from CSV are properly stored in SQLite
2. Verify portfolio calculations use only actual transaction data
3. Test the complete flow from CSV upload to visualization rendering
