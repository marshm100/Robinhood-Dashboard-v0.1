# Robinhood Portfolio Analysis 📊

*A cyberpunk-themed financial analysis tool that transforms your Robinhood trading data into professional-grade investment insights*

![Portfolio Dashboard](docs/ui_aesthetic_1.jpg)

**🟢 LIVE & READY**: Fully functional application with 100% Robinhood CSV compatibility verified!

---

## 🚀 What is This?

Robinhood Portfolio Analysis transforms your Robinhood trading history into beautiful, professional financial reports. Upload your CSV, get instant access to:

- **Portfolio Performance** - Interactive charts showing your investment journey
- **Risk Analysis** - Sharpe ratio, volatility, maximum drawdown, VaR
- **Custom Portfolio Backtesting** - Test "what if" scenarios with historical data
- **Benchmark Comparison** - Compare your portfolio against SPY, QQQ, and custom portfolios
- **Educational Content** - Learn financial concepts as you explore

All wrapped in a stunning cyberpunk-themed dark UI.

---

## 📖 Documentation

| Document | Purpose |
|----------|---------|
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | Complete technical architecture for developers and AI agents |
| **[DESIGN_PHILOSOPHY.md](DESIGN_PHILOSOPHY.md)** | UI/UX design principles and guidelines |
| **[CORE_FEATURES.md](CORE_FEATURES.md)** | Core feature documentation |
| **[STOCKR_BACKBONE_ARCHITECTURE.md](STOCKR_BACKBONE_ARCHITECTURE.md)** | Stock database system architecture |
| **[MASTER_IMPLEMENTATION_PLAN.md](MASTER_IMPLEMENTATION_PLAN.md)** | Development roadmap and task tracking |

---

## 🚀 Quick Start

### Option 1: Local Python

```bash
# Clone repository
git clone https://github.com/marshm100/Robinhood-Dashboard-v0.1.git
cd Robinhood-Dashboard-v0.1

# Install dependencies
pip install -r requirements.txt

# Start application
python run.py

# Open http://localhost:8000
```

### Option 2: Docker

```bash
# Development
docker-compose up -d

# Production
docker-compose -f docker-compose.prod.yml up -d
```

### Access Points

| URL | Description |
|-----|-------------|
| http://localhost:8000 | Main application |
| http://localhost:8000/upload | Upload CSV file |
| http://localhost:8000/dashboard | Portfolio dashboard |
| http://localhost:8000/analysis | Deep analysis |
| http://localhost:8000/comparison | Portfolio comparison |
| http://localhost:8000/api/docs | API documentation |
| http://localhost:8000/health | Health check |

---

## 📋 CSV Compatibility

**✅ 100% Compatible** with standard Robinhood CSV exports containing:

| Column | Format | Example |
|--------|--------|---------|
| Activity Date | MM/DD/YYYY | 01/15/2024 |
| Instrument | Ticker symbol | AAPL |
| Trans Code | Transaction type | Buy, Sell, CDIV |
| Quantity | Number (decimals OK) | 10.5 |
| Price | Dollar amount | $150.00 |
| Amount | Transaction total | ($1,575.00) |

**Supported Transaction Types:** Buy, Sell, CDIV (dividends), RTP, ACH (transfers), MISC

---

## ✨ Key Features

### 📈 Portfolio Performance

- Real-time portfolio valuation
- Interactive growth charts (Plotly.js)
- CAGR, total return calculations
- Rolling returns analysis
- Historical value tracking

### 🎯 Risk Analysis

- **Volatility** - Standard deviation of returns
- **Sharpe Ratio** - Risk-adjusted performance
- **Sortino Ratio** - Downside risk-adjusted return
- **Maximum Drawdown** - Largest peak-to-trough decline
- **Value at Risk (VaR)** - 95% and 99% confidence levels
- **Beta** - Market correlation coefficient

### 🔄 Custom Portfolio Creation & Backtesting

Create hypothetical portfolios and see how they would have performed:

1. **Create Portfolio** - Set asset allocations (e.g., 50% AAPL, 30% MSFT, 20% GOOGL)
2. **Choose Strategy** - Lump sum or dollar-cost averaging
3. **Backtest** - Simulate historical performance
4. **Compare** - Side-by-side comparison with your Robinhood portfolio and benchmarks

### 📊 Portfolio Comparison

Compare your portfolio against:
- Custom hypothetical portfolios
- Market benchmarks (SPY, QQQ)
- Historical performance charts
- Risk/return scatter plots

### 🎨 Cyberpunk Design

