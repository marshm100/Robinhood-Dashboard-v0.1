"""Test each API method individually"""
from src.database import SessionLocal
from src.services import PortfolioCalculator
import traceback

db = SessionLocal()
try:
    calc = PortfolioCalculator(db)
    
    print("1. Testing get_portfolio_summary...")
    summary = calc.get_portfolio_summary()
    print(f"   OK - Transaction count: {summary.get('transaction_count', 0)}")
    
    print("\n2. Testing calculate_performance_metrics...")
    perf = calc.calculate_performance_metrics()
    print(f"   OK - Keys: {list(perf.keys())}")
    
    print("\n3. Testing get_risk_assessment...")
    risk = calc.get_risk_assessment()
    print(f"   OK - Keys: {list(risk.keys())}")
    
    print("\n4. Testing get_advanced_analytics...")
    analytics = calc.get_advanced_analytics()
    print(f"   OK - Keys: {list(analytics.keys())}")
    
    print("\n5. Testing stock_price_service.validate_database...")
    from src.services import stock_price_service
    stock_db = stock_price_service.validate_database()
    print(f"   OK - Status: {stock_db}")
    
    print("\n✅ All methods work!")
    
except Exception as e:
    print(f"\n❌ Error in method: {e}")
    traceback.print_exc()
finally:
    db.close()





