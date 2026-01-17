import os
import importlib.util

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
FETCHER_PATH = os.path.join(PROJECT_ROOT, "stockr_backbone", "src", "fetcher.py")

if not os.path.exists(FETCHER_PATH):
    raise FileNotFoundError(f"fetcher.py not found at {FETCHER_PATH} — check submodule structure")

print(f"Loading fetcher module from {FETCHER_PATH}...")

spec = importlib.util.spec_from_file_location("fetcher", FETCHER_PATH)
fetcher_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetcher_module)

# Diagnostic: confirm function exists
if not hasattr(fetcher_module, "batch_fetch"):
    raise AttributeError("batch_fetch function not found in fetcher.py — inspect the file for the correct name")

batch_func = fetcher_module.batch_fetch
print("batch_fetch loaded successfully")

if __name__ == "__main__":
    print("Starting batch_fetch for all tickers in tickers.txt...")
    batch_func()
    print("Batch fetch complete!")
    print("stockr_backbone/stockr.db updated with fresh data for all tickers.")