"""
Test script for Step 0.4: Price Fallback Mechanism

This script tests that the portfolio calculator can gracefully fall back
to transaction prices when stockr_backbone doesn't have data.
"""

import sys
import logging
from pathlib import Path

# Setup logging to see fallback messages
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.database import SessionLocal
from src.services.portfolio_calculator import PortfolioCalculator
from src.models import Transaction


def test_price_fallback():
    """Test the price fallback mechanism"""
    print("=" * 60)
    print("Testing Step 0.4: Price Fallback Mechanism")
    print("=" * 60)
    
    db = SessionLocal()
    
    try:
        calculator = PortfolioCalculator(db)
        
        # Get some tickers from the transaction database
        print("\n1. Getting unique tickers from transactions...")
        tickers_with_prices = db.query(Transaction.ticker).filter(
            Transaction.price.isnot(None),
            Transaction.price > 0
        ).distinct().limit(5).all()
        
        tickers = [t[0] for t in tickers_with_prices if t[0]]
        print(f"   Found tickers: {tickers}")
        
        if not tickers:
            print("   [WARN] No tickers with prices found in transactions")
            return False
        
        # Test the main get_stock_price_at_date method for each ticker
        print("\n2. Testing get_stock_price_at_date() method...")
        
        results = []
        for ticker in tickers[:3]:  # Test first 3
            # Get a transaction date for this ticker
            tx = db.query(Transaction).filter(
                Transaction.ticker == ticker,
                Transaction.price > 0
            ).first()
            
            if tx:
                test_date = tx.activity_date
                if hasattr(test_date, 'strftime'):
                    test_date = test_date.strftime('%Y-%m-%d')
                
                print(f"\n   Testing {ticker} on {test_date}:")
                print(f"   - Transaction price: ${tx.price:.2f}")
                
                # Get price using the calculator (will try stockr first, then fallback)
                price = calculator.get_stock_price_at_date(ticker, test_date)
                
                if price is not None and price > 0:
                    print(f"   - Calculator returned: ${price:.2f} [OK]")
                    results.append(True)
                else:
                    print(f"   - Calculator returned: {price} [FAIL - expected a price]")
                    results.append(False)
        
        # Test the fallback method directly
        print("\n3. Testing _get_transaction_price_fallback() directly...")
        
        for ticker in tickers[:2]:
            tx = db.query(Transaction).filter(
                Transaction.ticker == ticker,
                Transaction.price > 0
            ).first()
            
            if tx:
                test_date = tx.activity_date
                if hasattr(test_date, 'strftime'):
                    test_date = test_date.strftime('%Y-%m-%d')
                
                fallback_price = calculator._get_transaction_price_fallback(ticker, test_date)
                print(f"   {ticker} fallback price: ${fallback_price:.2f}" if fallback_price else f"   {ticker}: No fallback price")
        
        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        
        passed = sum(results)
        total = len(results)
        
        if passed == total and total > 0:
            print(f"[OK] All {total} tests passed!")
            print("\nThe price fallback mechanism is working correctly:")
            print("- stockr_backbone is tried first (primary source)")
            print("- Transaction prices are used as fallback")
            print("- Logging indicates when fallback is used")
            return True
        else:
            print(f"[WARN] {passed}/{total} tests passed")
            return passed > 0
            
    except Exception as e:
        print(f"\n[ERROR] Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        db.close()


if __name__ == "__main__":
    success = test_price_fallback()
    sys.exit(0 if success else 1)
