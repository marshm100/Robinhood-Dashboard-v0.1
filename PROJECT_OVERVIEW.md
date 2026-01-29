# Project Overview: Robinhood Portfolio Analysis Dashboard

## 1. Project Name & One-Sentence Description

**Robinhood Portfolio Analysis Dashboard v0.1** - A cyberpunk-themed web application that transforms Robinhood trading CSV exports into professional-grade investment analysis with portfolio valuation, risk assessment, custom portfolio backtesting, and benchmark comparisons for retail investors.

---

## 2. Core Purpose & Key Features

### High-Level Goal
Provide retail investors (primarily Robinhood users) with comprehensive portfolio analytics, performance tracking, and investment strategy tools that go beyond what the Robinhood app offers natively. The application enables users to upload their Robinhood CSV exports and receive professional-grade analysis including risk metrics, benchmark comparisons, and hypothetical portfolio backtesting.

### Main User-Facing Features

- **CSV Upload & Processing**: Secure upload and flexible parsing of Robinhood transaction CSV files with automatic column detection (ticker/symbol, shares/quantity/amount)
- **Portfolio Tracking**: Real-time calculation of holdings and portfolio values with cost basis tracking
- **Performance Analytics**: Total returns, CAGR, rolling returns, and percentile rankings
- **Risk Assessment**: Volatility calculations, Value at Risk (VaR), Sharpe ratio, and maximum drawdown analysis
- **Market Benchmarking**: Performance comparison against market indices (SPY, QQQ, etc.)
- **Asset Allocation**: Diversification analysis and concentration risk assessment
- **Interactive Visualizations**: Charts powered by Plotly.js with cyberpunk styling

### Core Differentiating Features

- **Custom Portfolio Creation**: Create hypothetical portfolios with any asset allocation percentages
- **Portfolio Comparison**: Compare custom portfolios against actual Robinhood portfolio and benchmarks
- **Backtesting Engine**: Historical performance simulation for custom portfolios with DCA and lump-sum strategies
- **Educational Features**: Interactive tooltips and contextual financial education

### Notable Internal Capabilities

- **stockr_backbone Database**: Core internal stock data maintenance system that automatically tracks, caches, and refreshes historical price data
- **Auto-Discovery**: New tickers encountered are automatically added to tracking
- **Background Maintenance**: Continuous 24/7 data refresh (~60 minute intervals)

---

## 3. Technology Stack

### Backend
| Component | Technology | Version |
|-----------|------------|---------|
| Framework | FastAPI | 0.110.0 |
| Language | Python | 3.11+ |
| Server (Dev) | Uvicorn | 0.27.0 |
| Server (Prod) | Gunicorn + UvicornWorker | - |
| Database ORM | SQLAlchemy | 2.0.35 |
| Data Processing | Pandas | 2.2.3 |
| Stock Data (Primary) | yfinance | 0.2.41 |
| Stock Data (Secondary) | Stooq.com API | via stockr_backbone |
| HTTP Client | httpx | 0.27.0 |
| PostgreSQL Driver | psycopg2-binary | 2.9.9 |
| File Uploads | python-multipart | 0.0.9 |

### Frontend
| Component | Technology |
|-----------|------------|
| Templating | Jinja2 (server-side rendering) |
| Charts | Plotly.js (interactive visualizations) |
| Styling | Custom CSS (cyberpunk theme with neon effects) |
| Interactivity | Vanilla JavaScript |
| CSS Framework | Tailwind CSS (mentioned in docs, may be partial) |

### Database/Storage
| Environment | Technology | Purpose |
|-------------|------------|---------|
| Local Development | SQLite | Main application database |
| Production (Vercel) | PostgreSQL | Persistent storage |
| Stock Data | SQLite | stockr_backbone internal database |
| File Storage | Vercel Blob | CSV upload archival |