- Dark theme with neon accents
- Glassmorphism card effects
- Interactive Plotly.js charts
- Mobile responsive
- Educational tooltips

---

## 🏗️ Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                    ROBINHOOD PORTFOLIO ANALYSIS                   │
│                                                                    │
│  ┌────────────────┐   ┌────────────────┐   ┌────────────────┐   │
│  │   Dashboard    │   │    Analysis    │   │   Comparison   │   │
│  │   (Charts)     │   │   (Metrics)    │   │  (Backtest)    │   │
│  └───────┬────────┘   └───────┬────────┘   └───────┬────────┘   │
│          │                    │                    │              │
│          └────────────────────┼────────────────────┘              │
│                               │                                    │
│                     ┌─────────▼─────────┐                         │
│                     │   FastAPI Backend │                         │
│                     │   - Routes (API)  │                         │
│                     │   - Services      │                         │
│                     │   - Calculations  │                         │
│                     └─────────┬─────────┘                         │
│                               │                                    │
│          ┌────────────────────┼────────────────────┐              │
│          │                    │                    │              │
│  ┌───────▼────────┐   ┌───────▼────────┐   ┌───────▼────────┐   │
│  │  Transactions  │   │ Stock Prices   │   │   Custom       │   │
│  │  Database      │   │ (stockr_bb)    │   │   Portfolios   │   │
│  └────────────────┘   └────────────────┘   └────────────────┘   │
│                                                                    │
│  ⭐ CORE: stockr_backbone provides ALL stock price data           │
│     - Auto-refreshes every 60 minutes                             │
│     - Auto-discovers new tickers                                  │
│     - No external API keys required                               │
└──────────────────────────────────────────────────────────────────┘
```

**For complete architecture details, see [ARCHITECTURE.md](ARCHITECTURE.md)**

---

## 🔧 Technology Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI, Python 3.11+, SQLAlchemy |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Frontend | Jinja2 Templates, Plotly.js, CSS |
| Stock Data | stockr_backbone (internal database) |
| Deployment | Docker, Gunicorn, Nginx, Railway |

---

## 🔒 Security & Privacy

- **Local Processing** - Your data stays on your device/server
- **No Data Storage** - We don't save personal information
- **Secure Uploads** - Input validation and sanitization
- **HTTPS Ready** - Production encryption support

---

## 🆘 Troubleshooting

### Application won't start

```bash
# Check dependencies
pip install -r requirements.txt

# Check port availability
# Port 8000 must be free

# Try production runner
python run_prod.py
```

### Charts not displaying

- Check `/health` endpoint for stockr_backbone status
- Verify stock data exists: `/api/available-stocks`
- Check browser console for JavaScript errors

### CSV upload fails

- Ensure CSV has required columns: Activity Date, Trans Code, Amount
- Check file encoding is UTF-8
- Verify file size < 10MB

### Stock prices missing

- stockr_backbone auto-fetches missing tickers
- Wait 60 seconds for background refresh
- Check `/api/stockr-status` for service health

---

## 📈 API Reference

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/upload-csv` | POST | Upload Robinhood CSV |
| `/api/portfolio-overview` | GET | Full portfolio summary |
| `/api/performance-metrics` | GET | Performance calculations |
| `/api/risk-assessment` | GET | Risk metrics |
| `/api/custom-portfolios` | POST | Create custom portfolio |
| `/api/portfolio-comparison` | POST | Compare portfolios |
| `/health` | GET | System health check |

**Full API documentation:** http://localhost:8000/api/docs

---

## 🌐 Deployment

### Local Development

```bash
python run.py
# OR
uvicorn src.main:app --reload
```

### Docker Production

```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Railway Deployment

The application is optimized for Railway deployment:
- Automatic Docker detection and deployment
- Persistent storage via mounted volumes (`./data`)
- Set environment variables in Railway dashboard

---

## 📄 License

This project is open source under the MIT License.

### Disclaimer

**Not Financial Advice**: This tool is for educational and informational purposes only. Past performance doesn't guarantee future results. Always consult qualified financial advisors for investment decisions.

---

## 🙏 Acknowledgments

- **Open Source**: FastAPI, Plotly, Pandas, SQLAlchemy
- **Data Source**: Stooq.com for historical stock prices
- **Inspiration**: Robinhood's clean, educational UI design

---

## 📞 Support

- **Issues**: GitHub Issues
- **API Docs**: `/api/docs` endpoint
- **Health Check**: `/health` endpoint

---

**Version:** 1.0.1  
**Last Updated:** January 2026  
**Status:** ✅ Production Ready

---

*Built with ❤️ for the modern investor*
