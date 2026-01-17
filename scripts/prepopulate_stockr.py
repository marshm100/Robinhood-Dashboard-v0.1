import os
import sys
import importlib.util

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
SRC_PATH = os.path.join(PROJECT_ROOT, "stockr_backbone", "src")
FETCHER_PATH = os.path.join(SRC_PATH, "fetcher.py")

if not os.path.exists(FETCHER_PATH):
    raise FileNotFoundError(f"fetcher.py not found at {FETCHER_PATH}")

print(f"Temporarily adding {SRC_PATH} to sys.path for relative imports...")
sys.path.insert(0, SRC_PATH)

print(f"Loading fetcher module from {FETCHER_PATH}...")

spec = importlib.util.spec_from_file_location("stockr_backbone.src.fetcher", FETCHER_PATH)
fetcher_module = importlib.util.module_from_spec(spec)
fetcher_module.__package__ = "stockr_backbone.src"  # Critical for relative imports like 'from config...'
spec.loader.exec_module(fetcher_module)

# Clean up path
sys.path.pop(0)
print("sys.path restored")

if not hasattr(fetcher_module, "batch_fetch"):
    raise AttributeError("batch_fetch function not found in fetcher.py")

batch_func = fetcher_module.batch_fetch
print("batch_fetch loaded successfully!")

if __name__ == "__main__":
    print("Executing batch_fetch for all tickers in tickers.txt...")
    batch_func()
    print("Batch fetch complete! stockr_backbone/stockr.db is now fully populated.")