from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from api.config import CORS_ORIGINS
from api.database import get_db
from api.models.portfolio import Portfolio
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