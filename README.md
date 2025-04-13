# Robinhood Dashboard

## App Vision

Robinhood Dashboard is a simple web app that helps everyday investors understand their Robinhood trading history. Users can upload a CSV file from Robinhood, and the app will turn it into a clear picture of their portfolio's performance over time. It shows how much money they've made or lost, key stats like total return and risk, and cool charts like portfolio growth and asset breakdown. The app uses free tools like React for the interface, Node.js for the backend, and APIs like Alpha Vantage for stock prices, all hosted on Vercel for free. My goal is to make it easy to use, even for beginners like me, while giving powerful financial insights.

## Key Features

- **Upload CSV**: Let users upload their Robinhood transaction CSV file through a button on the webpage.
- **Parse Transactions**: Read the CSV to pull out details like date, ticker (stock symbol), buy/sell type, quantity, and price.
- **Calculate Portfolio Value**: Figure out the daily value of the portfolio by combining stock holdings with historical prices from Alpha Vantage.
- **Financial Metrics**: Show simple stats like:
  - Total Return (how much the portfolio grew overall).
  - Annualized Return (average yearly growth).
  - Volatility (how risky it is).
  - Maximum Drawdown (biggest drop in value).
  - Sharpe Ratio (return vs. risk).
- **Interactive Charts**: Display visuals like:
  - Portfolio Growth (line chart showing value over time).
  - Asset Allocation (pie chart of stocks in the portfolio).
  - Annual Returns (bar chart of yearly performance).
- **Simple Design**: Use Tailwind CSS to make it look clean and work on phones too.

## CSV Structure

- **File**: See `sample_transactions.csv` for an example.
- **Columns**:
  - `Activity Date`: When the transaction happened (e.g., "3/10/2025").
  - `Process Date`: When it was processed (e.g., "3/10/2025").
  - `Settle Date`: When it settled (e.g., "3/11/2025").
  - `Instrument`: Stock ticker (e.g., "BITU") or empty for non-trade entries.
  - `Description`: Details like stock name or transaction type (e.g., "ProShares Ultra Bitcoin ETF CUSIP: 74349Y704").
  - `Trans Code`: Type of transaction (e.g., "Buy", "Sell", "CDIV" for dividends, "RTP" for transfers, "MISC" for rewards).
  - `Quantity`: Number of shares (e.g., "2.085796"), empty for non-trades.
  - `Price`: Price per share (e.g., "$31.97"), empty for non-trades.
  - `Amount`: Total value (e.g., "($66.69)" for debits, "$457.92" for credits).
- **Notes**:
  - Dates are in MM/DD/YYYY format.
  - Prices and amounts include "$" and may have parentheses for negative values (e.g., "($14.97)").
  - Empty `Instrument` means it's a cash transaction (deposit, withdrawal, reward).

## API Keys and Usage

- **Alpha Vantage**:
  - **Purpose**: Fetch historical stock prices (e.g., daily adjusted prices).
  - **Key**: Stored in `backend/.env` as `ALPHA_VANTAGE_KEY`.
  - **Endpoint**: Use `TIME_SERIES_DAILY` (e.g., `https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=BITU&apikey=${process.env.ALPHA_VANTAGE_KEY}`).
  - **Limits**: 5 calls/minute, 500/day. Cache results in SQLite to stay within limits.
  - **Sample Response**: `{ "Meta Data": {...}, "Time Series (Daily)": {"2025-03-10": {"4. close": "31.97"}} }`.
- **Finnhub**:
  - **Purpose**: Optional real-time quotes or additional data.
  - **Key**: Stored in `backend/.env` as `FINNHUB_KEY`.
  - **Endpoint**: Use `/quote` (e.g., `https://finnhub.io/api/v1/quote?symbol=BITU&token=${process.env.FINNHUB_KEY}`).
  - **Limits**: 60 calls/minute, but limited historical data in free tier.
  - **Sample Response**: `{ "c": 31.97, "h": 32.00, "l": 31.50, "o": 31.75, "pc": 31.90 }`.

