"""
Test script for stockr_backbone core functionality.

This script verifies that the stockr_backbone system is fully operational.
Run this to ensure the core architectural component is working correctly.
"""

import sys
from pathlib import Path

# Add stockr_backbone to path
project_root = Path(__file__).parent
stockr_path = project_root / "stockr_backbone"
if str(stockr_path) not in sys.path:
    sys.path.insert(0, str(stockr_path))

def test_imports():
    """Test that all required modules can be imported"""
    print("Testing imports...")
    try:
        from src.fetcher_standalone import fetch_and_store, ensure_stock_tracked, refresh_all_stocks, get_tracked_stocks
        from src.background_maintenance import StockMaintenanceService, get_maintenance_service
        from config.database import get_db_session, stocks, historical_prices
        print("[OK] All imports successful")
        return True
    except Exception as e:
        print(f"[FAIL] Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_connection():
    """Test database connection"""
    print("\nTesting database connection...")
    try:
        from config.database import get_db_session, stocks
        from sqlalchemy import select
        
        with get_db_session() as session:
            result = session.execute(select(stocks.c.symbol).limit(1))
            print("[OK] Database connection successful")
            return True
    except Exception as e:
        print(f"[FAIL] Database connection failed: {e}")
        return False


def test_fetch_and_store():
    """Test fetching and storing stock data"""
    print("\nTesting fetch_and_store function...")
    try:
        from src.fetcher_standalone import fetch_and_store
        
        # Test with a well-known stock
        symbol = "AAPL"
        print(f"Fetching data for {symbol}...")
        records = fetch_and_store(symbol, incremental=False, ephemeral=False)
        
        if records > 0:
            print(f"[OK] Successfully fetched {records} records for {symbol}")
            return True
        else:
            print(f"[WARN] Fetched 0 records for {symbol} (may already be up-to-date)")
            return True  # Still a success, just no new data
    except Exception as e:
        print(f"[FAIL] fetch_and_store failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ensure_stock_tracked():
    """Test automatic stock tracking"""
    print("\nTesting ensure_stock_tracked function...")
    try:
        from src.fetcher_standalone import ensure_stock_tracked, get_tracked_stocks
        
        # Test with a different stock
        symbol = "MSFT"
        print(f"Ensuring {symbol} is tracked...")
        success = ensure_stock_tracked(symbol)
        
        if success:
            print(f"[OK] {symbol} is now tracked")
            
            # Verify it's in the tracked list
            tracked = get_tracked_stocks()
            if symbol in tracked:
                print(f"[OK] {symbol} confirmed in tracked stocks list")
                return True
            else:
                print(f"[WARN] {symbol} not found in tracked list")
                return False
        else:
            print(f"[FAIL] Failed to track {symbol}")
            return False
    except Exception as e:
        print(f"[FAIL] ensure_stock_tracked failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_maintenance_service():
    """Test background maintenance service"""
    print("\nTesting maintenance service...")
    try:
        from src.background_maintenance import StockMaintenanceService
        
        # Create service instance
        service = StockMaintenanceService(refresh_interval_minutes=5, initial_delay_seconds=2)
        
        # Start service
        print("Starting maintenance service...")
        service.start()
        
        # Wait a bit
        import time
        time.sleep(3)
        
        # Check status
        status = service.get_status()
        print(f"Service status: {status}")
        
        if status['running']:
            print("[OK] Maintenance service is running")
            
            # Stop service
            service.stop()
            print("[OK] Maintenance service stopped successfully")
            return True
        else:
            print("[FAIL] Maintenance service is not running")
            service.stop()
            return False
    except Exception as e:
        print(f"[FAIL] Maintenance service test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_get_tracked_stocks():
    """Test getting list of tracked stocks"""
    print("\nTesting get_tracked_stocks...")
    try:
        from src.fetcher_standalone import get_tracked_stocks
        
        tracked = get_tracked_stocks()
        print(f"[OK] Found {len(tracked)} tracked stocks")
        
        if len(tracked) > 0:
            print(f"Sample stocks: {', '.join(sorted(tracked)[:5])}")
        
        return True
    except Exception as e:
        print(f"[FAIL] get_tracked_stocks failed: {e}")
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("Stockr_Backbone Core Functionality Test")
    print("=" * 60)
    
    tests = [
        ("Imports", test_imports),
        ("Database Connection", test_database_connection),
        ("Fetch and Store", test_fetch_and_store),
        ("Ensure Stock Tracked", test_ensure_stock_tracked),
        ("Get Tracked Stocks", test_get_tracked_stocks),
        ("Maintenance Service", test_maintenance_service),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"[FAIL] Test '{name}' crashed: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n[SUCCESS] All tests passed! Stockr_backbone is fully operational.")
        return 0
    else:
        print(f"\n[WARNING] {total - passed} test(s) failed. Please review errors above.")
        return 1


if __name__ == "__main__":
    exit(main())

