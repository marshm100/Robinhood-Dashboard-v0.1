import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.config import CORS_ORIGINS, DATABASE_URL
from fastapi import Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, selectinload
from api.database import get_db
from api.models.portfolio import Portfolio
from api.services.analysis_service import calculate_portfolio_returns
from api.services.price_service import run_daily_price_update

print("\n" + "="*80)
print("VERCEL: Full app restoring – api/index.py loaded")
print("DB URL:", DATABASE_URL)
print("="*80 + "\n")

app = FastAPI(
    title="Robinhood Portfolio Analysis",
    description="Full version on Vercel serverless",
    version="1.0"
)

from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

templates = Jinja2Templates(directory="templates")

app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "title": "Home"})

@app.get("/portfolios", response_class=HTMLResponse)
async def portfolios_list(request: Request, db: Session = Depends(get_db)):
    portfolios = db.query(Portfolio).all()
    return templates.TemplateResponse("portfolios.html", {"request": request, "portfolios": portfolios})

@app.get("/portfolios/{portfolio_id}", response_class=HTMLResponse)
async def portfolio_detail(
    request: Request,
    portfolio_id: int,
    benchmark: str = "SPY",
    period: str = "5y",
    inflation_adjusted: bool = False,
    rebalance: str = "none",
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
    analysis = calculate_portfolio_returns(
        portfolio.holdings, benchmark, period, inflation_adjusted, rebalance
    )
    return templates.TemplateResponse(
        "portfolio_detail.html",
        {"request": request, "portfolio": portfolio, "analysis": analysis},
    )

# --- Internal cron endpoint for daily price cache update ---
@app.get("/api/internal/daily-price-update")
async def daily_price_update():
    results = run_daily_price_update()
    return results

# === Add routers here in next steps ===

@app.on_event("startup")
def startup():
    print("App starting - Vercel serverless")
    from api.database import init_db
    init_db()

from api.routes.health import router as health_router
app.include_router(health_router)

from api.routes.portfolio import router as portfolio_router
app.include_router(portfolio_router)

from api.routes.analysis import router as analysis_router
app.include_router(analysis_router)

from api.routes.stockr import router as stockr_router
app.include_router(stockr_router)

from api.routes.upload import router as upload_router
app.include_router(upload_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("index:app", host="0.0.0.0", port=8000, reload=True)
    # Trigger Vercel redeploy