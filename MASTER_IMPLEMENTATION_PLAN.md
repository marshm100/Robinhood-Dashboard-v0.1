# Master Implementation Plan - Robinhood Dashboard

**Goal**: Complete all remaining work in manageable, atomic steps that can be executed flawlessly in single runs.

**Philosophy**: Each step should be:
- Self-contained (no dependencies on future steps)
- Testable immediately after completion
- Small enough to complete without errors
- Clear success criteria

---

## Phase 0: Critical Fixes (Blocks Everything)

### Step 0.1: Diagnose Missing Stock Price Data
**Time**: ~5 min | **Risk**: Low | **Files**: Read-only

**Task**: Query stockr_backbone database to identify which tickers are missing and why.

**Actions**:
1. Run SQL query to check if BITU, AGQ, TSLL, SBIT, TSDD exist in stocks table
2. Check if historical_prices has data for these tickers
3. Check the date range of available data
4. Document findings

**Success**: Know exactly which tickers are missing and why

---

### Step 0.2: Add Missing Tickers to stockr_backbone
**Time**: ~5 min | **Risk**: Low | **Files**: `stockr_backbone/tickers.txt`

**Task**: Add missing leveraged ETF tickers to the tracking list.

**Actions**:
1. Read current `tickers.txt`
2. Add missing tickers: BITU, AGQ, TSLL, SBIT, TSDD
3. Verify format matches existing entries

**Success**: `tickers.txt` contains all needed tickers

---

### Step 0.3: Trigger Stock Data Fetch
**Time**: ~10 min | **Risk**: Low | **Files**: None (run script)

**Task**: Run the stockr_backbone fetcher to populate missing ticker data.

**Actions**:
1. Run `python -m stockr_backbone.src.fetcher_standalone` or equivalent
2. Wait for completion
3. Verify data was fetched by querying database

**Success**: Missing tickers have historical price data

---

### Step 0.4: Add Graceful Fallback for Missing Prices
**Time**: ~10 min | **Risk**: Medium | **Files**: `src/services/portfolio_calculator.py`

**Task**: When stock price is unavailable, use transaction price as fallback.

**Actions**:
1. Find `get_stock_price_at_date()` method
2. Add fallback logic: if stockr returns None, query transaction table for price
3. Add logging when fallback is used

**Code Pattern**:
```python
def get_stock_price_at_date(self, ticker: str, date: str) -> Optional[float]:
    # Try stockr_backbone first
    price = stock_price_service.get_price_at_date(ticker, date)
    if price and price.get('close'):
        return price['close']
    
    # Fallback: use transaction price
    return self._get_transaction_price_fallback(ticker, date)
```

**Success**: Charts render even when stockr_backbone is missing data

---

### Step 0.5: Fix Text Rendering Issue
**Time**: ~10 min | **Risk**: Low | **Files**: `src/templates/*.html` or `src/static/css/`

**Task**: Investigate and fix truncated text in navigation.

**Actions**:
1. Search for CSS rules causing text truncation
2. Check for `letter-spacing`, `text-overflow`, or font issues
3. Fix the CSS or font loading issue
4. Test in browser

**Success**: All navigation text displays correctly

---

## Phase 1: Performance & Infrastructure

### Step 1.1: Add Batch Price Query Method
**Time**: ~15 min | **Risk**: Medium | **Files**: `src/services/stock_price_service.py`

**Task**: Add method to fetch prices for multiple tickers in one query.

**Actions**:
1. Add `get_prices_batch(tickers: List[str], start_date: str, end_date: str)` method
2. Use single SQL query with `IN` clause for tickers
3. Return Dict[ticker, DataFrame]
4. Add unit test

**Code Pattern**:
```python
def get_prices_batch(self, tickers: List[str], start_date: str, end_date: str) -> Dict[str, pd.DataFrame]:
    """Fetch prices for multiple tickers in single query"""
    placeholders = ','.join(['?' for _ in tickers])
    query = f"""
        SELECT s.symbol, hp.date, hp.open, hp.high, hp.low, hp.close, hp.volume
        FROM historical_prices hp
        JOIN stocks s ON hp.stock_id = s.id
        WHERE s.symbol IN ({placeholders})
        AND hp.date BETWEEN ? AND ?
        ORDER BY s.symbol, hp.date
    """
    # Execute and return grouped DataFrames
```

**Success**: Method returns data for multiple tickers efficiently

---

### Step 1.2: Add Price Cache to Portfolio Calculator
**Time**: ~15 min | **Risk**: Medium | **Files**: `src/services/portfolio_calculator.py`

**Task**: Add in-memory cache for prices to avoid repeated queries.

