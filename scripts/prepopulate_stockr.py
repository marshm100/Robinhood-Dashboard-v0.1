import os
import sys
# Add project root to path if needed for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "stockr_backbone", "src")))

# Import the correct fetch function based on your inspection
from fetcher import batch_fetch

TICKERS_FILE = "stockr_backbone/tickers.txt"

if not os.path.exists(TICKERS_FILE):
    raise FileNotFoundError(f"{TICKERS_FILE} not found")

print("Reading tickers...")
with open(TICKERS_FILE, "r") as f:
    tickers = [line.strip().upper() for line in f if line.strip() and not line.startswith("#")]

print(f"Pre-populating {len(tickers)} tickers...")

# No need to loop through tickers individually if batch_fetch handles it
# Call the discovered fetch function — force refresh if possible
batch_fetch() # This function reads tickers.txt internally and fetches all

print("Pre-population complete!")
print("Next: Run this script locally, then 'git add stockr_backbone/stockr.db' and commit/push the updated DB.")