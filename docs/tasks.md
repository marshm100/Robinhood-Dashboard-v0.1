# Tasks for Robinhood Dashboard

## Core Functionality

Tasks related to setting up the basic backend and frontend infrastructure:

1. Add a POST /upload route in backend/index.js to receive a CSV file, parse it with Papa Parse, and store transactions in SQLite (columns: activity_date, ticker, trans_code, quantity, price, amount).
2. Create a transactions table in SQLite in backend/index.js with columns: activity_date, ticker, trans_code, quantity, price, amount.
3. Add a GET /transactions route in backend/index.js to return all transactions from SQLite as JSON.
4. Update frontend/src/App.jsx to send the uploaded CSV to <http://localhost:3001/upload> using fetch, and display a success message.
5. Add a GET /stock-prices route in backend/index.js to fetch historical prices from Alpha Vantage (TIME_SERIES_DAILY) for a given ticker, cache results in SQLite (table: stock_prices, columns: ticker, date, close_price), and return the data as JSON.
6. Create a stock_prices table in SQLite in backend/index.js with columns: ticker, date, close_price.
7. Add a function in backend/index.js to calculate daily portfolio value: combine transactions and stock prices, account for buys/sells and cash flows (RTP, MISC), and return a time series (date, value).
8. Add a GET /portfolio-value route in backend/index.js to return the daily portfolio value as JSON.

## Portfolio Configuration and Composition

Tasks for implementing portfolio setup and displaying composition:

1. Add a form in frontend/src/App.jsx for portfolio configuration: inputs for Total Investment Amount and Asset Allocation Percentages (as a percentage per ticker), styled with Tailwind CSS in a cyberpunk theme (neon colors, glowing effects).
2. Add a POST /portfolio-config route in backend/index.js to save portfolio configuration (total investment, allocations) in SQLite (table: portfolio_config, columns: total_investment, ticker, allocation_percentage).
3. Create a portfolio_config table in SQLite in backend/index.js with columns: total_investment, ticker, allocation_percentage.
4. Add a GET /portfolio-composition route in backend/index.js to return portfolio composition (ticker, name, allocation percentage) as JSON, using stored allocations.
5. Display portfolio composition in frontend/src/App.jsx as a table (ticker, name, allocation percentage), styled with Tailwind CSS in a cyberpunk theme.

Tasks for calculating and displaying key portfolio metrics:

1. Add functions in backend/index.js to calculate portfolio summary metrics: Time Period, Start Balance, End Balance, Annualized Return (CAGR), Standard Deviation (Annualized), Best/Worst Year Return, Maximum Drawdown, Sharpe/Sortino Ratio, Benchmark Correlation, Cumulative Return, Percentage of Positive Months, Best/Worst Year, Maximum Drawdown Period, Recovery Time, Upside/Downside Capture Ratio.
2. Add a GET /portfolio-summary route in backend/index.js to return the portfolio summary metrics as JSON.
3. Display portfolio summary metrics in frontend/src/App.jsx as a table, styled with Tailwind CSS in a cyberpunk theme.

## Trailing Returns

Tasks for implementing trailing return analysis:

1. Add a function in backend/index.js to calculate trailing returns for periods: 3 Month, Year-to-Date, 1 Year, 3 Year, 5 Year, 10 Year, Full Period (Total Return, Annualized Return, Annualized Standard Deviation).
2. Add a GET /trailing-returns route in backend/index.js to return trailing returns as JSON.
3. Display trailing returns in frontend/src/App.jsx as a bar chart using Chart.js, styled with Tailwind CSS in a cyberpunk theme.

## Holdings Based Style Analysis

Tasks for implementing style analysis features:

1. Add functions in backend/index.js to calculate holdings style analysis: Category, Weight, Yield (SEC/TTM), Expense Ratio (Net/Gross), P/E, Duration, Contribution to Return/Risk, Total Portfolio Yield (SEC/TTM), Total Portfolio Expense Ratio (Net/Gross), Total Portfolio P/E, Duration, Contribution to Return.
2. Add a GET /style-analysis route in backend/index.js to return style analysis data as JSON.
3. Display style analysis in frontend/src/App.jsx as a table, styled with Tailwind CSS in a cyberpunk theme.

## Fixed Income Maturity

Tasks for displaying fixed income data:

1. Add a GET /fundamentals-date route in backend/index.js to return a static Fundamentals Data Date (e.g., current date) as JSON.
2. Display Fundamentals Data Date in frontend/src/App.jsx as a text field, styled with Tailwind CSS in a cyberpunk theme.