## Tech Stack

- **Frontend**:
  - **React**: Build the UI with Vite for fast development.
  - **Tailwind CSS**: Style components, keep it responsive.
  - **Chart.js**: Create line, pie, and bar charts (via `react-chartjs-2`).
- **Backend**:
  - **Node.js**: Run the server.
  - **Express.js**: Handle API routes (e.g., CSV upload).
  - **Papa Parse**: Parse CSV files (installed as `papaparse`).
  - **SQLite**: Store parsed transactions and cached API data.
  - **dotenv**: Load API keys from `.env`.
- **Deployment**: Vercel (free tier for hosting frontend and backend).

## Aesthetic and Features

- **Aesthetic Images**: See `docs/ui_aesthetic_1.jpg` through `docs/ui_aesthetic_15.jpg` for style inspiration.
- **Aesthetic Notes**:
  - Aim for a cyberpunk, retro-futuristic vibe: neon greens, reds, and oranges on a black background.
  - Use glowing, holographic effects for charts and text (e.g., Tailwind CSS with shadows, opacity).
  - Monospace fonts for a terminal-like feel (e.g., Tailwind's `font-mono`).
  - Dense, grid-like layout with overlapping panels, inspired by sci-fi control rooms.
  - Add subtle CRT effects (e.g., scanlines via CSS) if possible.
- **Design Notes**: Exact layout is flexible, but include all features below. Use Tailwind CSS for styling and Chart.js for visualizations. Ensure responsiveness for mobile.
- **Full Feature List**:
  - **Portfolio Model Configuration**:
    - Total Investment Amount
    - Asset Allocation Percentages
    - User CSV Upload
  - **Sample Portfolio Composition**:
    - Ticker
    - Name
    - Allocation Percentage
  - **Portfolio Analysis Results (Summary)**:
    - Time Period
    - Start Balance
    - End Balance
    - Annualized Return (CAGR)
    - Standard Deviation (Annualized)
    - Best Year Return
    - Worst Year Return
    - Maximum Drawdown
    - Sharpe Ratio
    - Sortino Ratio
    - Benchmark Correlation
    - Cumulative Return
    - Percentage of Positive Months
    - Best Year
    - Worst Year
    - Maximum Drawdown Period
    - Recovery Time
    - Upside Capture Ratio
    - Downside Capture Ratio
  - **Trailing Returns**:
    - Trailing Return Periods (3 Month, Year-to-Date, 1 Year, 3 Year, 5 Year, 10 Year, Full Period)
    - Total Return
    - Annualized Return
    - Annualized Standard Deviation
  - **Holdings Based Style Analysis**:
    - Category
    - Weight
    - Yield (SEC)
    - Yield (TTM)
    - Expense Ratio (Net)
    - Expense Ratio (Gross)
    - Price-to-Earnings Ratio (P/E)
    - Duration
    - Contribution to Return
    - Contribution to Risk
    - Total Portfolio Yield (SEC)
    - Total Portfolio Yield (TTM)
    - Total Portfolio Expense Ratio (Net)
    - Total Portfolio Expense Ratio (Gross)
    - Total Portfolio P/E
    - Total Portfolio Duration
    - Total Contribution to Return
  - **Fixed Income Maturity**:
    - Fundamentals Data Date
  - **Active Return Contribution**:
    - Active Return by Asset (1 Day, 1 Week, 1 Month, 3 Month, 6 Month, 1-year, 3-year, 5-year, 10-year, Full Period)
  - **Up vs. Down Market Performance**:
    - Market Type (Up Market, Down Market, Total)
    - Occurrences
    - Percentage Above Benchmark
    - Average Active Return Above Benchmark
    - Average Active Return Below Benchmark
    - Total Average Active Return
  - **Risk and Return Metrics**:
    - Arithmetic Mean (Monthly)
    - Arithmetic Mean (Annualized)
    - Geometric Mean (Monthly)
    - Geometric Mean (Annualized)
    - Standard Deviation (Monthly)
    - Downside Deviation (Monthly)
    - Beta
    - Alpha (Annualized)
    - R-Squared (R²)
    - Treynor Ratio
    - Calmar Ratio
    - Modigliani–Modigliani Measure
    - Active Return
    - Tracking Error
    - Information Ratio
    - Skewness
    - Excess Kurtosis
    - Historical Value-at-Risk (5%)
    - Analytical Value-at-Risk (5%)
    - Conditional Value-at-Risk (5%)
    - Safe Withdrawal Rate
    - Perpetual Withdrawal Rate
    - Positive Periods
    - Gain/Loss Ratio
  - **Annual Returns**:
    - Year
    - Inflation Rate
    - Portfolio Return
    - Portfolio Balance
    - Benchmark Return
    - Benchmark Balance
    - Individual Asset Returns
  - **Monthly Returns**:
    - Year-Month
    - Portfolio Monthly Return
    - Portfolio Balance
    - Benchmark Monthly Return
    - Benchmark Balance
    - Individual Asset Monthly Returns
  - **Graphs and Visualizations**:
    - Portfolio Growth Chart (line chart of portfolio and benchmark over time)
    - Annual Returns Chart (bar or line chart of yearly returns)
    - Monthly Returns Chart (time series of monthly returns)
    - Drawdown Chart (drawdown percentage over time)
    - Up vs. Down Market Performance Chart (bar or scatter comparing portfolio vs. benchmark)
    - Asset Allocation Pie Chart (stock breakdown)
    - Risk-Return Scatter Plot (risk vs. return for portfolio and benchmark)
    - Trailing Returns Bar Chart (returns across time periods)
    - Insights Video or Interactive Timeline (optional interactive market drivers)
  - **Additional Features**:
    - Insights Links (hyperlinks/pop-ups for period analysis)
    - Benchmark Selection (user chooses benchmark)
    - Data Constraints Note (notify about data limits)
    - Fundamentals Data Source (attribute data providers)

## Debugging Tips

- **Console Errors (Frontend)**:
  - Open browser DevTools (F12 > Console) at <http://localhost:5173>.
  - Look for red errors (e.g., "Cannot read property 'map' of undefined") or "Failed to fetch".
  - Fix: Check if data is undefined (e.g., add `data && data.map(...)`) or ensure backend is running.
- **Console Errors (Backend)**:
  - Run `node index.js` in `backend/` and watch the terminal.
  - Look for errors like "Cannot find module 'express'" or "SQLITE_ERROR: no such table".
  - Fix: Install missing modules (`npm install express`) or create tables (e.g., Task 2).
- **Syntax Errors**:
  - Check for missing semicolons, parentheses, or imports in `index.js` or `App.jsx`.
  - Fix: Add missing syntax (e.g., `import { useState } from 'react';`).
- **API Responses**:
  - Backend: Check for 404/429 errors from Alpha Vantage in terminal logs.
  - Frontend: Look for "Failed to fetch" in DevTools if backend isn't running.
  - Fix: Add caching for API rate limits (Task 5) or start backend (`node index.js`).
- **Logging**:
  - Add `console.log` to trace data (e.g., `console.log('Parsed transactions:', transactions)` in `index.js`).
  - Check logs in terminal (backend) or DevTools Console (frontend).
- **Ask Cursor**:
  - Example: "Why is my chart not rendering in frontend/src/App.jsx? I'm using Chart.js for Task 41."
  - Example: "Fix this error in backend/index.js: 'SQLITE_ERROR: no such table: transactions' while running Task 1."

## Notes for Cursor

- This is for a novice coder using Cursor, so keep code simple and modular.
- Use the free tech stack above.
- Save calculated data in SQLite to avoid repeat API calls.
- See `sample_transactions.csv` for the CSV format I'll use.
- Use `dotenv` to load API keys from `backend/.env`.
- Be meticulous: prioritize precision in financial data and calculations.
- Include comments in all code for clarity.
- Fix errors methodically: log them, analyze, resolve with existing tools.
