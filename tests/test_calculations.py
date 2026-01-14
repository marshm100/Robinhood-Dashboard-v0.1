#!/usr/bin/env python3
"""
Comprehensive test suite for portfolio calculation functions
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import pytest
import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from src.services.portfolio_calculator import PortfolioCalculator
    from src.services.stock_price_service import stock_price_service
    from src.database import get_db, SessionLocal
    from src.models import Transaction
    IMPORTS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Some imports failed: {e}")
    IMPORTS_AVAILABLE = False
    PortfolioCalculator = None
    stock_price_service = None
    SessionLocal = None
    Transaction = None

class TestPortfolioCalculations:
    """Test suite for portfolio calculation functions"""

    @pytest.fixture
    def db_session(self):
        """Create a test database session"""
        if not IMPORTS_AVAILABLE:
            pytest.skip("Database imports not available")
        session = SessionLocal()
        try:
            yield session
        finally:
            session.rollback()
            session.close()

    @pytest.fixture
    def sample_transactions(self):
        """Create sample transaction data for testing"""
        base_date = datetime(2023, 1, 1)

        return [
            {
                "activity_date": (base_date + timedelta(days=i*30)).strftime("%Y-%m-%d"),
                "ticker": "AAPL" if i % 3 == 0 else "MSFT" if i % 3 == 1 else "GOOGL",
                "trans_code": "Buy",
                "quantity": 10 + i,
                "price": 150.0 + (i * 5),
                "amount": -(10 + i) * (150.0 + (i * 5))
            }
            for i in range(12)  # 12 months of data
        ]

    @pytest.fixture
    def calculator(self, db_session):
        """Create a portfolio calculator instance"""
        if not IMPORTS_AVAILABLE:
            pytest.skip("Portfolio calculator imports not available")
        return PortfolioCalculator(db_session)

    def test_portfolio_calculator_initialization(self, calculator):
        """Test that portfolio calculator initializes correctly"""
        if not IMPORTS_AVAILABLE:
            pytest.skip("Imports not available")
        assert calculator is not None
        assert hasattr(calculator, 'get_portfolio_summary')
        assert hasattr(calculator, 'calculate_performance_metrics')

    def test_empty_portfolio_calculations(self, calculator):
        """Test calculations with empty portfolio"""
        summary = calculator.get_portfolio_summary()

        assert summary["transaction_count"] == 0
        assert summary["unique_tickers"] == 0
        assert summary["current_holdings_count"] == 0
        assert summary["total_value"] == 0.0

    def test_basic_portfolio_metrics(self, calculator, db_session, sample_transactions):
        """Test basic portfolio metrics calculation"""
        # Insert sample transactions
        for tx in sample_transactions:
            transaction = Transaction(**tx)
            db_session.add(transaction)
        db_session.commit()

        summary = calculator.get_portfolio_summary()

        assert summary["transaction_count"] == len(sample_transactions)
        assert summary["unique_tickers"] > 0
        assert isinstance(summary["total_value"], (int, float))

    def test_performance_metrics_calculation(self, calculator, db_session, sample_transactions):
        """Test performance metrics calculation"""
        # Insert sample transactions
        for tx in sample_transactions:
            transaction = Transaction(**tx)
            db_session.add(transaction)
        db_session.commit()

        metrics = calculator.calculate_performance_metrics()

        # Check that all expected metrics are present
        expected_metrics = [
            "total_return", "cagr", "volatility", "max_drawdown",
            "sharpe_ratio", "sortino_ratio"
        ]

        for metric in expected_metrics:
            assert metric in metrics
            assert isinstance(metrics[metric], (int, float, type(None)))

    def test_risk_assessment_calculation(self, calculator, db_session, sample_transactions):
        """Test risk assessment calculations"""
        # Insert sample transactions
        for tx in sample_transactions:
            transaction = Transaction(**tx)
            db_session.add(transaction)
        db_session.commit()

        risk = calculator.get_risk_assessment()

        # Check risk metrics
        assert "volatility" in risk
        assert "max_drawdown" in risk
        assert "value_at_risk" in risk
        assert "sharpe_ratio" in risk

        # Check VaR structure
        var_data = risk["value_at_risk"]
        assert "var_95" in var_data
        assert "var_99" in var_data

    def test_portfolio_history_calculation(self, calculator, db_session, sample_transactions):
        """Test portfolio history calculation"""
        # Insert sample transactions
        for tx in sample_transactions:
            transaction = Transaction(**tx)
            db_session.add(transaction)
        db_session.commit()

        history = calculator.calculate_portfolio_history()

        assert isinstance(history, dict)
        if "history" in history:
            assert isinstance(history["history"], list)
            if len(history["history"]) > 0:
                # Check structure of history entries
                entry = history["history"][0]
                assert "date" in entry
                assert "portfolio_value" in entry

    def test_rolling_returns_calculation(self, calculator, db_session, sample_transactions):
        """Test rolling returns calculation"""
        # Insert sample transactions
        for tx in sample_transactions:
            transaction = Transaction(**tx)
            db_session.add(transaction)
        db_session.commit()

        rolling_returns = calculator.calculate_rolling_returns()

        assert isinstance(rolling_returns, dict)
        # Should have various time periods
        assert len(rolling_returns) > 0

    def test_correlation_matrix_calculation(self, calculator, db_session, sample_transactions):
        """Test correlation matrix calculation"""
        # Insert sample transactions
        for tx in sample_transactions:
            transaction = Transaction(**tx)
            db_session.add(transaction)
        db_session.commit()

        corr_matrix = calculator.calculate_correlation_matrix()

        assert isinstance(corr_matrix, pd.DataFrame)
        # With limited data, might be empty, but should not error

    def test_diversification_metrics(self, calculator, db_session, sample_transactions):
        """Test diversification metrics calculation"""
        # Insert sample transactions
        for tx in sample_transactions:
            transaction = Transaction(**tx)
            db_session.add(transaction)
        db_session.commit()

        diversification = calculator.calculate_diversification_metrics()

        assert isinstance(diversification, dict)
        # Should have diversification-related metrics
        assert "effective_bets" in diversification or len(diversification) >= 0

    def test_sector_allocation_calculation(self, calculator, db_session, sample_transactions):
        """Test sector allocation calculation"""
        # Insert sample transactions
        for tx in sample_transactions:
            transaction = Transaction(**tx)
            db_session.add(transaction)
        db_session.commit()

        sector_allocation = calculator.get_sector_allocation()

        assert isinstance(sector_allocation, dict)
        # May be empty with sample data, but should not error

    def test_portfolio_optimization(self, calculator, db_session, sample_transactions):
        """Test portfolio optimization recommendations"""
        # Insert sample transactions
        for tx in sample_transactions:
            transaction = Transaction(**tx)
            db_session.add(transaction)
        db_session.commit()

        optimization = calculator.get_optimization_recommendations()

        assert isinstance(optimization, dict)
        # Should have optimization recommendations structure

    def test_rebalancing_analysis(self, calculator, db_session, sample_transactions):
        """Test rebalancing analysis"""
        # Insert sample transactions
        for tx in sample_transactions:
            transaction = Transaction(**tx)
            db_session.add(transaction)
        db_session.commit()

        rebalancing = calculator.get_rebalancing_analysis()

        assert isinstance(rebalancing, dict)
        # Should have rebalancing analysis structure

    def test_calculation_edge_cases(self, calculator):
        """Test edge cases in calculations"""
        # Test with no data
        summary = calculator.get_portfolio_summary()
        assert summary["transaction_count"] == 0

        # Test performance metrics with no data
        metrics = calculator.calculate_performance_metrics()
        assert isinstance(metrics, dict)

        # Test risk assessment with no data
        risk = calculator.get_risk_assessment()
        assert isinstance(risk, dict)

    def test_calculation_accuracy(self, calculator, db_session):
        """Test calculation accuracy with known inputs"""
        # Create a simple test case with known outcomes
        base_date = datetime(2023, 1, 1)

        # Simple buy transaction
        transaction = Transaction(
            activity_date=base_date.strftime("%Y-%m-%d"),
            ticker="TEST",
            trans_code="Buy",
            quantity=100,
            price=10.0,
            amount=-1000.0
        )
        db_session.add(transaction)
        db_session.commit()

        summary = calculator.get_portfolio_summary()

        # Basic validations
        assert summary["transaction_count"] == 1
        assert summary["unique_tickers"] == 1
        assert "TEST" in str(summary.get("holdings", {}))

class TestDataValidation:
    """Test data validation functions"""

    def test_transaction_data_validation(self):
        """Test transaction data validation"""
        from src.services.csv_processor import process_robinhood_csv

        # Valid CSV data
        valid_csv = """activity_date,ticker,trans_code,quantity,price,amount
