import os
from pathlib import Path
from fastapi import FastAPI

print("=== VERCEL LOADING api/index.py ===")
print("If you see this in Vercel logs, we are past the import crash!")

# Force ALL writes to /tmp only
TMP_ROOT = Path("/tmp")
DATA_DIR = TMP_ROOT / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
STOCKR_DIR = DATA_DIR / "stockr_backbone"
TEMP_DIR = DATA_DIR / "temp"

for d in [DATA_DIR, UPLOAD_DIR, STOCKR_DIR, TEMP_DIR]:
    try:
        d.mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {d}")
    except Exception as e:
        print(f"Warning: could not create {d}: {e}")

# Hard-coded defaults using /tmp
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{TMP_ROOT}/data/portfolio.db")
STOCKR_DB_PATH = os.getenv("STOCKR_DB_PATH", f"{TMP_ROOT}/data/stockr_backbone/stockr.db")
upload_path = UPLOAD_DIR

app = FastAPI(
    title="Robinhood Portfolio Analysis",
    description="Temporary Vercel serverless version – data in /tmp",
    version="vercel-tmp"
)

@app.get("/")
def root():
    return {
        "status": "alive on Vercel!",
        "message": "Successfully bypassed read-only filesystem crash",
        "tmp_root": str(TMP_ROOT),
        "upload_dir": str(UPLOAD_DIR),
        "database_url": DATABASE_URL,
        "stockr_path": STOCKR_DB_PATH
    }

@app.on_event("startup")
async def startup_event():
    print("=== FastAPI app startup complete ===")
    print("Serverless function ready")

# Local dev only
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("index:app", host="0.0.0.0", port=8000, reload=True)
