#!/usr/bin/env python3
"""
Test Phase 4 Advanced Analytics functionality
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_advanced_analytics():
    """Test Phase 4 advanced analytics features"""
    print("=" * 60)
    print("Testing Phase 4: Advanced Analytics")
    print("=" * 60)

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
            print(f"[OK] Loaded {len(transactions_df)} sample transactions")

        # Test portfolio calculator
        calculator = PortfolioCalculator(db)

        # Test position weights (4.2.1)
        print("\n--- Testing Position Weights ---")
        weights = calculator.calculate_position_weights()
        print(f"[OK] Position weights calculated: {len(weights)} positions")
        if weights:
            top_3 = sorted(weights.items(), key=lambda x: x[1], reverse=True)[:3]
            print(f"[OK] Top positions: {top_3}")

        # Test diversification metrics (4.2.2)
        print("\n--- Testing Diversification Metrics ---")
        diversification = calculator.calculate_diversification_metrics()
        print(f"[OK] Diversification metrics calculated")
        print(f"[OK] Effective bets: {diversification.get('effective_bets', 0)}")
        print(f"[OK] Diversification score: {diversification.get('diversification_score', 0)}%")

        # Test sector allocation (4.2.3)
        print("\n--- Testing Sector Allocation ---")
        sector_allocation = calculator.get_sector_allocation()
        print(f"[OK] Sector allocation calculated: {sector_allocation.get('sector_count', 0)} sectors")
        if sector_allocation.get('largest_sector'):
            sector, weight = sector_allocation['largest_sector']
            print(f"[OK] Largest sector: {sector} ({weight}%)")

        # Test market conditions (4.1.2)
        print("\n--- Testing Market Conditions ---")
        market_conditions = calculator.analyze_market_conditions()
        conditions = market_conditions.get('market_conditions', {})
        print(f"[OK] Market conditions analyzed")
        print(f"[OK] Bull market days: {conditions.get('bull_market_days', 0)}")
        print(f"[OK] Bear market days: {conditions.get('bear_market_days', 0)}")

        # Test benchmarking (4.1.1, 4.1.3)
        print("\n--- Testing Benchmarking ---")
        tracking_error = calculator.calculate_tracking_error()
        print(f"[OK] Tracking error: {tracking_error}%")

        information_ratio = calculator.calculate_information_ratio()
        print(f"[OK] Information ratio: {information_ratio}")

        beta_metrics = calculator.calculate_beta_coefficient()
        print(f"[OK] Beta coefficient: {beta_metrics.get('beta', 0)}")

        # Test optimization recommendations (4.2.4, 4.2.5, 4.2.6)
        print("\n--- Testing Optimization Recommendations ---")
        optimization = calculator.get_portfolio_optimization_recommendations()
        print(f"[OK] Optimization recommendations generated")
        print(f"[OK] Risk level: {optimization.get('risk_level', 'unknown')}")
        print(f"[OK] Recommendations: {len(optimization.get('recommendations', []))}")

        # Test comprehensive advanced analytics
        print("\n--- Testing Comprehensive Advanced Analytics ---")
        advanced = calculator.get_advanced_analytics()
        print(f"[OK] Advanced analytics compiled successfully")
        print(f"[OK] Contains {len(advanced)} analytical categories")

        print("\n" + "=" * 60)
        print("🎉 Phase 4 Advanced Analytics: ALL TESTS PASSED")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"[FAIL] Phase 4 test error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_advanced_analytics()
    sys.exit(0 if success else 1)
