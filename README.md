# Robinhood Portfolio Dashboard

A web application for tracking and analyzing Robinhood investment portfolios. Upload your Robinhood CSV exports, create custom portfolios, manage holdings, and compare performance against benchmarks like SPY.

## Tech Stack

- **Backend**: [FastAPI](https://fastapi.tiangolo.com/) (Python)
- **Database**: SQLite (default) / PostgreSQL (production via Vercel Postgres)
- **ORM**: SQLAlchemy
- **Templates**: Jinja2 with [Tailwind CSS](https://tailwindcss.com/) (CDN) and [Chart.js](https://www.chartjs.org/)
- **Stock Data**: [yfinance](https://github.com/ranaroussi/yfinance) for historical prices
- **Deployment**: [Vercel](https://vercel.com/) serverless

## Features

- **Portfolio Management** -- Create, view, and manage multiple portfolios
- **CSV Upload** -- Import holdings from Robinhood account statement CSVs (auto-detects ticker/symbol and shares/quantity columns)
- **Benchmark Comparison** -- Compare portfolio returns against SPY or other benchmarks over configurable time periods
- **Historical Prices** -- Fetch historical stock price data via yfinance with retry logic and period fallback
- **Web UI** -- Server-rendered pages for home, portfolio list, and portfolio details

## Project Structure

```
api/
  index.py              # FastAPI app entry point (Vercel serverless function)
  config.py             # Configuration (DATABASE_URL, CORS, STOCKR_DB_PATH)
  database.py           # SQLAlchemy engine, session, and init_db()
  models/
    portfolio.py        # Portfolio, Holding, and Benchmark models
  routes/
    health.py           # GET /api/health
    portfolio.py        # Portfolio CRUD endpoints
    upload.py           # CSV upload and parsing
    analysis.py         # Portfolio vs benchmark comparison
    stockr.py           # Historical price lookup
  services/
    price_service.py    # yfinance wrapper with retries and fallback
    analysis_service.py # Portfolio return calculations
    blob_service.py     # Vercel Blob archive for uploaded files
templates/
  base.html             # Base layout with nav and footer
  index.html            # Home landing page
  portfolios.html       # Portfolio list page
static/
  favicon.ico
tests/                  # Test suite (API, database, calculations, integration, performance)
stockr_backbone/        # Git submodule for local stock price database (optional)
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Home page |
| `GET` | `/portfolios` | Portfolio list page |
| `GET` | `/api/health` | Health check |
| `POST` | `/api/portfolios/` | Create a portfolio (`name` query param) |
| `GET` | `/api/portfolios/` | List all portfolios |
| `GET` | `/api/portfolios/{id}` | Get portfolio with holdings |
| `POST` | `/api/portfolios/{id}/holdings` | Add a holding (`ticker`, `shares`, optional `cost_basis`) |
| `POST` | `/api/upload/{portfolio_id}` | Upload a CSV to replace portfolio holdings |
| `GET` | `/api/analysis/compare/{portfolio_id}` | Compare portfolio vs benchmark (`benchmark`, `period` params) |
| `GET` | `/api/stockr/prices/{ticker}` | Get historical prices for a ticker (`period` param) |

Interactive API docs are available at `/docs` when the server is running.

## Getting Started

### Prerequisites

- Python 3.8+
- pip

### Installation

```bash
git clone https://github.com/marshm100/Robinhood-Dashboard-v0.1.git
cd Robinhood-Dashboard-v0.1
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Configure Environment

```bash
cp env.example .env
```

Edit `.env` as needed. Defaults work for local development (SQLite at `/tmp/portfolio.db`).

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:////tmp/portfolio.db` | Database connection string |
| `POSTGRES_URL` | *(none)* | Vercel Postgres URL (takes precedence over `DATABASE_URL`) |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `STOCKR_DB_PATH` | `stockr_backbone/stockr.db` | Path to stockr_backbone SQLite database |
| `DEBUG` | `True` | Debug mode |
| `SECRET_KEY` | *(none)* | Application secret key |
| `BLOB_READ_WRITE_TOKEN` | *(none)* | Vercel Blob token for archiving uploaded CSVs |

### Run Locally

```bash
uvicorn api.index:app --reload --host 0.0.0.0 --port 8000
```

Then open:
- **Home**: http://localhost:8000/
- **Portfolios**: http://localhost:8000/portfolios
- **API Docs**: http://localhost:8000/docs

> **Note**: `run.py` references a legacy `src/` directory that has been removed. Use the `uvicorn` command above to run the app locally.

### Deploy to Vercel

The project includes a `vercel.json` that routes all requests to `api/index.py`:

```bash
vercel
```

On Vercel, set `POSTGRES_URL` in environment variables to use Vercel Postgres for persistent data. Without it, data is stored in `/tmp` and resets on cold starts.

## CSV Format

The upload endpoint accepts CSVs with flexible column detection. It looks for:

- **Ticker column**: a column named `ticker` or `symbol` (case-insensitive)
- **Shares column**: a column named `shares`, `quantity`, or `amount` (case-insensitive)
- **Cost basis column** (optional): any column with `cost` in the name

Rows with zero or negative shares, empty tickers, or tickers starting with `--` are skipped. Uploading replaces all existing holdings for that portfolio.

## stockr_backbone

The [stockr_backbone](https://github.com/marshm100/stockr_backbone) git submodule provides an optional local stock price database using free data from Stooq.com. To initialize it:

```bash
git submodule update --init --recursive
```

## Tests

Test files are located in `tests/` and in the project root (`test_*.py`). Tests can be run directly:

```bash
python test_setup.py              # Validates imports, DB, and core functionality
python tests/test_api.py
python tests/test_calculations.py
python tests/test_database.py
python tests/test_integration.py
```

## Dependencies

From `requirements.txt`:

- `fastapi` -- Web framework
- `uvicorn[standard]` -- ASGI server
- `sqlalchemy` -- ORM and database toolkit
- `psycopg2-binary` -- PostgreSQL driver
- `pandas` -- Data manipulation
- `yfinance` -- Yahoo Finance historical price data
- `httpx` -- Async HTTP client (used for Vercel Blob uploads)
- `python-multipart` -- File upload support for FastAPI
- `jinja2` -- HTML templating

## License

This project is not currently licensed. All rights reserved.
