"""
Step 0.1: Diagnose Missing Stock Price Data

This script checks the stockr_backbone database for missing tickers:
BITU, AGQ, TSLL, SBIT, TSDD

It will:
1. Check if these tickers exist in the stocks table
2. Check if historical_prices has data for them
3. Check the date range of available data
4. Document findings
"""

import sqlite3
import os
import sys
from pathlib import Path
from datetime import datetime

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def diagnose_missing_tickers():
    """Diagnose missing stock price data in the stockr_backbone database"""
    
    # Target tickers to check
    TARGET_TICKERS = ['BITU', 'AGQ', 'TSLL', 'SBIT', 'TSDD']
    
    # Database path
    project_root = Path(__file__).parent
    db_path = project_root / "stockr_backbone" / "stock_data.db"
    
    print("=" * 60)
    print("STEP 0.1: Diagnose Missing Stock Price Data")
    print("=" * 60)
    print(f"\nTarget tickers: {', '.join(TARGET_TICKERS)}")
    print(f"Database path: {db_path}")
    
    # Check if database exists
    if not db_path.exists():
        print(f"\n❌ DATABASE NOT FOUND at {db_path}")
        print("\n[FINDINGS] DIAGNOSIS FINDINGS:")
        print("-" * 40)
        print("1. The stockr_backbone database does not exist")
        print("2. This means ALL tickers are missing (not just the target ones)")
        print("3. The database needs to be initialized first")
        print("\n[ACTION] RECOMMENDED ACTIONS:")
        print("1. Initialize the database: python stockr_backbone/scripts/db_setup.py")
        print("2. Then run the fetcher to populate data")
        return {
            'database_exists': False,
            'missing_tickers': TARGET_TICKERS,
            'tickers_in_db': [],
            'tickers_with_prices': [],
            'action_needed': 'Initialize database'
        }
    
    print(f"\n[OK] Database found at {db_path}")
    
    # Connect to database
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    findings = {
        'database_exists': True,
        'missing_tickers': [],
        'tickers_in_db': [],
        'tickers_with_prices': [],
        'date_ranges': {}
    }
    
    # Check database tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"\n📊 Database tables: {tables}")
    
    # 1. Check which tickers exist in stocks table
    print("\n" + "=" * 60)
    print("1. CHECKING STOCKS TABLE")
    print("=" * 60)
    
    cursor.execute("SELECT symbol, id, ephemeral FROM stocks")
    all_stocks = {row[0]: {'id': row[1], 'ephemeral': row[2]} for row in cursor.fetchall()}
    
    print(f"Total stocks in database: {len(all_stocks)}")
    
    for ticker in TARGET_TICKERS:
        if ticker in all_stocks:
            stock_info = all_stocks[ticker]
            ephemeral_str = "(ephemeral)" if stock_info['ephemeral'] else "(permanent)"
            print(f"  [OK] {ticker}: Found in stocks table (id={stock_info['id']}) {ephemeral_str}")
            findings['tickers_in_db'].append(ticker)
        else:
            print(f"  ❌ {ticker}: NOT FOUND in stocks table")
            findings['missing_tickers'].append(ticker)
    
    # 2. Check historical_prices for found tickers
    print("\n" + "=" * 60)
    print("2. CHECKING HISTORICAL_PRICES TABLE")
    print("=" * 60)
    
    for ticker in findings['tickers_in_db']:
        stock_id = all_stocks[ticker]['id']
        
        # Count records
        cursor.execute(
            "SELECT COUNT(*) FROM historical_prices WHERE stock_id = ?",
            (stock_id,)
        )
        count = cursor.fetchone()[0]
        
        if count > 0:
            # Get date range
            cursor.execute(
                """SELECT MIN(date), MAX(date) FROM historical_prices 
                   WHERE stock_id = ?""",
                (stock_id,)
            )
            min_date, max_date = cursor.fetchone()
            
            print(f"  [OK] {ticker}: {count} price records")
            print(f"      Date range: {min_date} to {max_date}")
            findings['tickers_with_prices'].append(ticker)
            findings['date_ranges'][ticker] = {
                'count': count,
                'min_date': min_date,
                'max_date': max_date
            }
        else:
            print(f"  [MISSING] {ticker}: NO price records (stock exists but no data)")
    
    # 3. Check tickers.txt to see if they're configured
    print("\n" + "=" * 60)
    print("3. CHECKING tickers.txt CONFIGURATION")
    print("=" * 60)
    
    tickers_file = project_root / "stockr_backbone" / "tickers.txt"
    if tickers_file.exists():
        with open(tickers_file, 'r') as f:
            configured_tickers = [line.strip().upper() for line in f if line.strip()]
        
        for ticker in TARGET_TICKERS:
            if ticker in configured_tickers:
                print(f"  ✅ {ticker}: Configured in tickers.txt")
            else:
                print(f"  [MISSING] {ticker}: NOT configured in tickers.txt")
    else:
        print(f"  ⚠️ tickers.txt not found at {tickers_file}")
    
    # Summary
    print("\n" + "=" * 60)
    print("[SUMMARY] DIAGNOSIS SUMMARY")
    print("=" * 60)
    
    missing = [t for t in TARGET_TICKERS if t not in findings['tickers_with_prices']]
    
    if not missing:
        print("✅ All target tickers have price data!")
    else:
        print(f"❌ Missing tickers ({len(missing)}): {', '.join(missing)}")
        
        not_in_stocks = [t for t in TARGET_TICKERS if t not in findings['tickers_in_db']]
        no_prices = [t for t in findings['tickers_in_db'] if t not in findings['tickers_with_prices']]
        
        if not_in_stocks:
            print(f"\n   Not in stocks table: {', '.join(not_in_stocks)}")
        if no_prices:
            print(f"   In stocks but no prices: {', '.join(no_prices)}")
    
    print("\n[ACTION] RECOMMENDED NEXT STEPS:")
    if findings['missing_tickers']:
        print("1. Add missing tickers to stockr_backbone/tickers.txt (Step 0.2)")
        print("2. Run the fetcher to populate data (Step 0.3)")
    elif [t for t in findings['tickers_in_db'] if t not in findings['tickers_with_prices']]:
        print("1. Run the fetcher to populate price data (Step 0.3)")
    else:
        print("[OK] No action needed - all target tickers have data")
    
    conn.close()
    
    print("\n" + "=" * 60)
    print("Diagnosis complete!")
    print("=" * 60)
    
    return findings


if __name__ == "__main__":
    findings = diagnose_missing_tickers()
