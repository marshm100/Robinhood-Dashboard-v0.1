# Robinhood Dashboard - Comprehensive Development Plan

**Created**: 2025-12-16  
**Status**: Active  
**Purpose**: Complete all missing features and fix known issues

---

## Executive Summary

This plan addresses all features hinted at in the UI that are either broken, use placeholder data, or have not been implemented. The work is organized into 4 phases by priority and dependency.

---

## Phase 1: Performance & Infrastructure (CRITICAL)

### 1.1 Batch Stock Price Queries
**Priority**: CRITICAL  
**Impact**: All API endpoints timeout without this fix  
**File**: `src/services/stock_price_service.py`

**Current Problem**: Individual queries for each ticker/date combination cause 30+ second API timeouts.

**Implementation**:
```python
def get_prices_batch(
    self, 
    tickers: List[str], 
    start_date: str, 
    end_date: str
) -> Dict[str, pd.DataFrame]:
    """
    Fetch all prices for multiple tickers in date range with single query.
    Returns dict of ticker -> DataFrame with columns: date, open, high, low, close, volume
    """
```

**Tasks**:
- [ ] Add `get_prices_batch()` method to `StockPriceService`
- [ ] Query all tickers in single SQL statement with date range filter
- [ ] Return indexed DataFrame for O(1) lookups
- [ ] Update `PortfolioCalculator` to use batch queries

---

### 1.2 In-Memory Price Cache
**Priority**: CRITICAL  
**File**: `src/services/portfolio_calculator.py`

**Current Problem**: Same prices fetched repeatedly during calculations.

**Implementation**:
```python
class PortfolioCalculator:
    def __init__(self, db):
        self._price_cache: Dict[str, Dict[str, float]] = {}  # ticker -> {date -> price}
        
    def _get_cached_price(self, ticker: str, date: str) -> Optional[float]:
        """Get price from cache or fetch and cache"""
```

**Tasks**:
- [ ] Add `_price_cache` dict to `PortfolioCalculator.__init__`
- [ ] Create `_get_cached_price()` helper method
- [ ] Pre-populate cache using batch query at calculation start
- [ ] Replace all individual price lookups with cached version

---

### 1.3 Date Sampling for History
**Priority**: HIGH  
**File**: `src/services/portfolio_calculator.py`

**Current Problem**: Calculates value for every single day, creating thousands of data points.

**Implementation**:
- For date ranges > 1 year: sample weekly
- For date ranges > 3 years: sample monthly
- Always include first/last dates and transaction dates

**Tasks**:
- [ ] Add `_sample_dates()` helper method
- [ ] Update `get_portfolio_value_history()` to use sampling
- [ ] Ensure transaction dates are always included in samples

---

## Phase 2: Analysis Features (HIGH PRIORITY)

### 2.1 Performance Attribution
**Priority**: HIGH  
**Files**: `src/services/portfolio_calculator.py`, `src/templates/analysis.html`

**Current State**: Shows "Feature under development" placeholder.

**Implementation**:
```python
def get_performance_attribution(self) -> Dict[str, Any]:
    """
    Calculate contribution of each asset to total portfolio return.
    
    Returns:
        {
            "by_asset": {
                "AAPL": {"contribution": 5.2, "weight": 0.30, "return": 17.3},
                ...
            },
            "by_period": {
                "2024-Q1": {"return": 8.5, "top_contributor": "NVDA"},
                ...
            }
        }
    """
```

**Tasks**:
- [ ] Add `get_performance_attribution()` to `PortfolioCalculator`
- [ ] Calculate weighted contribution: `asset_return * asset_weight`
- [ ] Group by time periods (quarterly)
- [ ] Add `/api/performance-attribution` endpoint
- [ ] Update `analysis.html` to fetch and display real data

---

### 2.2 Real Drawdown Analysis
**Priority**: HIGH  
**Files**: `src/services/portfolio_calculator.py`, `src/templates/analysis.html`

**Current State**: Uses simulated/fake data with random patterns.

**Implementation**:
```python
def get_drawdown_analysis(self) -> Dict[str, Any]:
    """
    Calculate actual drawdown metrics from portfolio history.
    
    Returns:
        {
            "drawdown_series": [{"date": "2024-01-15", "drawdown": -5.2}, ...],
            "max_drawdown": -15.3,
            "max_drawdown_date": "2024-03-10",
            "recovery_time_days": 45,
            "drawdown_periods": [
                {"start": "2024-03-01", "end": "2024-04-15", "depth": -15.3}
            ]
        }
    """
```

**Tasks**:
- [ ] Add `get_drawdown_analysis()` to `PortfolioCalculator`
- [ ] Calculate running max (peak) of portfolio value
- [ ] Calculate drawdown as `(current - peak) / peak * 100`
- [ ] Identify drawdown periods (start, bottom, recovery)
- [ ] Calculate recovery time for each drawdown
- [ ] Add `/api/drawdown-analysis` endpoint
- [ ] Update `createDrawdownChart()` in `analysis.html` to use real data

---

### 2.3 Sector Allocation
**Priority**: MEDIUM  
**Files**: `src/services/portfolio_calculator.py`, `src/services/stock_price_service.py`

**Current State**: Returns empty `sector_allocation` object.

**Implementation**:
Create sector mapping for common tickers:
```python
SECTOR_MAPPING = {
    "AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Technology",
    "AMZN": "Consumer Discretionary", "TSLA": "Consumer Discretionary",
    "JPM": "Financials", "BAC": "Financials",
    "JNJ": "Healthcare", "PFE": "Healthcare",
    "XOM": "Energy", "CVX": "Energy",
    # ... etc
}
```

