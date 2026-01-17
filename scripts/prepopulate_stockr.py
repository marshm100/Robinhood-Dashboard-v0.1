import os

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
STOCKR_SRC = os.path.join(PROJECT_ROOT, "stockr_backbone", "src")

if not os.path.exists(STOCKR_SRC):
    raise FileNotFoundError(f"stockr_backbone/src not found at {STOCKR_SRC} — check submodule")

print(f"Changing directory to {STOCKR_SRC} for imports...")
os.chdir(STOCKR_SRC)

# Now imports resolve (config is relative to src)
from fetcher import batch_fetch

# Change back optional, but good practice
os.chdir(SCRIPT_DIR)

if __name__ == "__main__":
    print("Current dir restored:", os.getcwd())
    print("Running batch_fetch() for all tickers in tickers.txt...")
    batch_fetch()
    print("Batch fetch complete!")
    print("stockr_backbone/stockr.db has been updated with fresh data.")