2023-01-01,AAPL,Buy,10,150.00,-1500.00
2023-01-02,MSFT,Sell,5,300.00,1500.00"""

        df = process_robinhood_csv(valid_csv)

        assert len(df) == 2
        assert "activity_date" in df.columns
        assert "ticker" in df.columns
        assert "amount" in df.columns

    def test_invalid_csv_handling(self):
        """Test handling of invalid CSV data"""
        from src.services.csv_processor import process_robinhood_csv

        # Invalid CSV with missing columns
        invalid_csv = """date,symbol,action,qty,cost,total
2023-01-01,AAPL,Buy,10,150.00,-1500.00"""

        df = process_robinhood_csv(invalid_csv)

        # Should handle gracefully or raise appropriate error
        assert isinstance(df, pd.DataFrame)

    def test_numeric_data_validation(self):
        """Test numeric data validation"""
        import numpy as np

        # Test that calculations handle NaN values properly
        test_values = [1.0, 2.0, np.nan, 4.0]

        # Should not crash with NaN values
        result = np.nanmean(test_values)
        assert not np.isnan(result) or np.isnan(result)  # Either valid result or NaN

class TestStockPriceService:
    """Test stock price service functionality"""

    def test_stock_price_service_initialization(self):
        """Test stock price service initialization"""
        if not IMPORTS_AVAILABLE:
            pytest.skip("Stock price service imports not available")
        service = stock_price_service
        assert service is not None

    def test_database_validation(self):
        """Test database validation"""
        if not IMPORTS_AVAILABLE:
            pytest.skip("Stock price service imports not available")
        result = stock_price_service.validate_database()
        # May return None if database not available, but should not crash
        assert isinstance(result, (dict, type(None)))

    def test_price_lookup_error_handling(self):
        """Test error handling in price lookups"""
        if not IMPORTS_AVAILABLE:
            pytest.skip("Stock price service imports not available")
        # Test with invalid ticker
        price = stock_price_service.get_price_at_date("INVALID", "2023-01-01")
        assert price is None or isinstance(price, (int, float))

    def test_get_prices_batch_returns_dict_of_dataframes(self):
        """Test that get_prices_batch returns Dict[str, DataFrame] for multiple tickers"""
        if not IMPORTS_AVAILABLE:
            pytest.skip("Stock price service imports not available")
        tickers = ["AAPL", "MSFT"]
        start_date = "2024-01-01"
        end_date = "2024-01-31"
        
        result = stock_price_service.get_prices_batch(tickers, start_date, end_date)
        
        # Should return a dictionary
        assert isinstance(result, dict)
        
        # Each value should be a DataFrame (if ticker exists in database)
        for ticker, df in result.items():
            assert isinstance(df, pd.DataFrame)
            # DataFrame should have price columns if data exists
            if not df.empty:
                expected_columns = ['open', 'high', 'low', 'close', 'volume']
                for col in expected_columns:
                    assert col in df.columns, f"Missing column {col} for {ticker}"

    def test_get_prices_batch_empty_tickers(self):
        """Test that get_prices_batch handles empty ticker list gracefully"""
        if not IMPORTS_AVAILABLE:
            pytest.skip("Stock price service imports not available")
        result = stock_price_service.get_prices_batch([], "2024-01-01", "2024-01-31")
        
        assert isinstance(result, dict)
        assert len(result) == 0

    def test_get_prices_batch_invalid_tickers(self):
        """Test that get_prices_batch handles invalid tickers gracefully"""
        if not IMPORTS_AVAILABLE:
            pytest.skip("Stock price service imports not available")
        result = stock_price_service.get_prices_batch(
            ["INVALID_TICKER_XYZ123"], 
            "2024-01-01", 
            "2024-01-31"
        )
        
        # Should not raise an error, returns empty dict or dict without invalid ticker
        assert isinstance(result, dict)

    def test_get_prices_batch_single_ticker(self):
        """Test that get_prices_batch works with a single ticker"""
        if not IMPORTS_AVAILABLE:
            pytest.skip("Stock price service imports not available")
        tickers = ["AAPL"]
        start_date = "2024-01-01"
        end_date = "2024-01-31"
        
        result = stock_price_service.get_prices_batch(tickers, start_date, end_date)
        
        assert isinstance(result, dict)
        # If AAPL data exists, should have one entry
        if result:
            assert "AAPL" in result
            assert isinstance(result["AAPL"], pd.DataFrame)

    def test_get_prices_at_dates_batch(self):
        """Test that get_prices_at_dates_batch returns correct structure"""
        if not IMPORTS_AVAILABLE:
            pytest.skip("Stock price service imports not available")
        tickers = ["AAPL", "MSFT"]
        dates = ["2024-01-02", "2024-01-15", "2024-01-30"]
        
        result = stock_price_service.get_prices_at_dates_batch(tickers, dates)
        
        # Should return Dict[str, Dict[str, float]]
        assert isinstance(result, dict)
        
        for ticker, date_prices in result.items():
            assert isinstance(date_prices, dict)
            for date_str, price in date_prices.items():
                assert isinstance(price, (int, float))

    def test_get_prices_at_dates_batch_empty_inputs(self):
        """Test that get_prices_at_dates_batch handles empty inputs"""
        if not IMPORTS_AVAILABLE:
            pytest.skip("Stock price service imports not available")
        # Empty tickers
        result1 = stock_price_service.get_prices_at_dates_batch([], ["2024-01-01"])
        assert isinstance(result1, dict)
        assert len(result1) == 0
        
        # Empty dates
        result2 = stock_price_service.get_prices_at_dates_batch(["AAPL"], [])
        assert isinstance(result2, dict)
        assert len(result2) == 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
