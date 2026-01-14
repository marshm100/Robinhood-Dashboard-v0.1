# Architecture Documentation

## For AI Agents: Complete System Understanding

This document provides comprehensive architectural documentation for the Robinhood Portfolio Analysis application. It is designed to give any AI agent (or developer) complete understanding of the system without needing to examine source code.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Technology Stack](#technology-stack)
3. [Directory Structure](#directory-structure)
4. [Core Architecture](#core-architecture)
5. [Data Flow](#data-flow)
6. [Backend Services](#backend-services)
7. [API Reference](#api-reference)
8. [Database Schemas](#database-schemas)
9. [Frontend Architecture](#frontend-architecture)
10. [Deployment](#deployment)
11. [Configuration](#configuration)
12. [Key Design Decisions](#key-design-decisions)

---

## Project Overview

### Purpose

Robinhood Portfolio Analysis is a web application that transforms Robinhood trading CSV exports into professional-grade investment analysis with:
- Portfolio valuation and performance tracking
- Risk assessment and metrics (Sharpe ratio, volatility, drawdown)
- Custom portfolio creation and backtesting
- Portfolio comparison against benchmarks (SPY, QQQ)
- Educational content with cyberpunk-themed UI

### Target Users

Individual retail investors who use Robinhood and want to:
- Understand their portfolio performance
- Compare their strategy against alternatives
- Learn financial concepts through interactive tools

### Core Value Proposition

1. **No external API keys required** - Self-contained stock price database
2. **Privacy-focused** - All data processed locally
3. **Educational** - Explains financial concepts in plain language
4. **Visual** - Cyberpunk-themed interactive charts

---

## Technology Stack

### Backend

| Component | Technology | Purpose |
|-----------|------------|---------|
| Web Framework | FastAPI (Python 3.11+) | REST API and server-side rendering |
| Database | SQLite (dev) / PostgreSQL (prod) | Transaction and portfolio data |
| ORM | SQLAlchemy | Database abstraction |
| Data Processing | Pandas, NumPy | Financial calculations |
| Settings | Pydantic Settings | Configuration management |
| ASGI Server | Uvicorn | Development server |
| Production Server | Gunicorn + Uvicorn workers | Production deployment |

### Frontend

| Component | Technology | Purpose |
|-----------|------------|---------|
| Templating | Jinja2 | Server-side HTML rendering |
| Charts | Plotly.js | Interactive financial visualizations |
| Styling | Custom CSS | Cyberpunk-themed dark UI |
| Interactivity | Vanilla JavaScript | Client-side logic |

### Stock Data System (stockr_backbone)

| Component | Technology | Purpose |
|-----------|------------|---------|
| Database | SQLite | Local stock price storage |
| Data Source | Stooq.com API | Free historical price data |
| Scheduler | Python threading | Background data refresh |
| HTTP Client | Requests + Tenacity | API calls with retry logic |

---

## Directory Structure

```
Robinhood-Dashboard v0.1/
├── src/                          # Main application source
│   ├── __init__.py
│   ├── main.py                   # FastAPI app entry point
│   ├── config.py                 # Settings and configuration
│   ├── database.py               # Database connection
│   ├── models.py                 # SQLAlchemy models
│   ├── routes/
│   │   ├── __init__.py           # Router exports
│   │   ├── api.py                # REST API endpoints
│   │   └── web.py                # HTML page routes
│   ├── services/
│   │   ├── __init__.py           # Service exports
│   │   ├── csv_processor.py      # Robinhood CSV parsing
│   │   ├── portfolio_calculator.py  # Financial calculations
│   │   ├── stock_price_service.py   # Stock data access
│   │   ├── custom_portfolio_service.py  # Custom portfolio logic
│   │   └── batch_processor.py    # Batch processing utilities
│   ├── static/
│   │   └── js/
│   │       └── dashboard.js      # Client-side JavaScript
│   └── templates/
│       ├── dashboard.html        # Main portfolio dashboard
│       ├── upload.html           # CSV upload page
│       ├── analysis.html         # Deep analysis page
│       └── comparison.html       # Portfolio comparison page
│
├── stockr_backbone/              # Stock data subsystem (git submodule)
│   ├── src/
│   │   ├── app.py               # Standalone API (optional)
│   │   ├── fetcher_standalone.py # Core data fetching
│   │   ├── background_maintenance.py  # Scheduled refresh
│   │   ├── ticker_sync.py       # Ticker list management
│   │   └── scheduler.py         # Task scheduling
│   ├── config/
│   │   ├── database.py          # Database configuration
│   │   ├── logging_config.py    # Logging setup
│   │   └── alembic/             # Database migrations
│   ├── tickers.txt              # List of tracked tickers
│   └── stockr.db                # SQLite stock database
│
├── tests/                        # Test suite
│   ├── test_api.py              # API endpoint tests
│   ├── test_calculations.py     # Financial calc tests
│   ├── test_database.py         # Database tests
│   ├── test_integration.py      # Integration tests
│   └── test_performance.py      # Performance tests
│
├── docs/                         # UI reference images
│   └── ui_aesthetic_*.jpg       # Design reference images
│
├── migrations/                   # Alembic migrations (main app)
│   └── env.py
│
├── nginx/                        # Nginx configuration
│   └── nginx.conf
│
├── run.py                        # Development entry point
├── run_prod.py                   # Production entry point
├── requirements.txt              # Python dependencies
├── docker-compose.yml            # Docker development setup
├── docker-compose.prod.yml       # Docker production setup
├── Dockerfile                    # Container definition
├── gunicorn.conf.py              # Gunicorn configuration
├── alembic.ini                   # Alembic configuration
├── celery_app.py                 # Celery setup (optional)
│
├── README.md                     # User documentation
├── ARCHITECTURE.md               # This file
├── DESIGN_PHILOSOPHY.md          # UI/UX design principles
├── CORE_FEATURES.md              # Core feature documentation
├── STOCKR_BACKBONE_ARCHITECTURE.md  # Stock system docs
└── MASTER_IMPLEMENTATION_PLAN.md # Development roadmap
```

---

## Core Architecture

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐        │
│  │  Dashboard │  │   Upload   │  │  Analysis  │  │ Comparison │        │
│  │   Page     │  │   Page     │  │   Page     │  │   Page     │        │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘        │
│        │               │               │               │                │
│        └───────────────┴───────────────┴───────────────┘                │
│                               │ HTTP/AJAX                               │
└───────────────────────────────┼─────────────────────────────────────────┘
                                │
┌───────────────────────────────┼─────────────────────────────────────────┐
│                         FASTAPI APPLICATION                              │
│                               │                                          │
│  ┌────────────────────────────┴────────────────────────────────────┐   │
│  │                         ROUTES LAYER                              │   │
│  │  ┌─────────────┐                          ┌─────────────┐        │   │
│  │  │  Web Routes │  /dashboard, /upload,    │  API Routes │        │   │
│  │  │  (web.py)   │  /analysis, /comparison  │  (api.py)   │        │   │
│  │  └─────────────┘                          └─────────────┘        │   │
│  └────────────────────────────┬────────────────────────────────────┘   │
│                               │                                          │
│  ┌────────────────────────────┴────────────────────────────────────┐   │
│  │                       SERVICES LAYER                              │   │
│  │                                                                    │   │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────┐  │   │
│  │  │  CSV Processor   │  │ Portfolio Calc   │  │ Custom Port.   │  │   │
│  │  │  - Parse CSV     │  │ - Performance    │  │ - Create       │  │   │
│  │  │  - Validate      │  │ - Risk metrics   │  │ - Backtest     │  │   │
│  │  │  - Transform     │  │ - Sector alloc   │  │ - Compare      │  │   │
│  │  └──────────────────┘  └────────┬─────────┘  └───────┬────────┘  │   │
│  │                                 │                     │           │   │
│  │                    ┌────────────┴─────────────────────┘           │   │
│  │                    │                                              │   │
│  │  ┌─────────────────┴──────────────────────────────────────────┐  │   │
│  │  │              Stock Price Service                            │  │   │
│  │  │  - get_price_at_date()    - get_prices_batch()             │  │   │
│  │  │  - validate_database()    - get_available_stocks()         │  │   │
│  │  └─────────────────┬──────────────────────────────────────────┘  │   │
│  └────────────────────┼────────────────────────────────────────────┘   │
│                       │                                                  │
└───────────────────────┼──────────────────────────────────────────────────┘
                        │
┌───────────────────────┼──────────────────────────────────────────────────┐
│                       │      DATA LAYER                                   │
│                       ▼                                                   │
│  ┌────────────────────────────┐    ┌────────────────────────────────┐   │
│  │   MAIN APPLICATION DB      │    │   STOCKR_BACKBONE DB           │   │
│  │   (portfolio.db)           │    │   (stockr.db)                  │   │
│  │                            │    │                                 │   │
│  │  Tables:                   │    │  Tables:                       │   │
│  │  - transactions            │    │  - stocks                      │   │
│  │  - custom_portfolios       │    │  - historical_prices           │   │
│  │  - portfolio_snapshots     │    │                                 │   │
│  └────────────────────────────┘    │  Background Service:           │   │
│                                     │  - Auto-refresh every 60 min   │   │
│                                     │  - Auto-discovery of new       │   │
│                                     │    tickers                     │   │
│                                     └────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
```

### Critical Component: stockr_backbone

**stockr_backbone is the FOUNDATIONAL DATABASE for all stock price data. It is NOT optional.**

Without stockr_backbone:
- ❌ Portfolio valuation would not work
- ❌ Custom portfolio backtesting would fail
- ❌ Benchmark comparisons would be impossible
- ❌ All performance metrics would be unavailable

**How it works:**
1. Runs as a background daemon thread (started automatically)
2. Refreshes all tracked stocks every 60 minutes
3. Auto-discovers new tickers when they're first queried
4. Uses Stooq.com as data source (free, no API key required)
5. Stores data in local SQLite database

---

## Data Flow

### 1. CSV Upload Flow

```
User uploads CSV
       │
       ▼
┌─────────────────┐
│  csv_processor  │ Parse Robinhood format
│  validate_csv   │ Validate columns/data
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Transaction    │ Store in database
│  Model          │ (transactions table)
└────────┬────────┘
         │
         ▼
    Redirect to
    Dashboard
```

### 2. Portfolio Calculation Flow

```
Dashboard Request
       │
       ▼
┌─────────────────┐
│ Portfolio       │ Load transactions
│ Calculator      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│ Stock Price     │────▶│ stockr_backbone │
│ Service         │     │ Database        │
└────────┬────────┘     └─────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ Calculate:                               │
│ - Holdings (shares × current price)     │
│ - Performance (returns, CAGR)           │
│ - Risk (volatility, Sharpe, drawdown)   │
│ - Sector allocation                     │
└────────┬────────────────────────────────┘
         │
         ▼
    JSON Response
    to Frontend
```

### 3. Custom Portfolio Backtest Flow

```
User creates portfolio
(60% AAPL, 40% MSFT)
       │
       ▼
┌─────────────────┐
│ Custom Portfolio│ Validate allocations
│ Service         │ (must sum to 100%)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Backtest        │ For each historical date:
│ Engine          │ 1. Get prices from stockr
│                 │ 2. Calculate portfolio value
│                 │ 3. Track performance
└────────┬────────┘
         │
         ▼
Return: total return,
Sharpe ratio, max drawdown,
value history
```

---

## Backend Services

### 1. CSV Processor (`src/services/csv_processor.py`)

**Purpose:** Parse and validate Robinhood CSV exports

**Key Functions:**
- `validate_csv_structure(content)` - Check required columns exist
- `process_robinhood_csv(content)` - Parse CSV into DataFrame
- `normalize_transaction(row)` - Standardize transaction format

**Supported Transaction Types:**
- Buy, Sell (stock trades)
- CDIV (cash dividends)
- RTP, ACH (bank transfers)
- MISC (miscellaneous)

### 2. Portfolio Calculator (`src/services/portfolio_calculator.py`)

**Purpose:** All financial calculations and metrics

**Key Methods:**

| Method | Returns | Description |
|--------|---------|-------------|
| `get_portfolio_summary()` | dict | Holdings, values, transaction count |
| `get_portfolio_value_history(start, end)` | DataFrame | Daily portfolio values |
| `calculate_performance_metrics()` | dict | CAGR, volatility, Sharpe, Sortino |
| `get_risk_assessment()` | dict | VaR, beta, max drawdown |
| `get_sector_allocation()` | dict | Sector breakdown percentages |
| `get_drawdown_analysis()` | dict | Drawdown series and periods |
| `get_performance_attribution()` | dict | Contribution by asset |
| `get_advanced_analytics()` | dict | Diversification metrics |

**Internal Features:**
- Price caching (`_price_cache`) to avoid repeated queries
- Batch price loading (`_preload_price_cache`)
- Date sampling for long histories (monthly for >3yr, weekly for >1yr)
- Transaction price fallback when stockr data unavailable

### 3. Stock Price Service (`src/services/stock_price_service.py`)

**Purpose:** Interface to stockr_backbone database

**Key Methods:**

| Method | Returns | Description |
|--------|---------|-------------|
| `get_price_at_date(symbol, date)` | dict | OHLCV for specific date |
| `get_prices_batch(tickers, start, end)` | dict | Multiple tickers at once |
| `get_available_stocks()` | list | All tracked tickers |
| `validate_database()` | dict | Database health check |

**Auto-Discovery:**
When a ticker is queried but not in database:
1. Automatically adds to stockr_backbone tracking
2. Fetches historical data from Stooq.com
3. Returns data (subsequent queries use cache)

### 4. Custom Portfolio Service (`src/services/custom_portfolio_service.py`)

**Purpose:** Create, backtest, and compare custom portfolios

**Key Methods:**

| Method | Description |
|--------|-------------|
| `create_portfolio(name, allocation, strategy)` | Create new portfolio |
| `backtest_portfolio(id, start, end, initial)` | Simulate historical performance |
| `compare_portfolios(ids, benchmarks, robinhood)` | Multi-portfolio comparison |
| `get_benchmark_history(ticker, start, end)` | Benchmark data for comparison |
| `run_scenario(portfolio_id, type, params)` | What-if analysis |

**Supported Strategies:**
- `lump_sum` - Full investment at start
- `dca` - Dollar-cost averaging monthly

---

## API Reference

### Health & Status

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | System health check (includes stockr status) |
| `/api/health` | GET | API-specific health check |
| `/api/stockr-status` | GET | Detailed stockr_backbone status |

### CSV & Transactions

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/upload-csv` | POST | Upload Robinhood CSV file |
| `/api/validate-csv` | POST | Validate CSV without saving |
| `/api/transactions` | GET | Get paginated transactions |

### Portfolio Analysis

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/portfolio-overview` | GET | Full portfolio summary |
| `/api/portfolio-history` | GET | Historical value series |
| `/api/performance-metrics` | GET | Performance calculations |
| `/api/risk-assessment` | GET | Risk metrics |
| `/api/advanced-analytics` | GET | Diversification analysis |
| `/api/drawdown-analysis` | GET | Drawdown series and periods |
| `/api/performance-attribution` | GET | Return contribution by asset |
| `/api/monthly-performance` | GET | Monthly returns table |

### Stock Data

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/stock-price/{symbol}/{date}` | GET | Price for specific date |
| `/api/available-stocks` | GET | List of tracked stocks |
| `/api/validate-stock-database` | GET | Stock database health |

### Custom Portfolios

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/custom-portfolios` | POST | Create custom portfolio |
| `/api/custom-portfolios` | GET | List all portfolios |
| `/api/custom-portfolios/{id}` | GET | Get specific portfolio |
| `/api/custom-portfolios/{id}` | PUT | Update portfolio |
| `/api/custom-portfolios/{id}` | DELETE | Delete portfolio |
| `/api/custom-portfolios/{id}/backtest` | POST | Run backtest |
| `/api/portfolio-comparison` | POST | Compare multiple portfolios |
| `/api/benchmarks/{ticker}` | GET | Benchmark historical data |
| `/api/scenarios` | POST | Run what-if scenario |

### Web Pages

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Root redirect |
| `/dashboard` | GET | Main dashboard page |
| `/upload` | GET | CSV upload page |
| `/analysis` | GET | Deep analysis page |
| `/comparison` | GET | Portfolio comparison page |

---

## Database Schemas

### Main Application Database (portfolio.db)

#### transactions

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| activity_date | DATE | Transaction date |
| ticker | VARCHAR | Stock symbol (nullable) |
| trans_code | VARCHAR | Transaction type (Buy, Sell, etc.) |
| quantity | FLOAT | Number of shares |
| price | FLOAT | Price per share |
| amount | FLOAT | Total transaction amount |

#### custom_portfolios

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| name | VARCHAR | Portfolio name |
| description | TEXT | Optional description |
| asset_allocation | JSON | {"AAPL": 0.5, "MSFT": 0.5} |
| strategy | VARCHAR | "lump_sum" or "dca" |
| monthly_investment | FLOAT | DCA amount (nullable) |
| created_at | DATETIME | Creation timestamp |
| updated_at | DATETIME | Last update timestamp |

### Stockr Backbone Database (stockr.db)

#### stocks

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| symbol | VARCHAR | Stock ticker (unique, indexed) |
| name | VARCHAR | Company name (optional) |
| ephemeral | BOOLEAN | 0=permanent, 1=temporary |

#### historical_prices

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| stock_id | INTEGER | FK to stocks.id |
| date | DATE | Price date |
| open | FLOAT | Opening price |
| high | FLOAT | High price |
| low | FLOAT | Low price |
| close | FLOAT | Closing price |
| volume | INTEGER | Trading volume |

**Constraints:** Unique on (stock_id, date)

---

## Frontend Architecture

### Page Structure

Each page follows a consistent pattern:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Page Title</title>
    <link> <!-- Plotly.js CDN -->
    <style> <!-- Cyberpunk theme CSS --> </style>
</head>
<body>
    <nav> <!-- Fixed navigation --> </nav>
    <main>
        <!-- Page content -->
        <!-- Metric cards -->
        <!-- Chart containers -->
    </main>
    <script> <!-- Plotly.js --> </script>
    <script> <!-- Page-specific JavaScript --> </script>
</body>
</html>
```

### Design System

**Color Palette:**
- Background: `#0a0a0a` (deep black)
- Cards: `#12121e` (dark blue-black)
- Accent: `#00ffff` (neon cyan)
- Positive: `#00ff88` (bright green)
- Negative: `#ff3366` (muted red)
- Text: `#e0e0e0` (light gray)

**Visual Effects:**
- Neon glow on key values
- Glassmorphism cards (blur + transparency)
- Subtle scanlines for retro feel
- Smooth hover transitions

### Chart Configuration

All charts use Plotly.js with consistent theming:

```javascript
layout = {
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    font: { color: '#e0e0e0', family: 'JetBrains Mono' },
    xaxis: { gridcolor: 'rgba(255,255,255,0.1)' },
    yaxis: { gridcolor: 'rgba(255,255,255,0.1)' }
}
```

---

## Deployment

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
python run.py
# OR
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Access at http://localhost:8000
```

### Docker Development

```bash
# Start with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Docker Production

```bash
# Start production stack
docker-compose -f docker-compose.prod.yml up -d

# Includes:
# - Gunicorn + Uvicorn workers
# - Nginx reverse proxy
# - PostgreSQL database
# - Redis (optional, for caching)
```

### Railway Deployment

Railway automatically detects and deploys Docker applications.

**Configuration:**
1. Connect your GitHub repository to Railway
2. Railway will auto-detect the Dockerfile
3. Set environment variables in Railway dashboard:
   - `DATABASE_URL=sqlite:///./data/portfolio.db`
   - `STOCKR_DB_PATH=./data/stockr_backbone/stockr.db`
   - `SECRET_KEY=your-secure-key`
4. Data persists in the `./data` directory (mounted volume)

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | development | Environment mode |
| `DATABASE_URL` | sqlite:///portfolio.db | Database connection |
| `DEBUG` | True | Enable debug mode |
| `SECRET_KEY` | (generated) | Session secret |
| `HOST` | 0.0.0.0 | Server bind address |
| `PORT` | 8000 | Server port |
| `CORS_ORIGINS` | localhost:3000,5173 | Allowed CORS origins |
| `ALPHA_VANTAGE_KEY` | None | Optional API key |
| `FINNHUB_KEY` | None | Optional API key |

---

## Key Design Decisions

### 1. Self-Contained Stock Database

**Decision:** Build internal stock database (stockr_backbone) instead of relying on external APIs.

**Rationale:**
- External APIs have rate limits (Alpha Vantage: 5 calls/min)
- No API keys required for users
- Faster queries (local database)
- Historical data always available

### 2. Server-Side Rendering with Jinja2

**Decision:** Use Jinja2 templates instead of React/Vue SPA.

**Rationale:**
- Simpler deployment
- No build step required
- Better SEO (though not critical for this app)
- Faster initial page load

### 3. SQLite for MVP

**Decision:** SQLite as default database, PostgreSQL for production.

**Rationale:**
- Zero configuration for development
- Single file, easy to backup/restore
- Sufficient performance for MVP scale
- Easy migration path to PostgreSQL

### 4. Background Thread vs Celery

**Decision:** Use Python threading instead of Celery for stock data refresh.

**Rationale:**
- No Redis dependency
- Simpler deployment
- Sufficient for background refresh task
- Can upgrade to Celery if needed

### 5. Transaction Price Fallback

**Decision:** When stock price unavailable, fall back to transaction price.

**Rationale:**
- Ensures charts always render
- Better UX than error messages
- Logged for debugging
- Accurate enough for visualization

---

## Common Tasks for AI Agents

### Adding a New API Endpoint

1. Add route in `src/routes/api.py`
2. Add service method if needed in `src/services/`
3. Add model if needed in `src/models.py`
4. Update API documentation in this file

### Adding a New Financial Metric

1. Add calculation method in `portfolio_calculator.py`
2. Include in relevant API response (e.g., `get_portfolio_summary`)
3. Add frontend display in appropriate template
4. Add tooltip explanation for educational value

### Adding a New Chart

1. Add chart container in template HTML
2. Add JavaScript function to fetch data and render with Plotly
3. Follow existing chart styling conventions
4. Add loading state and error handling

### Debugging Stock Price Issues

1. Check `/api/stockr-status` for service health
2. Check if ticker exists: `/api/available-stocks`
3. Check specific price: `/api/stock-price/{symbol}/{date}`
4. Verify stockr_backbone database has data

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | Nov 2025 | Initial release |
| 1.0.1 | Jan 2026 | Docker/Railway deployment optimization |

---

**Last Updated:** January 2026
**Status:** Production Ready
**Maintained By:** Development Team
