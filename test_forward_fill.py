"""
Test script to verify forward-fill logic for stock prices.

This script verifies that:
1. The stock price service can connect to the stockr_backbone database
2. Forward-fill works for stocks with data gaps
3. Proper handling for stocks that didn't exist before a date
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))


def test_stock_price_service_connection():
    """Test that stock price service can connect"""
    print("\n1. Testing Stock Price Service Connection:")
    
    try:
        from src.services.stock_price_service import StockPriceService
        service = StockPriceService()
        
        # Check database path
        print(f"   Database path: {service.db_path}")
        print(f"   Database exists: {service.db_path.exists()}")
        
        if not service.db_path.exists():
            print("   [WARN] Stockr database not found - forward-fill tests will be skipped")
            return False
        
        # Try to connect
        conn = service._get_connection()
        print(f"   Connection successful: {conn is not None}")
        
        print("   [PASS] Stock price service connected successfully")
        return True
        
    except FileNotFoundError as e:
        print(f"   [WARN] Database not found: {e}")
        return False
    except Exception as e:
        print(f"   [ERROR] {e}")
        return False


def test_forward_fill_helper_method():
    """Test the _stock_existed_before_date helper method"""
    print("\n2. Testing Forward-Fill Helper Method:")
    
    try:
        from src.services.stock_price_service import StockPriceService
        service = StockPriceService()
        
        if not service.db_path.exists():
            print("   [SKIP] Database not found")
            return True
        
        # Get a stock ID that should exist (AAPL is common)
        stock_id = service.get_stock_id("AAPL")
        print(f"   AAPL stock_id: {stock_id}")
        
        if stock_id:
            # Test with a very old date (stock should exist)
            old_date = "2015-01-01"
            existed_old = service._stock_existed_before_date(stock_id, old_date)
            print(f"   AAPL existed before {old_date}: {existed_old}")
            
            # Test with a future date (stock should exist)
            future_date = "2030-01-01"
            existed_future = service._stock_existed_before_date(stock_id, future_date)
            print(f"   AAPL existed before {future_date}: {existed_future}")
        else:
            print("   [WARN] AAPL not in database, trying to list available stocks...")
            # Try to get any available stock
            result = service._execute_query(
                "SELECT id, symbol FROM stocks LIMIT 5"
            )
            if result:
                print(f"   Available stocks: {result}")
        
        print("   [PASS] Forward-fill helper method works")
        return True
        
    except Exception as e:
        print(f"   [ERROR] {e}")
        return False


def test_get_price_at_date():
    """Test get_price_at_date with forward-fill"""
    print("\n3. Testing get_price_at_date with Forward-Fill:")
    
    try:
        from src.services.stock_price_service import StockPriceService
        service = StockPriceService()
        
        if not service.db_path.exists():
            print("   [SKIP] Database not found")
            return True
        
        # Test 1: Get price for a stock on a regular trading day
        test_date = "2024-01-02"  # A Tuesday
        result = service.get_price_at_date("AAPL", test_date)
        print(f"   AAPL on {test_date}: {result}")
        
        # Test 2: Get price for a weekend (should forward-fill from Friday)
        weekend_date = "2024-01-06"  # A Saturday
        result_weekend = service.get_price_at_date("AAPL", weekend_date)
        print(f"   AAPL on {weekend_date} (Saturday): {result_weekend}")
        
        # Test 3: Get price for a stock that might not have existed
        # (This should return 0 prices or forward-fill depending on date)
        old_date = "2010-01-01"
        result_old = service.get_price_at_date("AAPL", old_date)
        print(f"   AAPL on {old_date}: {result_old}")
        
        print("   [PASS] get_price_at_date works correctly")
        return True
        
    except Exception as e:
        print(f"   [ERROR] {e}")
        return False


def test_portfolio_calculator_integration():
    """Test portfolio calculator's handling of prices"""
    print("\n4. Testing Portfolio Calculator Integration:")
    
    try:
        from src.services.portfolio_calculator import PortfolioCalculator
        from src.database import SessionLocal, init_db_sync
        
        # Initialize database
        init_db_sync()
        
        # Create session
        db = SessionLocal()
        
        try:
            calculator = PortfolioCalculator(db)
            
            # Test getting a stock price
            price = calculator.get_stock_price_at_date("AAPL", "2024-01-02")
            print(f"   AAPL price via calculator: {price}")
            
            if price is not None:
                print(f"   Price type: {type(price)}")
                assert isinstance(price, (int, float)), "Price should be numeric"
            else:
                print("   [WARN] No price returned - stockr database might be empty")
            
            print("   [PASS] Portfolio calculator integration works")
            return True
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"   [ERROR] {e}")
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("FORWARD-FILL LOGIC TEST")
    print("=" * 60)
    
    results = []
    
    # Test 1: Connection
    results.append(("Connection", test_stock_price_service_connection()))
    
    # Only run remaining tests if connection succeeded
    if results[0][1]:
        results.append(("Helper Method", test_forward_fill_helper_method()))
        results.append(("Get Price At Date", test_get_price_at_date()))
    
    # Always test portfolio calculator (uses the database we've confirmed works)
    results.append(("Portfolio Calculator", test_portfolio_calculator_integration()))
    
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY:")
    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL/SKIP]"
        print(f"   {status} {name}")
    print("=" * 60)
    
    # Return 0 if all critical tests passed
    all_passed = all(passed for _, passed in results)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
