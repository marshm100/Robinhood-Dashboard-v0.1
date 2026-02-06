from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, selectinload

from api.config import CORS_ORIGINS
from api.database import get_db
from api.models.portfolio import Portfolio
from api.services.price_service import get_latest_prices, get_cached_history, clear_fetch_errors, get_fetch_errors
from api.services.analysis_service import calculate_portfolio_returns
from api.routes.health import router as health_router
from api.routes.portfolio import router as portfolio_router
from api.routes.analysis import router as analysis_router
from api.routes.stockr import router as stockr_router
from api.routes.upload import router as upload_router

app = FastAPI(
    title="Robinhood Portfolio Dashboard",
    version="1.0",
)

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Page routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "title": "Home"})

@app.get("/portfolios", response_class=HTMLResponse)
async def portfolios_list(request: Request, db: Session = Depends(get_db)):
    portfolios = db.query(Portfolio).all()
    return templates.TemplateResponse("portfolios.html", {"request": request, "portfolios": portfolios})

@app.get("/portfolios/{portfolio_id:int}", response_class=HTMLResponse)
async def portfolio_detail(
    request: Request,
    portfolio_id: int,
    benchmark: str = "SPY",
    period: str = "1y",
    db: Session = Depends(get_db),
):
    portfolio = (
        db.query(Portfolio)
        .options(selectinload(Portfolio.holdings))
        .filter(Portfolio.id == portfolio_id)
        .first()
    )
    if not portfolio:
        return HTMLResponse("<h1>Portfolio not found</h1>", status_code=404)

    benchmark = benchmark.upper().strip()
    holdings_with_values = []
    total_value = 0.0
    chart_data = None
    chart_error = None
    common_start_date = None
    missing_tickers = []
    benchmark_unavailable = False
    error_info = {}

    valid_holdings = [h for h in portfolio.holdings if h.shares and h.shares > 0]

    if valid_holdings:
        # Clear error tracking for this request cycle
        clear_fetch_errors()

        # Dedicated priming loop: prime ALL unique tickers (holdings + benchmark)
        # with full history BEFORE any other processing. This is the single point
        # where external fetches happen — everything after reads from DB cache only.
        unique_tickers = {h.ticker for h in valid_holdings} | {benchmark}
        for t in unique_tickers:
            try:
                get_cached_history(t, period="max")
            except Exception:
                pass  # errors tracked in _fetch_errors

        # Fetch latest prices for the holdings table (cache reads after priming)
        tickers = list({h.ticker for h in valid_holdings})
        try:
            prices = get_latest_prices(tickers)
        except Exception:
            prices = {}

        # Build enriched holdings list
        for h in valid_holdings:
            price = prices.get(h.ticker)
            value = round(price * h.shares, 2) if price is not None else None
            if value is not None:
                total_value += value
            holdings_with_values.append(
                {"ticker": h.ticker, "shares": h.shares, "cost_basis": h.cost_basis,
                 "price": price, "value": value, "pct": None}
            )

        # Compute percentage of portfolio
        if total_value > 0:
            for h in holdings_with_values:
                if h["value"] is not None:
                    h["pct"] = round(h["value"] / total_value * 100, 1)

        # Sort by value descending (holdings with price first)
        holdings_with_values.sort(key=lambda h: h["value"] or 0, reverse=True)

        # Fetch chart data (cache-only reads — all priming already done above)
        try:
            result = calculate_portfolio_returns(valid_holdings, benchmark=benchmark, period=period)
            if "error" in result:
                chart_error = result["error"]
            else:
                chart_data = result
                common_start_date = result.get("common_start")
                missing_tickers = result.get("missing_tickers", [])
                benchmark_unavailable = result.get("benchmark_unavailable", False)
        except Exception as e:
            chart_error = str(e)

        # Collect fetch errors for diagnostic banners
        error_info = get_fetch_errors()

    # Convert holding dicts to simple namespace for dot-access in template
    class HoldingView:
        def __init__(self, d):
            self.__dict__.update(d)

    context = {
        "request": request,
        "portfolio": portfolio,
        "holdings_with_values": [HoldingView(h) for h in holdings_with_values],
        "total_value": total_value,
        "chart_data": chart_data,
        "chart_error": chart_error,
        "current_benchmark": benchmark,
        "current_period": period,
        "common_start_date": common_start_date,
        "missing_tickers": missing_tickers,
        "benchmark_unavailable": benchmark_unavailable,
        "error_info": error_info,
    }
    return templates.TemplateResponse("portfolio_detail.html", context)

# API routes
app.include_router(health_router)
app.include_router(portfolio_router)
app.include_router(analysis_router)
app.include_router(stockr_router)
app.include_router(upload_router)

@app.on_event("startup")
def startup():
    from api.database import init_db
    init_db()