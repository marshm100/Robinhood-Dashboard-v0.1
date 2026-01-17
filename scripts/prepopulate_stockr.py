import os
import sys
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
SRC_PATH = os.path.join(PROJECT_ROOT, "stockr_backbone", "src")
FETCHER_PATH = os.path.join(SRC_PATH, "fetcher.py")

if not os.path.exists(FETCHER_PATH):
    raise FileNotFoundError(f"fetcher.py not found at {FETCHER_PATH}")

print(f"Executing fetcher.py using venv Python: {sys.executable}")
print(f"in directory {SRC_PATH}...")

result = subprocess.run(
    [sys.executable, "fetcher.py"],
    cwd=SRC_PATH,
    capture_output=True,
    text=True
)

print("=== STDOUT ===")
print(result.stdout or "(no output)")
print("=== STDERR ===")
print(result.stderr or "(no errors)")
print("=== RETURN CODE ===")
print(result.returncode)

if result.returncode != 0:
    raise RuntimeError(f"fetcher.py failed with code {result.returncode}. Check STDERR above.")

print("Batch fetch complete! stockr_backbone/stockr.db updated with fresh Stooq data.")