**Actions**:
1. Add `_price_cache: Dict[str, Dict[str, float]]` to `__init__`
2. Add `_preload_price_cache()` method that uses batch query
3. Add `_get_cached_price()` helper method
4. Call `_preload_price_cache()` at start of calculations

**Success**: Prices fetched once and reused throughout calculations

---

### Step 1.3: Add Date Sampling for Long Histories
**Time**: ~10 min | **Risk**: Low | **Files**: `src/services/portfolio_calculator.py`

**Task**: Sample dates for portfolios with long histories to reduce data points.

**Actions**:
1. Add `_sample_dates(start: date, end: date) -> List[date]` helper
2. Logic: >3 years = monthly, >1 year = weekly, else daily
3. Always include first, last, and transaction dates
4. Use in `get_portfolio_value_history()`

**Success**: Long portfolios load quickly with sampled data points

---

## Phase 2: Analysis Features

### Step 2.1: Implement Performance Attribution
**Time**: ~20 min | **Risk**: Medium | **Files**: `src/services/portfolio_calculator.py`, `src/routes/api.py`

**Task**: Calculate how each asset contributed to total return.

**Actions**:
1. Add `get_performance_attribution()` method
2. Calculate: `contribution = asset_return * average_weight`
3. Group by asset and by quarter
4. Add `/api/performance-attribution` endpoint
5. Return JSON with `by_asset` and `by_period` keys

**Success**: API returns real attribution data, not placeholder

---

### Step 2.2: Connect Performance Attribution to UI
**Time**: ~10 min | **Risk**: Low | **Files**: `src/templates/analysis.html`

**Task**: Update UI to fetch and display real attribution data.

**Actions**:
1. Find the attribution section in `analysis.html`
2. Replace placeholder with fetch to `/api/performance-attribution`
3. Render results in existing UI structure

**Success**: Attribution section shows real data

---

### Step 2.3: Implement Real Drawdown Analysis
**Time**: ~20 min | **Risk**: Medium | **Files**: `src/services/portfolio_calculator.py`

**Task**: Calculate actual drawdown metrics from portfolio history.

**Actions**:
1. Add `get_drawdown_analysis()` method
2. Calculate running peak: `peak = max(value_so_far)`
3. Calculate drawdown: `(current - peak) / peak * 100`
4. Identify drawdown periods (start, trough, recovery)
5. Return series and summary metrics

**Success**: Method returns actual drawdown data

---

### Step 2.4: Add Drawdown API Endpoint
**Time**: ~5 min | **Risk**: Low | **Files**: `src/routes/api.py`

**Task**: Expose drawdown analysis via API.

**Actions**:
1. Add `@app.get("/api/drawdown-analysis")` endpoint
2. Call `calculator.get_drawdown_analysis()`
3. Return JSON response

**Success**: `/api/drawdown-analysis` returns real data

---

### Step 2.5: Connect Drawdown to UI
**Time**: ~10 min | **Risk**: Low | **Files**: `src/templates/analysis.html`

**Task**: Update drawdown chart to use real data.

**Actions**:
1. Find `createDrawdownChart()` function
2. Replace simulated data with fetch to `/api/drawdown-analysis`
3. Map response to chart format

**Success**: Drawdown chart shows actual portfolio drawdowns

---

### Step 2.6: Add Sector Mapping Data
**Time**: ~10 min | **Risk**: Low | **Files**: `src/services/portfolio_calculator.py`

**Task**: Create sector mapping for common tickers.

**Actions**:
1. Add `SECTOR_MAPPING` constant with 50+ tickers
2. Include: Tech, Financials, Healthcare, Energy, Consumer, etc.
3. Map common ETFs and stocks

**Code Pattern**:
```python
SECTOR_MAPPING = {
    # Technology
    "AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Technology",
    "META": "Technology", "NVDA": "Technology", "AMD": "Technology",
    # Financials
    "JPM": "Financials", "BAC": "Financials", "GS": "Financials",
    # ... etc
}
```

**Success**: Mapping covers most common tickers

---

### Step 2.7: Implement Sector Allocation Method
**Time**: ~15 min | **Risk**: Low | **Files**: `src/services/portfolio_calculator.py`

**Task**: Calculate sector allocation from holdings.

**Actions**:
1. Add `get_sector_allocation()` method
2. Map each holding to sector using `SECTOR_MAPPING`
3. Sum weights by sector
4. Return `{"Technology": 45.2, "Financials": 20.1, ...}`

**Success**: Method returns sector breakdown

---

### Step 2.8: Update Sector Allocation in API
**Time**: ~5 min | **Risk**: Low | **Files**: `src/routes/api.py`

**Task**: Include sector allocation in portfolio overview.

