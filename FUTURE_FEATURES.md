# Future Features - Portfolio Visualizer Enhancements

This document outlines features identified from Portfolio Visualizer that can be implemented to enhance the Robinhood Dashboard.

## Priority 1: Performance Highlights Section

### Description
Add a prominent section displaying key portfolio metrics at a glance.

### Features
- **Annualized Return (CAGR)**: Display with color coding (green positive, red negative)
- **Standard Deviation**: Risk metric with tooltip explanation
- **Maximum Drawdown**: Worst peak-to-trough decline with dates
- **Sharpe Ratio**: Risk-adjusted return metric
- **Sortino Ratio**: Downside risk-adjusted return

### Implementation Notes
- Already have calculations in `portfolio_calculator.py`
- Need to create new dashboard component for display
- Consider using cards with color gradients based on performance

---

## Priority 2: Trailing Returns Table

### Description
Multi-period returns comparison showing performance over various time horizons.

### Features
- **Time Periods**: 3 Month, YTD, 1 Year, 3 Year, 5 Year, 10 Year, Full
- **Metrics per Period**:
  - Total Return
  - Annualized Return
  - Annualized Standard Deviation
- **Benchmark Comparison**: Side-by-side with S&P 500 or custom benchmark

### Implementation Notes
- Requires date range filtering in calculator
- Need to handle cases where portfolio doesn't have enough history
- Consider lazy loading for longer time periods

---

## Priority 3: Enhanced Chart Controls

### Description
Add interactive controls to the portfolio growth chart.

### Features
- **Logarithmic Scale Toggle**: Better visualization for long-term growth
- **Inflation-Adjusted Toggle**: Real returns vs nominal returns
- **Custom Date Range Selection**: Allow users to zoom into specific periods
- **Benchmark Overlay**: Show S&P 500 or custom benchmark on same chart

### Implementation Notes
- Plotly supports log scale via `yaxis_type='log'`
- Need CPI data for inflation adjustment
- Consider using Plotly's built-in range slider

---

## Priority 4: Monthly Returns Heatmap

### Description
Visual calendar-style heatmap showing monthly returns by year.

### Features
- **Color Gradient**: Red (negative) to Green (positive)
- **Year Rows, Month Columns**: Traditional heatmap layout
- **Hover Details**: Show exact return percentage
- **Annual Summary**: Row totals showing yearly returns

### Implementation Notes
- Use Plotly heatmap or custom CSS grid
- Group existing transaction data by month
- Consider using diverging color scale centered at 0

---

## Priority 5: Drawdown Analysis Table

### Description
Detailed table showing all significant drawdown periods.

### Features
- **Columns**:
  - Drawdown Rank
  - Start Date
  - End Date (trough)
  - Recovery Date
  - Depth (%)
  - Length (days)
  - Recovery Length (days)
- **Sorting**: By depth or length
- **Highlighting**: Emphasize current/ongoing drawdowns

### Implementation Notes
- Need to track peak-to-trough-to-recovery cycles
- Store calculated drawdown periods for performance
- Consider pagination for many drawdowns

---

## Priority 6: Rolling Returns Analysis

### Description
Show how returns vary over rolling time periods.

### Features
- **Rolling Windows**: 1 Year, 3 Year, 5 Year
- **Statistics**:
  - Average Rolling Return
  - Best Rolling Period
  - Worst Rolling Period
  - Percentage of Positive Periods
- **Chart**: Line chart showing rolling returns over time

### Implementation Notes
- Computationally intensive for long histories
- Consider caching rolling calculations
- Use pandas rolling window functions

---

## Priority 7: Asset Contribution Analysis

### Description
Show how each holding contributed to overall portfolio returns.

### Features
- **Contribution Metrics**:
  - Return Contribution (%)
  - Weight at Start
  - Weight at End
  - Individual Return
- **Sorting**: By contribution (positive first)
- **Time Period Selection**: Match trailing returns periods

### Implementation Notes
- Requires tracking weights over time
- Need to handle additions/removals during period
- Consider Brinson attribution methodology

---

## Implementation Roadmap

### Phase 1 (Quick Wins)
1. Performance Highlights Section - uses existing calculations
2. Enhanced Chart Controls - mostly frontend changes

### Phase 2 (Medium Effort)
3. Trailing Returns Table - requires date filtering
4. Monthly Returns Heatmap - new visualization

### Phase 3 (Complex)
5. Drawdown Analysis Table - new calculations needed
6. Rolling Returns Analysis - computational complexity
7. Asset Contribution Analysis - attribution methodology

---

## Technical Considerations

### Backend Changes
- Add new API endpoints for each feature
- Consider caching expensive calculations
- Add date range parameters to existing endpoints

### Frontend Changes
- Create reusable table components
- Add chart configuration options
- Implement responsive designs for mobile

### Data Requirements
- CPI data for inflation adjustment (external API)
- Benchmark data (S&P 500, etc.) - already in stockr_backbone
- Portfolio snapshots for historical weights - partially implemented

---

## References

- Original Portfolio Visualizer: https://www.portfoliovisualizer.com/backtest-portfolio
- Source analysis in transcript: `9a7cb02c-4abc-4128-bb49-9c50e915412b.txt`
