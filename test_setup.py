#!/usr/bin/env python3
"""
Test script to verify the application setup and stock price integration
"""

import sys
import os
from pathlib import Path

def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")

    try:
        # Test basic imports
        import sqlalchemy
        print("[OK] SQLAlchemy imported")

        import fastapi
        print("[OK] FastAPI imported")

        import pandas as pd
        print("[OK] Pandas imported")

        # Test our modules
        from src.config import settings
        print("[OK] Config imported")

        from src.database import init_db, get_db
        print("[OK] Database imported")

        from src.models import Transaction, StockPrice
        print("[OK] Models imported")

        # Test services individually to avoid relative import issues
        from src.services.csv_processor import process_robinhood_csv
        print("[OK] CSV processor imported")

        from src.services.stock_price_service import StockPriceService
        print("[OK] Stock price service imported")

        return True
    except Exception as e:
        print(f"✗ Import error: {e}")
        return False

def test_stock_database():
    """Test stock price database connection"""
    print("\nTesting stock database...")

    try:
        from src.services.stock_price_service import StockPriceService

        service = StockPriceService()
        result = service.validate_database()
        print(f"Stock database validation: {result}")

        if result['valid']:
            print(f"✓ Database valid with {result['stock_count']} stocks and {result['price_records']} price records")

            # Test a sample stock lookup
            stocks = service.get_available_stocks()
            if stocks:
                sample_stock = stocks[0]['symbol']
                print(f"✓ Sample stock available: {sample_stock}")

                # Test price lookup
                price_data = service.get_price_at_date(sample_stock, "2023-01-01")
                if price_data:
                    print(f"✓ Sample price data retrieved for {sample_stock}")
                else:
                    print(f"⚠ No price data found for {sample_stock} on 2023-01-01 (may be normal)")
            else:
                print("⚠ No stocks found in database")
        else:
            print(f"✗ Database validation failed: {result.get('error', 'Unknown error')}")

        return result['valid']

    except Exception as e:
        print(f"✗ Stock database test error: {e}")
        return False

def test_database_setup():
    """Test that our local database can be initialized"""
    print("\nTesting local database setup...")

    try:
        from src.database import init_db
        init_db()
        print("✓ Local database initialized successfully")
        return True
    except Exception as e:
        print(f"✗ Local database setup error: {e}")
        return False

def test_portfolio_calculations():
    """Test portfolio calculation functionality"""
    print("\nTesting portfolio calculations...")

    try:
        from src.database import get_db
        from src.services import PortfolioCalculator
        from src.services.csv_processor import process_robinhood_csv
        from src.models import Transaction

        # Get database session
        db = next(get_db())

        # Load sample transaction data if not already loaded
        transaction_count = db.query(Transaction).count()
        if transaction_count == 0:
            print("Loading sample transaction data...")
            # Read sample CSV
            with open("sample_transactions.csv", "r", encoding="utf-8") as f:
                csv_content = f.read()

            # Process CSV
            transactions_df = process_robinhood_csv(csv_content)

            # Save to database
            for _, row in transactions_df.iterrows():
                transaction = Transaction(
                    activity_date=row['activity_date'],
                    ticker=row.get('ticker'),
                    trans_code=row['trans_code'],
                    quantity=row.get('quantity'),
                    price=row.get('price'),
                    amount=row['amount']
                )
                db.add(transaction)
            db.commit()
            print(f"✓ Loaded {len(transactions_df)} sample transactions")

        # Test portfolio calculator
        calculator = PortfolioCalculator(db)

        # Test holdings calculation
        holdings = calculator.get_current_holdings()
        print(f"✓ Current holdings calculated: {len(holdings)} positions")

        # Test performance metrics
        performance = calculator.calculate_performance_metrics()
        print(f"✓ Performance metrics calculated: Total Return {performance.get('total_return', 0)}%")

        # Test risk assessment
        risk = calculator.get_risk_assessment()
        print(f"✓ Risk assessment calculated: Volatility {risk.get('volatility', 0)}%")

        # Test portfolio history
        history = calculator.get_portfolio_value_history()
        print(f"✓ Portfolio history calculated: {len(history)} data points")

        # Test advanced analytics (Phase 4)
        advanced = calculator.get_advanced_analytics()
        print(f"✓ Advanced analytics calculated: {len(advanced.get('position_weights', {}))} positions")

        # Test sector allocation
        sector_allocation = calculator.get_sector_allocation()
        print(f"✓ Sector allocation calculated: {sector_allocation.get('sector_count', 0)} sectors")

        # Test optimization recommendations
        optimization = calculator.get_portfolio_optimization_recommendations()
        print(f"✓ Optimization recommendations generated: {len(optimization.get('recommendations', []))} recommendations")

        # Test market conditions
        market_conditions = calculator.analyze_market_conditions()
        print(f"✓ Market conditions analyzed: {len(market_conditions.get('market_conditions', {}))} metrics")

        # Test benchmarking
        tracking_error = calculator.calculate_tracking_error()
        print(f"✓ Tracking error calculated: {tracking_error}%")

        information_ratio = calculator.calculate_information_ratio()
        print(f"✓ Information ratio calculated: {information_ratio}")

        return True

    except Exception as e:
        print(f"✗ Portfolio calculation test error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("Robinhood Portfolio Analysis - Setup Test")
    print("=" * 50)

    all_passed = True

    # Test imports
    all_passed &= test_imports()

    # Test local database
    all_passed &= test_database_setup()

    # Test portfolio calculations
    all_passed &= test_portfolio_calculations()

    # Test stock database
    all_passed &= test_stock_database()

    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All tests passed! Ready to run the application.")
        print("Run: python run.py")
    else:
        print("❌ Some tests failed. Please check the errors above.")
    print("=" * 50)

