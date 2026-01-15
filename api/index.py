import os
from pathlib import Path
from fastapi import FastAPI

print("\n" + "="*60)
print("VERCEL SUCCESS: LOADING api/index.py – OLD src/ IS GONE!")
print("If you see this in function logs → entrypoint fixed!")
print("Working dir:", os.getcwd())
print("="*60 + "\n")

TMP = Path("/tmp")
DATA = TMP / "data"
UPLOAD = DATA / "uploads"
STOCKR = DATA / "stockr_backbone"
TEMP = DATA / "temp"

for p in [DATA, UPLOAD, STOCKR, TEMP]:
    try:
        p.mkdir(parents=True, exist_ok=True)
        print(f"Created: {p}")
    except Exception as e:
        print(f"mkdir warning {p}: {e}")

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{TMP}/data/portfolio.db")
STOCKR_DB_PATH = os.getenv("STOCKR_DB_PATH", f"{TMP}/data/stockr_backbone/stockr.db")

app = FastAPI(title="Robinhood Dashboard – Vercel Live")

@app.get("/")
def home():
    return {
        "status": "LIVE ON VERCEL 🚀",
        "message": "Old src/ deleted – read-only crash fixed",
        "tmp": str(TMP),
        "upload_dir": str(UPLOAD),
        "db": DATABASE_URL
    }

@app.on_event("startup")
async def startup():
    print("FastAPI ready – accepting requests\n")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("index:app", host="0.0.0.0", port=8000, reload=True)