**Tasks**:
- [ ] Create `SECTOR_MAPPING` constant with 50+ common tickers
- [ ] Add `get_sector_allocation()` method
- [ ] Group holdings by sector and sum weights
- [ ] Return sector breakdown with "Unknown" for unmapped tickers
- [ ] Update `updateSectorAllocation()` in `analysis.html`

---

## Phase 3: Comparison Features (MEDIUM PRIORITY)

### 3.1 Investment Scenario Analysis
**Priority**: MEDIUM  
**Files**: `src/services/custom_portfolio_service.py`, `src/routes/api.py`, `src/templates/comparison.html`

**Current State**: Uses hardcoded fake simulation data.

**Implementation**:
```python
def run_scenario(
    self,
    portfolio_id: int,
    scenario_type: str,  # "rebalance", "add_asset", "reduce_position", "market_change"
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Run what-if scenario analysis on a portfolio.
    
    Returns:
        {
            "original": {"return": 15.2, "risk": 12.5, "sharpe": 1.21},
            "scenario": {"return": 18.7, "risk": 14.2, "sharpe": 1.32},
            "difference": {"return": 3.5, "risk": 1.7, "sharpe": 0.11},
            "projected_history": [...]
        }
    """
```

**Scenario Types**:
1. **Rebalance**: Apply new target weights, recalculate metrics
2. **Add Asset**: Add new ticker with specified weight, reduce others proportionally
3. **Reduce Position**: Reduce specific ticker, redistribute to others
4. **Market Change**: Apply uniform % change to all holdings

**Tasks**:
- [ ] Add `run_scenario()` to `CustomPortfolioService`
- [ ] Implement each scenario type calculation
- [ ] Add `/api/scenarios` POST endpoint
- [ ] Update `runScenario()` in `comparison.html` to call API
- [ ] Display real comparison results

---

### 3.2 Real Comparative Timeline
**Priority**: MEDIUM  
**Files**: `src/services/custom_portfolio_service.py`, `src/templates/comparison.html`

**Current State**: Uses simulated data with random noise.

**Implementation**:
Extend `compare_portfolios()` to return actual historical values:
```python
def compare_portfolios(...) -> Dict[str, Any]:
    return {
        "portfolios": [
            {
                "name": "Portfolio 1",
                "history": [
                    {"date": "2024-01-01", "value": 10000},
                    {"date": "2024-01-08", "value": 10150},
                    ...
                ],
                "total_return": 15.2,
                "sharpe_ratio": 1.21
            },
            ...
        ]
    }
```

**Tasks**:
- [ ] Update `compare_portfolios()` to include `history` array
- [ ] Calculate actual historical values for each portfolio
- [ ] Update `createComparativeTimeline()` to use `comparison.portfolios[].history`

---

### 3.3 Real Benchmark Data
**Priority**: MEDIUM  
**Files**: `src/templates/comparison.html`

**Current State**: Risk-return scatter uses hardcoded S&P 500 values (8.5% return, 15% volatility).

**Tasks**:
- [ ] Fetch real SPY data from `/api/benchmarks/SPY`
- [ ] Calculate actual benchmark return and volatility
- [ ] Update `createRiskReturnScatter()` to use fetched data

---

## Phase 4: Bug Fixes & Polish (LOW PRIORITY)

### 4.1 Welcome Modal Persistence
**Priority**: LOW  
**File**: `src/templates/dashboard.html`

**Current Problem**: Modal reappears on every page refresh.

**Tasks**:
- [ ] Verify localStorage key is unique (`robinhood_dashboard_welcome_dismissed`)
- [ ] Check modal is not resetting the key on load
- [ ] Add console logging to debug localStorage state
- [ ] Test in incognito mode to verify fix

---

### 4.2 Market Conditions Data
**Priority**: LOW  
**Dependency**: Requires SPY data in stockr_backbone database

**Current Problem**: Shows "Market conditions data is not available" when SPY not tracked.

**Tasks**:
- [ ] Ensure SPY is in stockr_backbone tickers list
- [ ] Run stockr_backbone data fetch for SPY
- [ ] Verify market conditions API returns data
- [ ] Add fallback message if SPY data unavailable

---

## Implementation Order

```
Week 1: Phase 1 (Performance)
├── 1.1 Batch queries
├── 1.2 Price cache
└── 1.3 Date sampling

Week 2: Phase 2 (Analysis)
├── 2.1 Performance attribution
├── 2.2 Drawdown analysis
└── 2.3 Sector allocation

Week 3: Phase 3 (Comparison)
├── 3.1 Scenario analysis
├── 3.2 Comparative timeline
└── 3.3 Benchmark data

Week 4: Phase 4 (Polish)
├── 4.1 Modal persistence
└── 4.2 Market conditions
```

---

## Success Criteria

| Metric | Target |
|--------|--------|
| API response time | < 5 seconds |
| Dashboard load time | < 10 seconds |
| Analysis tabs | All show real data |
| Comparison scenarios | Return calculated results |
| No placeholder text | 0 instances of "under development" |
| No fake data | 0 simulated/random data in production |

---

## Files to Modify

| File | Changes |
|------|---------|
| `src/services/stock_price_service.py` | Add batch query, sector mapping |
| `src/services/portfolio_calculator.py` | Add cache, attribution, drawdown |
| `src/services/custom_portfolio_service.py` | Add scenarios, timeline history |
| `src/routes/api.py` | Add new endpoints |
| `src/templates/analysis.html` | Connect to real APIs |
| `src/templates/comparison.html` | Connect to real APIs |
| `src/templates/dashboard.html` | Fix modal persistence |

---

**Last Updated**: 2025-12-16

