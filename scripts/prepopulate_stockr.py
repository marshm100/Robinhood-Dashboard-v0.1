import os
import sys
import importlib.util

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
SRC_PATH = os.path.join(PROJECT_ROOT, "stockr_backbone", "src")
FETCHER_PATH = os.path.join(SRC_PATH, "fetcher.py")

if not os.path.exists(FETCHER_PATH):
    raise FileNotFoundError(f"fetcher.py not found at {FETCHER_PATH}")

print(f"Temporarily adding {SRC_PATH} to sys.path...")
sys.path.insert(0, SRC_PATH)
print("sys.path[0]:", sys.path[0])

print(f"Loading fetcher module as flat 'fetcher' from {FETCHER_PATH}...")

spec = importlib.util.spec_from_file_location("fetcher", FETCHER_PATH)  # Flat name
fetcher_module = importlib.util.module_from_spec(spec)
# Do not set __package__ — let absolute imports use sys.path
spec.loader.exec_module(fetcher_module)

sys.path.pop(0)
print("sys.path restored")

if not hasattr(fetcher_module, "batch_fetch"):
    raise AttributeError("batch_fetch not found — check function name in fetcher.py")

batch_func = fetcher_module.batch_fetch
print("batch_fetch loaded successfully!")

if __name__ == "__main__":
    print("Starting batch_fetch...")
    batch_func()
    print("Batch fetch complete! stockr.db updated.")