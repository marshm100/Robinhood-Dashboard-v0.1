import os
from pathlib import Path

# Vercel serverless: force writable paths to /tmp
TMP_ROOT = Path("/tmp")
DATA_DIR = TMP_ROOT / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
STOCKR_DIR = DATA_DIR / "stockr_backbone"
TEMP_DIR = DATA_DIR / "temp"

for d in [DATA_DIR, UPLOAD_DIR, STOCKR_DIR, TEMP_DIR]:
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Warning: mkdir {d} failed: {e}")

# Database paths
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{TMP_ROOT}/data/portfolio.db")
STOCKR_DB_PATH = os.getenv("STOCKR_DB_PATH", f"{TMP_ROOT}/data/stockr_backbone/stockr.db")

# Other settings (add your original ones here later)
SECRET_KEY = os.getenv("SECRET_KEY", "temp-secret-change-me")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")