### Other Major Tools
| Tool | Purpose |
|------|---------|
| Alembic | Database migrations |
| GitHub Actions | CI/CD pipeline |
| Docker | Containerization |
| Nginx | Reverse proxy (production) |
| GHCR | Container registry (GitHub Container Registry) |

### Deployment Platforms (Supported)
- **Primary**: Vercel (serverless functions)
- **Alternative**: Railway, Render, DigitalOcean, AWS ECS

---

## 4. High-Level Architecture

### Component Interaction Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                        USER BROWSER                                   │
│                  (HTML/CSS/JS + Plotly Charts)                       │
└─────────────────────────────┬────────────────────────────────────────┘
                              │ HTTP Requests
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    VERCEL SERVERLESS FUNCTION                         │
│                      (api/index.py entry point)                       │
├──────────────────────────────────────────────────────────────────────┤
│                         FastAPI Application                           │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │ Static Files│  │ Jinja2       │  │ CORS         │  │ Router    │ │
│  │ /static     │  │ Templates    │  │ Middleware   │  │ Includes  │ │
│  └─────────────┘  └──────────────┘  └──────────────┘  └───────────┘ │
└─────────────────────────────┬────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────────┐
        ▼                     ▼                         ▼
┌───────────────┐   ┌─────────────────┐   ┌─────────────────────────────┐
│  API Routes   │   │  Web Routes     │   │  Static Files               │
│  /api/*       │   │  / /portfolios  │   │  /static/*                  │
├───────────────┤   └────────┬────────┘   └─────────────────────────────┘
│ • health      │            │
│ • portfolio   │            │ Jinja2 Render
│ • analysis    │            ▼
│ • upload      │   ┌─────────────────┐
│ • stockr      │   │ HTML Templates  │
└───────┬───────┘   │ • index.html    │
        │           │ • portfolios.html│
        ▼           │ • base.html     │
┌───────────────────┴─────────────────┐
│         SERVICES LAYER              │
│  ┌──────────────┐ ┌──────────────┐ │
│  │price_service │ │analysis_     │ │
│  │(yfinance)    │ │service       │ │
│  ├──────────────┤ ├──────────────┤ │
│  │blob_service  │ │              │ │
│  │(Vercel Blob) │ │              │ │
│  └──────────────┘ └──────────────┘ │
└─────────────────┬───────────────────┘
                  │
    ┌─────────────┼─────────────┐
    ▼             ▼             ▼
┌─────────┐ ┌───────────┐ ┌──────────────────────────────┐
│ SQLite/ │ │ Vercel    │ │   STOCKR_BACKBONE            │
│PostgreSQL│ │ Blob      │ │   (Core Stock Data System)   │
│         │ │ Storage   │ │   ┌─────────────────────────┐│
│Tables:  │ │           │ │   │ Background Maintenance  ││
│•portfolios│          │ │   │ (60-min refresh cycle)  ││
│•holdings│ │           │ │   └───────────┬─────────────┘│
│•benchmarks│          │ │               ▼              │
└─────────┘ └───────────┘ │   ┌─────────────────────────┐│
                          │   │ SQLite: stocks,         ││
                          │   │ historical_prices       ││
                          │   └───────────┬─────────────┘│
                          │               ▼              │
                          │   ┌─────────────────────────┐│
                          │   │ External: Stooq.com API ││
                          │   │ (Only for cache misses) ││
                          │   └─────────────────────────┘│
                          └──────────────────────────────┘
```

### Request Flow Examples

**1. User Views Portfolio:**
```
Browser → GET /portfolios → FastAPI → SQLAlchemy → PostgreSQL → Jinja2 → HTML Response
```

**2. User Requests Analysis:**
```
Browser → GET /api/analysis/compare/{id} → analysis_service → price_service →
  → stockr_backbone (local) OR yfinance (fallback) → JSON Response
```

**3. Background Stock Update:**
```
stockr_backbone maintenance thread → fetch_and_store() → Stooq.com API →
  → stockr SQLite database (historical_prices table)
```

### Deployment Configuration

**Vercel (Current Primary):**
- Single serverless function at `api/index.py`
- All routes handled by FastAPI
- Data stored in `/tmp` (ephemeral) + PostgreSQL (persistent)
- Vercel Blob for file archival

**Docker-Based (Alternative):**
- Production: `docker-compose.prod.yml` (includes Nginx reverse proxy)
- Development: `docker-compose.yml`
- Backup automation: `docker-compose.backup.yml`

---

## 5. Project Structure Overview

```
/home/user/Robinhood-Dashboard-v0.1/
│
├── api/                           # Vercel serverless entry point
│   ├── index.py                   # FastAPI app initialization (76 lines)
│   ├── config.py                  # Environment configuration
│   ├── database.py                # SQLAlchemy setup, session management
│   ├── models/
│   │   └── portfolio.py           # Data models: Portfolio, Holding, Benchmark
│   ├── routes/                    # API endpoints (~150 lines total)
│   │   ├── health.py              # GET /api/health
│   │   ├── portfolio.py           # Portfolio CRUD operations
│   │   ├── analysis.py            # Performance comparison endpoints
│   │   ├── upload.py              # CSV upload handling
│   │   └── stockr.py              # Stock price endpoints
│   └── services/                  # Business logic (~130 lines total)
│       ├── price_service.py       # yfinance integration with retry/backoff
│       ├── analysis_service.py    # Portfolio return calculations
│       └── blob_service.py        # Vercel Blob storage integration
│
├── stockr_backbone/               # Core stock data system (CRITICAL)
│   ├── src/                       # Fetcher, maintenance service
│   └── stockr.db                  # Stock data SQLite database
│
├── templates/                     # Jinja2 HTML templates
│   ├── base.html                  # Base layout with navigation
│   ├── index.html                 # Home page
│   └── portfolios.html            # Portfolio list view
│
├── static/                        # Frontend assets
│   └── favicon.ico                # Chart icon
│
├── tests/                         # Test suite
│   ├── test_api.py                # API endpoint tests
│   ├── test_integration.py        # Integration tests
│   ├── test_performance.py        # Performance tests
│   ├── test_calculations.py       # Calculation accuracy tests
│   └── test_database.py           # Database tests
│
├── scripts/                       # Automation scripts
│   ├── prepopulate_stockr.py      # Stock database population
│   ├── migrate_sqlite_to_postgres.py  # Database migration
│   └── backup.py                  # Backup utilities
│
├── migrations/                    # Alembic database migrations
│   └── env.py                     # Migration configuration
│
├── nginx/                         # Reverse proxy configuration
│   └── nginx.conf                 # Nginx production config
│
├── docs/                          # Documentation and mockups
│   └── ui_aesthetic_*.jpg         # UI design mockups (15 images)
│
├── .github/workflows/             # CI/CD
│   └── deploy.yml                 # GitHub Actions deployment pipeline
│
├── run.py                         # Development entry point (Uvicorn)
├── run_prod.py                    # Production entry point (Gunicorn)
├── requirements.txt               # Python dependencies
├── vercel.json                    # Vercel serverless configuration
├── alembic.ini                    # Database migration configuration
├── gunicorn.conf.py               # Production server configuration
├── env.example                    # Environment variable template
│
└── Documentation Files:
    ├── README.md                  # Quick project intro
    ├── README_PYTHON.md           # Detailed features and usage
    ├── ARCHITECTURE.md            # System architecture documentation
    ├── STOCKR_BACKBONE_ARCHITECTURE.md  # Stock data system details
    ├── DESIGN_PHILOSOPHY.md       # UI/UX design guidelines
    ├── DEPLOYMENT_GUIDE.md        # Production deployment instructions
    └── [15+ other .md files]      # Various documentation
```

---

## 6. Setup & Running Instructions

### Prerequisites
- Python 3.8+ (3.11 recommended)
- pip package manager
- Git

### Local Development Setup

```bash
# 1. Clone the repository
git clone <repository-url>
cd robinhood-dashboard

# 2. Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # Mac/Linux
# venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment (optional)
cp env.example .env
# Edit .env with your settings

# 5. Run the application
python run.py
```

### Access Points (Development)
| URL | Purpose |
|-----|---------|
| http://localhost:8000/ | Home page |
| http://localhost:8000/dashboard | Main dashboard |
| http://localhost:8000/upload | CSV upload page |
| http://localhost:8000/portfolios | Portfolio list |
| http://localhost:8000/api/docs | Swagger API documentation |

### Required Environment Variables

```bash
# Database (required)
DATABASE_URL=sqlite:///./portfolio.db          # Local SQLite
# OR
POSTGRES_URL=postgresql://user:pass@host/db    # Production PostgreSQL

# Optional API Keys (for extended functionality)
ALPHA_VANTAGE_KEY=your_key_here
FINNHUB_KEY=your_key_here

# Stockr Backbone Database Path
STOCKR_DB_PATH=./stockr_backbone/stockr.db

# Application Settings
DEBUG=True                    # Enable debug mode
SECRET_KEY=your-secret-key    # Session security

# Server Configuration
HOST=0.0.0.0
PORT=8000

# CORS (production)
CORS_ORIGINS=https://yourdomain.com
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_api.py -v

# Run with coverage
pytest tests/ --cov=api --cov-report=html
```

### Database Management

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Reset database (development only)
python -c "from src.database import reset_db; reset_db()"
```

### Production Deployment

```bash
# Using Gunicorn (recommended)
gunicorn src.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# Using Docker
docker build -t robinhood-analysis .
docker run -p 8000:8000 robinhood-analysis
```

---

## 7. Key Implementation Details

### Notable Design Patterns

1. **Service Layer Pattern**: Business logic separated into service modules (`price_service`, `analysis_service`, `blob_service`) distinct from route handlers

2. **Dependency Injection**: FastAPI's `Depends()` used for database session management:
   ```python
   def portfolios_list(db: Session = Depends(get_db)):
   ```

3. **Repository Pattern** (implicit): SQLAlchemy models provide data access abstraction

4. **Background Worker Pattern**: stockr_backbone runs continuous maintenance in a daemon thread, independent of request handling

### Complex/Custom Components

#### stockr_backbone (Critical Core)

The most important internal component. Key characteristics:

- **Location**: `stockr_backbone/src/`
- **Database**: Separate SQLite at `stockr_backbone/stockr.db`
- **Tables**: `stocks` (tracked symbols), `historical_prices` (OHLCV data)
- **Data Source**: Stooq.com API (free, no rate limits when cached)

**Key Functions:**
| Function | Purpose |
|----------|---------|
| `fetch_and_store(symbol)` | Fetch and cache stock data |
| `ensure_stock_tracked(symbol)` | Auto-discovery - add new tickers |
| `refresh_all_stocks()` | Batch update all tracked stocks |

**Auto-Discovery Flow:**
```
Request for unknown ticker → Stock not in DB → ensure_stock_tracked() called →
Fetch from Stooq.com → Store in local DB → Mark as permanently tracked →
Background service maintains automatically
```

#### Price Service with Resilience

`api/services/price_service.py` implements robust data fetching:
- Retry with exponential backoff (3 attempts)
- Period fallback (1y → 6mo if data unavailable)
- Custom headers to avoid blocking
- Forward/backward fill for missing data

#### Analysis Service

`api/services/analysis_service.py` calculates:
- Portfolio daily values from holdings × prices
- Percentage returns vs initial value
- Benchmark comparison (SPY default)
- Handles edge cases (zero initial value, missing data)

### Important Configuration Files

| File | Purpose |
|------|---------|
| `vercel.json` | Routes all requests to `api/index.py`, uses `@vercel/python` build |
| `alembic.ini` | Database migration configuration, points to `migrations/` |
| `gunicorn.conf.py` | Production server: UvicornWorker, 120s timeout, CPU-based worker count |
| `.github/workflows/deploy.yml` | CI pipeline: test → build Docker → push GHCR → deploy |

### UI Design Philosophy

From `DESIGN_PHILOSOPHY.md`:
- **Primary**: Robinhood-style radical minimalism (one goal per screen)
- **Secondary**: Cyberpunk accents (neon cyan/green, subtle scanlines, glassmorphism)
- **Color Palette**:
  - Background: `#0a0a0a` (deep black), `#12121e` (cards)
  - Accents: `#00ffff` (cyan), `#00ff88` (positive), `#ff3366` (negative)
  - Text: `#e0e0e0` (primary), `#8888aa` (secondary)
- **Neon Effects**: Limited to <15% screen area, medium intensity on key values

---

## 8. Current Status & Known Issues

### What Works Well

- **Core Infrastructure**: FastAPI application, database setup, route structure
- **API Endpoints**: All documented endpoints return correct data structures
- **Page Loading**: Upload, Dashboard, Analysis, Comparison pages load correctly
- **CSV Processing**: Flexible column detection and parsing
- **Price Service**: yfinance integration with retry logic
- **Vercel Deployment**: Serverless function operational

### Known Bugs / Critical Issues

#### CRITICAL: Charts Not Loading
- **Problem**: Dashboard charts show "No price data" - all portfolio values are 0.0
- **Root Cause**: Missing stock price data for certain tickers (BITU, AGQ, TSLL, SBIT, TSDD - leveraged/inverse ETFs)
- **Impact**: Core functionality blocked - users cannot see portfolio performance
- **Status**: Documented in `CRITICAL_ISSUES_SUMMARY.md`

#### MEDIUM: Text Rendering Issues
- **Problem**: Navigation text appears truncated/garbled ("Dashboard" → "Da hboard")
- **Possible Causes**: CSS text-overflow, font loading, character encoding
- **Impact**: Cosmetic - functionality not affected

### Unfinished Features / TODOs

1. **Vercel PostgreSQL Integration**: Currently using `/tmp` storage (resets on cold starts)
2. **Stock Data Population**: stockr_backbone may need manual population for exotic tickers
3. **File Upload Workflow**: Requires manual testing with actual CSV files
4. **Linting Configuration**: Placeholder in CI/CD pipeline
5. **Health Check URLs**: Placeholder in deployment pipeline

### Recent Development Focus

Based on git history, recent work focused on **stockr_backbone subprocess execution fixes**:
```
f67b1ec - fix: use sys.executable in subprocess to run fetcher.py with venv
799b491 - fix: subprocess run fetcher.py in src dir
b3f382f - fix: temp sys.path + __package__ for relative config import
```

This indicates active debugging of the stock data population system, specifically around:
- Python virtual environment path handling
- Module import resolution
- Subprocess execution from the correct directory

### Architecture Maturity

The project has comprehensive documentation (19+ markdown files) indicating significant design effort. The `stockr_backbone` component is marked as "CRITICAL CORE" throughout documentation, suggesting it's the foundation that other features depend on.

---

## Summary

**Robinhood Portfolio Analysis Dashboard** is a Python/FastAPI web application that provides retail investors with professional-grade portfolio analytics. The key differentiator is the **stockr_backbone** internal stock data system that maintains historical prices locally, enabling features like custom portfolio backtesting and benchmark comparisons without hitting external API rate limits.

The application is currently deployed on Vercel as a serverless function, with PostgreSQL for persistent storage. The cyberpunk-themed UI uses server-side rendering with Jinja2 and interactive Plotly.js charts.

**Critical Path Items:**
1. Fix missing stock price data for charts to render
2. Complete Vercel PostgreSQL integration for data persistence
3. Ensure stockr_backbone auto-discovery works for all ticker types

The codebase is well-documented and follows modern Python web development patterns, making it maintainable and extensible for future feature development.
