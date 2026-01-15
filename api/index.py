import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.config import CORS_ORIGINS, DATABASE_URL, STOCKR_DB_PATH, UPLOAD_DIR

print("\n" + "="*80)
print("VERCEL: Full app restoring – api/index.py loaded")
print("DB URL:", DATABASE_URL)
print("Upload dir:", UPLOAD_DIR)
print("="*80 + "\n")

app = FastAPI(
    title="Robinhood Portfolio Analysis",
    description="Full version on Vercel serverless",
    version="1.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check
@app.get("/")
def health():
    return {
        "status": "LIVE ON VERCEL – Phase II",
        "endpoints": [
            "/api/health",
            "/api/portfolios",
            "/api/analysis/compare",
            "/api/stockr/prices/{ticker}"
        ],
        "note": "Core features restoring – /tmp SQLite in use"
    }

# === Add routers here in next steps ===

@app.on_event("startup")
async def startup():
    print("Full FastAPI startup complete")
    from api.database import init_db
    await init_db()

from api.routes.health import router as health_router
app.include_router(health_router)

from api.routes.portfolio import router as portfolio_router
app.include_router(portfolio_router)

from api.routes.analysis import router as analysis_router
app.include_router(analysis_router)

from api.routes.stockr import router as stockr_router
app.include_router(stockr_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("index:app", host="0.0.0.0", port=8000, reload=True)