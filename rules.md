---
description: 
globs: 
alwaysApply: true
---
# Robinhood Dashboard Rules

## Keep it simple and beginner-friendly while building a fintech dashboard

- Use React with functional components and hooks (no classes) for the frontend.
- Style with Tailwind CSS, ensure mobile responsiveness.
- Use Chart.js for all charts (line, pie, bar) via react-chartjs-2.
- Parse CSVs with Papa Parse (papaparse) on the backend.
- Store data in SQLite with simple tables (e.g., transactions, stock_prices).
- Fetch stock prices from Alpha Vantage’s TIME_SERIES_DAILY endpoint.
- Keep code modular: small files (under 300 lines), clear function names.
- Use dotenv to load API keys from backend/.env.
- Always include comments in code for clarity (e.g., # Calculate daily value).
- Prefer simple solutions over complex ones.
- Avoid duplication: reuse existing code when possible (check App.jsx, index.js first).
- Only make changes requested or clearly tied to the task.
- Keep the codebase clean: no unused variables or dead code.
- New files are okay if they improve clarity (e.g., separate API logic), but minimize them.
- For local debugging, allow console.log or SQLite mocks, but never in prod-ready code.
- Fix errors methodically: log them, analyze in 3 reasoning steps, resolve with existing tools.
