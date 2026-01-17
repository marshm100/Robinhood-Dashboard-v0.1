import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
STOCKR_SRC = os.path.join(PROJECT_ROOT, "stockr_backbone", "src")

if not os.path.exists(STOCKR_SRC):
    raise FileNotFoundError(f"stockr_backbone/src not found at {STOCKR_SRC}")

print(f"Changing to {STOCKR_SRC}...")
os.chdir(STOCKR_SRC)

# Diagnostic: list files
print("Files in src/:")
print(os.listdir("."))

# Correct import — adjust based on actual filename (likely fetcher.py)
try:
    import fetcher
    batch_func = fetcher.batch_fetch
    print("Imported fetcher.batch_fetch successfully")
except ImportError as e:
    print(f"Import failed: {e}")
    raise

# Restore cwd
os.chdir(SCRIPT_DIR)
print(f"Restored cwd: {os.getcwd()}")

if __name__ == "__main__":
    print("Starting batch_fetch for all tickers...")
    batch_func()  # Call the function
    print("Batch fetch complete! stockr.db updated.")