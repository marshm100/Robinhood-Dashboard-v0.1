"""Test portfolio overview to find the error"""
from src.database import SessionLocal
from src.services import PortfolioCalculator
import traceback

db = SessionLocal()
try:
    calc = PortfolioCalculator(db)
    print("Testing get_portfolio_summary...")
    summary = calc.get_portfolio_summary()
    print(f"✅ get_portfolio_summary works!")
    print(f"Transaction count: {summary.get('transaction_count', 0)}")
    
    print("\nTesting calculate_performance_metrics...")
    perf = calc.calculate_performance_metrics()
    print("✅ calculate_performance_metrics works!")
    
    print("\nTesting get_risk_assessment...")
    risk = calc.get_risk_assessment()
    print("✅ get_risk_assessment works!")
    
    print("\nTesting get_advanced_analytics...")
    analytics = calc.get_advanced_analytics()
    print("✅ get_advanced_analytics works!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    traceback.print_exc()
finally:
    db.close()





