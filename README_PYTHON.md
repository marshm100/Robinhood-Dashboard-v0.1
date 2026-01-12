# Robinhood Portfolio Analysis - Python Version

A cyberpunk-themed web application for analyzing Robinhood trading data with comprehensive portfolio analytics.

## Features

- **CSV Upload & Processing**: Secure upload and processing of Robinhood transaction CSV files
- **Portfolio Tracking**: Real-time calculation of holdings and portfolio values
- **Performance Analytics**: Total returns, CAGR, rolling returns, and percentile rankings
- **Risk Assessment**: Volatility, VaR, Sharpe ratio, maximum drawdown calculations
- **Market Benchmarking**: Performance comparison against market indices
- **Asset Allocation**: Diversification analysis and concentration risk assessment
- **Interactive Visualizations**: Charts powered by Plotly.js with cyberpunk styling
- **⭐ Custom Portfolio Creation**: Create hypothetical portfolios with any asset allocation ⭐ CORE FEATURE
- **⭐ Portfolio Comparison**: Compare custom portfolios against your Robinhood portfolio and benchmarks like SPY ⭐ CORE FEATURE
- **⭐ Backtesting Engine**: Historical performance simulation for custom portfolios ⭐ CORE FEATURE
- **Educational Features**: Interactive tooltips and contextual financial education
- **⭐ stockr_backbone Database**: Core database system providing historical stock price data for all features ⭐ CORE COMPONENT

## Tech Stack

- **Backend**: FastAPI (Python web framework)
- **Database**: SQLite with SQLAlchemy ORM
- **Data Processing**: Pandas, NumPy
- **Visualization**: Plotly.js
- **Frontend**: HTML/CSS/JavaScript with Tailwind CSS
- **Styling**: Custom cyberpunk theme with neon colors and effects

## Quick Start

### Prerequisites
- Python 3.8+
- pip

### Installation

1. **Clone and setup**:
   ```bash
   git clone <repository-url>
   cd robinhood-dashboard
   python -m venv venv
   venv\Scripts\activate  # Windows
   # source venv/bin/activate  # Mac/Linux
   pip install -r requirements.txt
   ```

2. **Run the application**:
   ```bash
   python run.py
   ```

3. **Access the application**:
   - Dashboard: http://localhost:8000/dashboard
   - Upload CSV: http://localhost:8000/upload
   - API Docs: http://localhost:8000/api/docs

## Usage

1. **Upload Data**: Go to the upload page and drag/drop your Robinhood CSV file
2. **View Dashboard**: See portfolio overview, performance metrics, and holdings
3. **Analyze Performance**: Explore detailed analytics and risk metrics
4. **⭐ Create Custom Portfolios**: Build hypothetical portfolios with custom asset allocations ⭐ CORE FEATURE
5. **⭐ Compare Portfolios**: Compare your Robinhood portfolio against custom portfolios and benchmarks like SPY ⭐ CORE FEATURE
6. **⭐ Backtest Strategies**: See how different investment strategies would have performed historically ⭐ CORE FEATURE

## Core Architecture: stockr_backbone Database

**⭐ CRITICAL CORE COMPONENT ⭐**

The application depends on the **stockr_backbone database** for all stock price data. This is a **FOUNDATIONAL CORE** component that:

- Provides historical stock price data for portfolio valuation
- Enables custom portfolio backtesting with accurate historical data
- Supplies benchmark data (SPY, QQQ, etc.) for comparisons
- Automatically maintains and refreshes stock data in the background
- Auto-discovers and tracks new stocks as they're encountered

**The stockr_backbone database is automatically started when the application starts.** Check `/health` or `/api/stockr-status` to verify it's running.

**Without stockr_backbone, portfolio valuations, custom portfolio backtesting, and benchmark comparisons would not be possible.**

## Project Structure

```
src/
├── main.py              # FastAPI application entry point
├── config.py            # Application settings
├── database.py          # Database connection and setup
├── models.py            # SQLAlchemy database models
├── routes/
│   ├── api.py          # REST API endpoints
│   └── web.py          # Web page routes
├── services/
│   ├── csv_processor.py    # CSV parsing and validation
│   ├── portfolio_calculator.py  # Portfolio calculations
│   └── custom_portfolio_service.py  # ⭐ Custom portfolio creation and comparison ⭐ CORE
├── models.py               # Database models (includes CustomPortfolio, PortfolioSnapshot)
└── templates/           # HTML templates
    ├── dashboard.html
    └── upload.html
```

## API Endpoints

### Core Endpoints
- `GET /api/health` - API health check (includes stockr_backbone status)
- `POST /api/validate-csv` - Validate CSV structure
- `POST /api/upload-csv` - Upload and process CSV
- `GET /api/portfolio-overview` - Get portfolio summary
- `GET /api/transactions` - Get paginated transactions

### ⭐ Custom Portfolio Endpoints (CORE FEATURES)
- `POST /api/custom-portfolios` - Create a custom portfolio
- `GET /api/custom-portfolios` - List all custom portfolios
- `GET /api/custom-portfolios/{id}` - Get portfolio details
- `PUT /api/custom-portfolios/{id}` - Update portfolio
- `DELETE /api/custom-portfolios/{id}` - Delete portfolio
- `POST /api/custom-portfolios/{id}/backtest` - Backtest portfolio over date range
- `POST /api/portfolio-comparison` - Compare multiple portfolios, benchmarks, and Robinhood portfolio
- `GET /api/benchmarks/{ticker}` - Get benchmark data (SPY, QQQ, etc.)

### Web Pages
- `GET /dashboard` - Main dashboard
- `GET /upload` - CSV upload page
- `GET /analysis` - Portfolio analysis
- `GET /comparison` - ⭐ Portfolio comparison and custom portfolio creation ⭐ CORE FEATURE

## Configuration

Create a `.env` file in the root directory:

```env
# Database
DATABASE_URL=sqlite:///./portfolio.db

# Application
DEBUG=True
SECRET_KEY=your-secret-key

# Server
HOST=0.0.0.0
PORT=8000
```

## Development

### Running Tests
```bash
pytest tests/
```

### Database Management
```bash
# Reset database
python -c "from src.database import reset_db; reset_db()"

# Create migration
alembic revision --autogenerate -m "message"

# Run migration
alembic upgrade head
```

## Deployment

### Docker Deployment
```bash
docker build -t robinhood-analysis .
docker run -p 8000:8000 robinhood-analysis
```

### Production Server
For production, use a WSGI server like Gunicorn:
```bash
pip install gunicorn
gunicorn src.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
