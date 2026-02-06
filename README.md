# Robinhood Portfolio Dashboard

**Live**: https://robinhood-dashboard-v0-1.vercel.app/

A web application for tracking and analyzing Robinhood investment portfolios. Create portfolios, upload holdings via CSV, and compare performance against benchmarks like SPY.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | [FastAPI](https://fastapi.tiangolo.com/) (Python) |
| Database | SQLite (dev) / PostgreSQL via [Vercel Postgres](https://vercel.com/docs/storage/vercel-postgres) (prod) |
| ORM | [SQLAlchemy](https://www.sqlalchemy.org/) |
| Frontend | [Jinja2](https://jinja.palletsprojects.com/) templates, [Tailwind CSS](https://tailwindcss.com/) (CDN), [Chart.js](https://www.chartjs.org/) |
| Stock Data | [yfinance](https://github.com/ranaroussi/yfinance) (Yahoo Finance historical prices) |
| File Storage | [Vercel Blob](https://vercel.com/docs/storage/vercel-blob) (CSV archive) |
| Deployment | [Vercel](https://vercel.com/) serverless |

## Features

- **Portfolio CRUD** -- Create, list, and inspect portfolios with their holdings
- **CSV Upload** -- Import holdings from Robinhood CSV exports; auto-detects `ticker`/`symbol` and `shares`/`quantity`/`amount` columns
- **Benchmark Comparison** -- Compare portfolio cumulative returns against SPY (or any ticker) over configurable periods
- **Historical Prices** -- Fetch close prices via yfinance with retry/backoff and automatic period fallback
- **Blob Archiving** -- Uploaded CSVs are archived to Vercel Blob storage when `BLOB_READ_WRITE_TOKEN` is set

## Project Structure

```
api/
  index.py              # FastAPI app entry point
  config.py             # DATABASE_URL, CORS_ORIGINS from env
  database.py           # SQLAlchemy engine, session, init_db()
  models/
    portfolio.py        # Portfolio, Holding, Benchmark models
  routes/
    health.py           # GET /api/health
    portfolio.py        # Portfolio and holding CRUD
    upload.py           # CSV upload and parsing
    analysis.py         # Portfolio vs benchmark comparison
    stockr.py           # Single-ticker price lookup
  services/
    price_service.py    # yfinance wrapper (retries, fallback)
    analysis_service.py # Portfolio return calculation
    blob_service.py     # Vercel Blob upload
templates/
  base.html             # Layout (Tailwind, Chart.js, nav)
  index.html            # Home page
  portfolios.html       # Portfolio list
static/
  favicon.ico
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Home page |
| `GET` | `/portfolios` | Portfolio list page |
| `GET` | `/api/health` | Health check |
| `POST` | `/api/portfolios/` | Create portfolio (`name` query param) |
| `GET` | `/api/portfolios/` | List all portfolios |
| `GET` | `/api/portfolios/{id}` | Get portfolio with holdings |
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
| `yfinance` | Historical stock prices |
| `httpx` | Async HTTP client (Blob uploads) |
| `python-multipart` | File upload support |
| `jinja2` | HTML templating |
