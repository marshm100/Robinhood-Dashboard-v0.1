import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.config import CORS_ORIGINS, DATABASE_URL
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

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