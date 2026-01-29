import os
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, selectinload

from api.config import CORS_ORIGINS, DATABASE_URL
from api.database import get_db
from api.models.portfolio import Portfolio

print("\n" + "="*80)
print("VERCEL: Full app restoring – api/index.py loaded")
print("DB URL:", DATABASE_URL)
print("="*80 + "\n")

app = FastAPI(
    title="Robinhood Portfolio Analysis",
    description="Full version on Vercel serverless",
    version="1.0"
)

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

# ============== HTML ROUTES (render templates) ==============

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page"""
    return templates.TemplateResponse("index.html", {"request": request, "title": "Home"})


@app.get("/portfolios", response_class=HTMLResponse)
async def portfolios_list(request: Request, db: Session = Depends(get_db)):
    """List all portfolios"""
    portfolios = db.query(Portfolio).all()
    return templates.TemplateResponse("portfolios.html", {"request": request, "portfolios": portfolios})


@app.get("/portfolios/new", response_class=HTMLResponse)
async def portfolio_new(request: Request):
    """Create new portfolio form"""
    return templates.TemplateResponse("portfolio_new.html", {"request": request})


@app.get("/portfolios/{portfolio_id}", response_class=HTMLResponse)
async def portfolio_detail(request: Request, portfolio_id: int, db: Session = Depends(get_db)):
    """Portfolio detail page with holdings and charts"""
    portfolio = db.query(Portfolio).options(selectinload(Portfolio.holdings)).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return templates.TemplateResponse("portfolio_detail.html", {
        "request": request,
        "portfolio": portfolio,
        "holdings": portfolio.holdings
    })


@app.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request, portfolio_id: int = None, db: Session = Depends(get_db)):
    """Upload CSV page"""
    portfolios = db.query(Portfolio).all()
    portfolio = None
    if portfolio_id:
        portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    return templates.TemplateResponse("upload.html", {
        "request": request,
        "portfolios": portfolios,
        "portfolio": portfolio
    })


# ============== STARTUP ==============

@app.on_event("startup")
def startup():
    print("App starting - Vercel serverless")
    from api.database import init_db
    init_db()


# ============== API ROUTERS ==============

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