**Actions**:
1. Find `/api/portfolio-overview` endpoint
2. Add `sector_allocation` to response using new method

**Success**: API returns sector data

---

## Phase 3: Comparison Features

### Step 3.1: Fix Benchmark Data Fetch
**Time**: ~10 min | **Risk**: Low | **Files**: `src/templates/comparison.html`

**Task**: Fetch real SPY data instead of hardcoded values.

**Actions**:
1. Find `createRiskReturnScatter()` function
2. Replace hardcoded SPY values with fetch to `/api/benchmarks/SPY`
3. Calculate return and volatility from historical data

**Success**: Scatter plot shows real SPY position

---

### Step 3.2: Implement Scenario Analysis Backend
**Time**: ~20 min | **Risk**: Medium | **Files**: `src/services/custom_portfolio_service.py`

**Task**: Add real scenario calculation logic.

**Actions**:
1. Add `run_scenario(portfolio_id, scenario_type, params)` method
2. Implement "rebalance" scenario: apply new weights, recalculate
3. Implement "add_asset" scenario: add ticker, reduce others
4. Return original vs scenario comparison

**Success**: Method calculates real scenario results

---

### Step 3.3: Add Scenario API Endpoint
**Time**: ~5 min | **Risk**: Low | **Files**: `src/routes/api.py`

**Task**: Expose scenario analysis via API.

**Actions**:
1. Add `@app.post("/api/scenarios")` endpoint
2. Accept portfolio_id, scenario_type, params
3. Return comparison results

**Success**: API accepts scenario requests

---

### Step 3.4: Connect Scenario UI to API
**Time**: ~10 min | **Risk**: Low | **Files**: `src/templates/comparison.html`

**Task**: Update scenario UI to use real API.

**Actions**:
1. Find `runScenario()` function
2. Replace fake data with fetch to `/api/scenarios`
3. Display real comparison results

**Success**: Scenario analysis shows calculated results

---

### Step 3.5: Add History to Portfolio Comparison
**Time**: ~15 min | **Risk**: Medium | **Files**: `src/services/custom_portfolio_service.py`

**Task**: Include historical value series in comparison results.

**Actions**:
1. Find `compare_portfolios()` method
2. Add `history` array to each portfolio in response
3. Calculate actual historical values for date range

**Success**: Comparison includes time series data

---

### Step 3.6: Update Comparative Timeline Chart
**Time**: ~10 min | **Risk**: Low | **Files**: `src/templates/comparison.html`

**Task**: Use real history data for timeline chart.

**Actions**:
1. Find `createComparativeTimeline()` function
2. Replace simulated data with `comparison.portfolios[].history`
3. Plot actual values over time

**Success**: Timeline shows real portfolio histories

---

## Phase 4: Bug Fixes & Polish

### Step 4.1: Fix Welcome Modal Persistence
**Time**: ~10 min | **Risk**: Low | **Files**: `src/templates/dashboard.html`

**Task**: Make welcome modal remember dismissal.

**Actions**:
1. Find modal JavaScript code
2. Verify localStorage key is unique
3. Check modal doesn't reset the key on load
4. Add `console.log` to debug if needed
5. Fix the persistence logic

**Success**: Modal only shows once per user

---

### Step 4.2: Add SPY to Default Tickers
**Time**: ~5 min | **Risk**: Low | **Files**: `stockr_backbone/tickers.txt`

**Task**: Ensure SPY is tracked for market conditions.

**Actions**:
1. Check if SPY is in `tickers.txt`
2. Add if missing
3. Run fetcher to populate data

**Success**: Market conditions section shows data

---

### Step 4.3: Add User-Friendly Error Messages
**Time**: ~15 min | **Risk**: Low | **Files**: `src/templates/dashboard.html`

**Task**: Show helpful messages when data is missing.

**Actions**:
1. Find chart rendering code
2. Add check for empty/zero data
3. Display message: "Stock price data unavailable for: [tickers]"
4. Suggest user action (wait for data fetch, etc.)

**Success**: Users understand why charts are empty

---

## Phase 5: Future Features (Optional Enhancements)

### Step 5.1: Add Performance Highlights Cards
**Time**: ~15 min | **Risk**: Low | **Files**: `src/templates/dashboard.html`

**Task**: Add prominent metrics display at top of dashboard.

**Actions**:
1. Add HTML section for metric cards
2. Style with color coding (green/red)
3. Populate from existing API data

**Success**: Key metrics visible at a glance

---

### Step 5.2: Add Trailing Returns Table
**Time**: ~20 min | **Risk**: Medium | **Files**: `src/services/portfolio_calculator.py`, `src/routes/api.py`

**Task**: Calculate returns for multiple time periods.

