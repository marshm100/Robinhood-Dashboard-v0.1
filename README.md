# Robinhood Portfolio Dashboard

**Live**: https://robinhood-dashboard-v0-1.vercel.app/

A web application for tracking and analyzing Robinhood investment portfolios. Create portfolios, upload holdings via CSV, view current valuations, and compare performance against benchmarks like SPY with interactive charts. A self-healing shared price cache eliminates flaky external API failures.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | [FastAPI](https://fastapi.tiangolo.com/) (Python) |
| Database | SQLite (dev) / PostgreSQL via [Vercel Postgres](https://vercel.com/docs/storage/vercel-postgres) (prod) |
| ORM | [SQLAlchemy](https://www.sqlalchemy.org/) |
| Frontend | [Jinja2](https://jinja.palletsprojects.com/) templates, [Tailwind CSS](https://tailwindcss.com/) (CDN), [Chart.js](https://www.chartjs.org/) |
| Stock Data | [Stooq](https://stooq.com/) (primary) + [yfinance](https://github.com/ranaroussi/yfinance) (fallback), DB-backed price cache |
| File Storage | [Vercel Blob](https://vercel.com/docs/storage/vercel-blob) (CSV archive) |
| Deployment | [Vercel](https://vercel.com/) serverless |

## Features

- **Portfolio CRUD** -- Create, list, and inspect portfolios with their holdings
- **Portfolio Detail View** -- Holdings table with live prices, current value, and percentage allocation; interactive Chart.js line chart comparing cumulative portfolio returns vs a configurable benchmark (SPY, QQQ, etc.) over selectable time periods (1y, 2y, 5y, all)
- **Self-Healing Price Cache** -- Stock and DailyPrice tables automatically discover and cache historical close prices on first access; primary source is Stooq (reliable daily CSVs, no rate limits) with yfinance as strict fallback; shared across all users; stale data is incrementally refreshed; specific user-friendly banners diagnose temporary failures (rate limits, outages); never hard-errors
- **CSV Upload** -- Import holdings from Robinhood CSV exports; auto-detects `ticker`/`symbol` and `shares`/`quantity`/`amount` columns; new tickers are auto-registered in the cache on upload
- **Benchmark Comparison** -- Common-timeline alignment across all holdings and benchmark; graceful info banners when history is limited or tickers are missing
- **Blob Archiving** -- Uploaded CSVs are archived to Vercel Blob storage when `BLOB_READ_WRITE_TOKEN` is set

## Project Structure

```
api/
  index.py              # FastAPI app + page routes (home, list, detail)
  config.py             # DATABASE_URL, CORS_ORIGINS from env
  database.py           # SQLAlchemy engine, session, init_db()
  models/
    portfolio.py        # Portfolio, Holding, Benchmark models
    price_cache.py      # Stock, DailyPrice models (shared price cache)
  routes/
    health.py           # GET /api/health
    portfolio.py        # Portfolio and holding CRUD (JSON API)
    upload.py           # CSV upload, parsing, ticker registration
    analysis.py         # Portfolio vs benchmark comparison
    stockr.py           # Single-ticker price lookup
  services/
    price_service.py    # Cache-backed price fetching (Stooq primary, yfinance fallback)
    analysis_service.py # Portfolio return calculation with common timeline
    blob_service.py     # Vercel Blob upload
templates/
  base.html             # Layout (Tailwind, Chart.js, nav)
  index.html            # Home page
  portfolios.html       # Portfolio list (clickable names)
  portfolio_detail.html # Detail view: holdings table + benchmark chart + info banners
static/
  favicon.ico
```

## Routes

### Pages

| Path | Description |
|------|-------------|
| `/` | Home page |
| `/portfolios` | Portfolio list -- click a name to view details |
| `/portfolios/{id}` | Portfolio detail -- holdings table, live valuations, benchmark comparison chart |

### JSON API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/portfolios/` | Create portfolio (`name` query param) |
| `GET` | `/api/portfolios/` | List all portfolios |
| `GET` | `/api/portfolios/{id}` | Get portfolio with holdings (JSON) |
| `POST` | `/api/portfolios/{id}/holdings` | Add holding (`ticker`, `shares`, optional `cost_basis`) |
| `POST` | `/api/upload/{portfolio_id}` | Upload CSV to replace holdings |
| `GET` | `/api/analysis/compare/{portfolio_id}` | Compare vs benchmark (`benchmark`, `period` params) |
| `GET` | `/api/stockr/prices/{ticker}` | Historical prices (`period` param) |

Interactive API docs at `/docs` when the server is running.

## Getting Started

### Prerequisites

- Python 3.8+

### Install and Run

```bash
git clone https://github.com/marshm100/Robinhood-Dashboard-v0.1.git
cd Robinhood-Dashboard-v0.1
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Open http://localhost:8000/

### Environment Variables

Copy `env.example` to `.env` to override defaults:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:////tmp/portfolio.db` | Database connection string |
| `POSTGRES_URL` | -- | Vercel Postgres URL (takes precedence) |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `BLOB_READ_WRITE_TOKEN` | -- | Vercel Blob token for CSV archiving |

### Deploy to Vercel

The repo includes `vercel.json` routing all requests to `api/index.py`. Push to GitHub and connect to Vercel, or run `vercel` from the CLI.

Set `POSTGRES_URL` in Vercel environment variables for persistent data. Without it, SQLite writes to `/tmp` and resets on cold starts.

## Self-Healing Price Cache

The `stocks` and `daily_prices` tables are created automatically on startup. Common benchmarks and indices (SPY, QQQ, ^GSPC, VTI, VXUS) are pre-seeded as `Stock` rows so they exist before first use.

**How it works**: When a portfolio detail page loads, a dedicated priming loop explicitly fetches full history for **every** unique ticker (all holdings + the benchmark) before any chart computation. This is the single point where external calls happen — all downstream analysis reads from DB cache only.

For each ticker, the priming step:

1. Creates a `Stock` row if the ticker is unknown
2. Fetches full history from **Stooq** (primary — reliable daily CSVs, no rate limits); tries plain ticker, then `.us` and `.ny` suffixes for US equities
3. If Stooq fails for all variants, falls back to **yfinance** (5 retries with exponential backoff)
4. Stores daily close prices in `daily_prices`; forward-fills gaps up to 5 business days
5. On subsequent requests, serves from DB; only fetches incrementally if data is >1 day stale

**Resilience**: Every ticker is primed in its own try/except — one failure never blocks others. Diagnostic banners appear only for genuinely unfetchable tickers:

- **Rate limit** — "data will update in ~15–60 minutes"
- **Temporary outage** — "will retry automatically on next page load"
- **No data** — "no historical price data available"

The system never returns a 500 error. If the benchmark is unavailable, the chart shows portfolio returns only with an explanation. If some holdings are missing, they are excluded with a warning while all other holdings still chart normally.

New tickers are auto-registered (without fetching) when a CSV is uploaded. Prices are primed on first detail page visit.

## CSV Format

The upload endpoint detects columns flexibly:

- **Ticker**: column named `ticker` or `symbol`
- **Shares**: column named `shares`, `quantity`, or `amount`
- **Cost basis** (optional): any column containing `cost`

Rows with empty tickers, tickers starting with `--`, or non-positive shares are skipped. Uploading replaces all existing holdings for that portfolio.

A `sample_transactions.csv` is included for testing.

## Dependencies

| Package | Purpose |
|---------|---------|
| `fastapi` | Web framework |
| `uvicorn[standard]` | ASGI server |
| `sqlalchemy` | ORM |
| `psycopg2-binary` | PostgreSQL driver |
| `pandas` | CSV parsing and data manipulation |
| `yfinance` | Historical stock prices (fallback source) |
| `httpx` | Async HTTP client (Blob uploads) |
| `python-multipart` | File upload support |
| `jinja2` | HTML templating |