## Active Return Contribution

Tasks for analyzing active returns:

1. Add a function in backend/index.js to calculate Active Return by Asset for periods: 1 Day, 1 Week, 1 Month, 3 Month, 6 Month, 1-year, 3-year, 5-year, 10-year, Full Period.
2. Add a GET /active-return route in backend/index.js to return active return data as JSON.
3. Display active return data in frontend/src/App.jsx as a table, styled with Tailwind CSS in a cyberpunk theme.

## Up vs. Down Market Performance

Tasks for analyzing market performance in different conditions:

1. Add a function in backend/index.js to calculate Up vs. Down Market Performance: Market Type (Up, Down, Total), Occurrences, Percentage Above Benchmark, Average Active Return Above/Below Benchmark, Total Average Active Return.
2. Add a GET /market-performance route in backend/index.js to return market performance data as JSON.
3. Display market performance in frontend/src/App.jsx as a bar chart using Chart.js, styled with Tailwind CSS in a cyberpunk theme.

## Risk and Return Metrics

Tasks for implementing detailed risk analysis:

1. Add functions in backend/index.js to calculate risk and return metrics: Arithmetic/Geometric Mean (Monthly/Annualized), Standard/Downside Deviation (Monthly), Beta, Alpha (Annualized), R-Squared, Treynor/Calmar/Modigliani-Modigliani Measure, Active Return, Tracking Error, Information Ratio, Skewness, Excess Kurtosis, Historical/Analytical/Conditional Value-at-Risk (5%), Safe/Perpetual Withdrawal Rate, Positive Periods, Gain/Loss Ratio.
2. Add a GET /risk-return route in backend/index.js to return risk and return metrics as JSON.
3. Display risk and return metrics in frontend/src/App.jsx as a table, styled with Tailwind CSS in a cyberpunk theme.
4. Add a scatter plot in frontend/src/App.jsx for Risk-Return (risk vs. return for portfolio and benchmark) using Chart.js, styled with Tailwind CSS in a cyberpunk theme.

## Annual and Monthly Returns

Tasks for time-based return analysis:

1. Add functions in backend/index.js to calculate Annual Returns: Year, Inflation Rate, Portfolio Return/Balance, Benchmark Return/Balance, Individual Asset Returns.
2. Add a GET /annual-returns route in backend/index.js to return annual returns as JSON.
3. Display annual returns in frontend/src/App.jsx as a bar chart using Chart.js, styled with Tailwind CSS in a cyberpunk theme.
4. Add functions in backend/index.js to calculate Monthly Returns: Year-Month, Portfolio Monthly Return/Balance, Benchmark Monthly Return/Balance, Individual Asset Monthly Returns.
5. Add a GET /monthly-returns route in backend/index.js to return monthly returns as JSON.
6. Display monthly returns in frontend/src/App.jsx as a time series chart using Chart.js, styled with Tailwind CSS in a cyberpunk theme.

## Graphs and Visualizations

Tasks for implementing key visual components:

1. Add a Portfolio Growth Chart in frontend/src/App.jsx using Chart.js (line chart of portfolio and benchmark over time), styled with Tailwind CSS in a cyberpunk theme.
2. Add a Drawdown Chart in frontend/src/App.jsx using Chart.js (drawdown percentage over time), styled with Tailwind CSS in a cyberpunk theme.
3. Add an Asset Allocation Pie Chart in frontend/src/App.jsx using Chart.js, styled with Tailwind CSS in a cyberpunk theme.

## Additional Features

Tasks for enhancing the user experience:

1. Add a Benchmark Selection dropdown in frontend/src/App.jsx (e.g., S&P 500, NASDAQ), styled with Tailwind CSS in a cyberpunk theme.
2. Add Insights Links in frontend/src/App.jsx as pop-ups for specific periods (placeholder links), styled with Tailwind CSS in a cyberpunk theme.
3. Add a Data Constraints Note in frontend/src/App.jsx (e.g., 'Data limited to available asset history'), styled with Tailwind CSS in a cyberpunk theme.
4. Add a Fundamentals Data Source attribution in frontend/src/App.jsx (e.g., 'Data from Alpha Vantage'), styled with Tailwind CSS in a cyberpunk theme.
5. Add an Interactive Timeline in frontend/src/App.jsx for market drivers (placeholder with static events), styled with Tailwind CSS in a cyberpunk theme.