**Actions**:
1. Add `get_trailing_returns()` method
2. Calculate 3M, YTD, 1Y, 3Y, 5Y returns
3. Add API endpoint
4. Add UI table

**Success**: Dashboard shows multi-period returns

---

### Step 5.3: Add Log Scale Toggle
**Time**: ~10 min | **Risk**: Low | **Files**: `src/templates/dashboard.html`

**Task**: Add toggle button for logarithmic chart scale.

**Actions**:
1. Add toggle button to chart controls
2. On click, update Plotly layout: `yaxis.type = 'log'`
3. Re-render chart

**Success**: Users can toggle log scale

---

### Step 5.4: Add Monthly Returns Heatmap
**Time**: ~25 min | **Risk**: Medium | **Files**: Multiple

**Task**: Create calendar-style heatmap visualization.

**Actions**:
1. Add `get_monthly_returns()` method to calculator
2. Group returns by year/month
3. Add API endpoint
4. Add Plotly heatmap to analysis page

**Success**: Heatmap shows monthly performance patterns

---

## Execution Checklist

### Critical (Do First)
- [x] Step 0.1: Diagnose Missing Stock Price Data ✅ COMPLETE (All tickers have data!)
- [x] Step 0.2: Add Missing Tickers ✅ COMPLETE (Added AGQ, BITU, SBIT, TSDD, TSLL to tickers.txt)
- [x] Step 0.3: Trigger Stock Data Fetch ✅ COMPLETE (Fetcher ran, all tickers verified with data)
- [x] Step 0.4: Add Graceful Fallback ✅ COMPLETE (Transaction price fallback with logging)
- [x] Step 0.5: Fix Text Rendering ✅ COMPLETE (Fixed letter-spacing and font-family in nav-link)

### High Priority
- [x] Step 1.1: Batch Price Query ✅ COMPLETE (get_prices_batch() and get_prices_at_dates_batch() implemented with IN clause)
- [x] Step 1.2: Price Cache ✅ COMPLETE (_price_cache, _preload_price_cache(), _get_cached_price() added to PortfolioCalculator)
- [x] Step 1.3: Date Sampling ✅ COMPLETE (_sample_dates() with >3yr=monthly, >1yr=weekly, else=daily, always includes transaction dates)
- [x] Step 2.1: Performance Attribution ✅ COMPLETE (get_performance_attribution() + /api/performance-attribution endpoint already implemented)
- [x] Step 2.2: Connect Attribution UI ✅ COMPLETE (updatePerformanceAttribution() in analysis.html already fetches from API and renders data)
- [x] Step 2.3: Drawdown Analysis ✅ COMPLETE (get_drawdown_analysis() already computes running peak, drawdown%, periods, recovery)
- [x] Step 2.4: Drawdown API ✅ COMPLETE (/api/drawdown-analysis endpoint already calls get_drawdown_analysis())
- [ ] Step 2.5: Connect Drawdown UI
- [x] Step 2.6: Sector Mapping ✅ COMPLETE (SECTOR_MAPPING constant with 50+ tickers added to portfolio_calculator)
- [x] Step 2.7: Sector Allocation Method ✅ COMPLETE (get_sector_allocation() uses global SECTOR_MAPPING)
- [x] Step 2.8: Update Sector API ✅ COMPLETE (portfolio-overview now includes sector_allocation, sector_count, largest_sector)

### Medium Priority
- [ ] Step 3.1: Fix Benchmark Fetch
- [ ] Step 3.2: Scenario Backend
- [ ] Step 3.3: Scenario API
- [ ] Step 3.4: Connect Scenario UI
- [ ] Step 3.5: Comparison History
- [ ] Step 3.6: Update Timeline Chart

### Low Priority
- [ ] Step 4.1: Modal Persistence
- [ ] Step 4.2: Add SPY Ticker
- [ ] Step 4.3: Error Messages

### Optional
- [ ] Step 5.1: Highlights Cards
- [ ] Step 5.2: Trailing Returns
- [ ] Step 5.3: Log Scale Toggle
- [ ] Step 5.4: Monthly Heatmap

---

## Time Estimates

| Phase | Steps | Est. Time |
|-------|-------|-----------|
| Phase 0 (Critical) | 5 | ~40 min |
| Phase 1 (Performance) | 3 | ~40 min |
| Phase 2 (Analysis) | 8 | ~95 min |
| Phase 3 (Comparison) | 6 | ~70 min |
| Phase 4 (Polish) | 3 | ~30 min |
| Phase 5 (Future) | 4 | ~70 min |
| **Total** | **29** | **~6 hours** |

---

**Created**: January 2026
**Status**: Ready to Execute
