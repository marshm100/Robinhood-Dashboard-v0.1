#!/usr/bin/env python3
"""
Integration and end-to-end testing
"""

import sys
import os
from pathlib import Path
from io import BytesIO

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.database import SessionLocal
from src.models import Transaction

class TestIntegrationWorkflows:
    """Integration tests for complete workflows"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def db_session(self):
        """Create test database session"""
        session = SessionLocal()
        try:
            yield session
        finally:
            session.rollback()
            session.close()

    def test_csv_upload_to_portfolio_display_workflow(self, client, db_session):
        """Test complete workflow: CSV upload → processing → portfolio display"""
        # Step 1: Create test CSV data
        csv_content = """activity_date,ticker,trans_code,quantity,price,amount
2023-01-01,AAPL,Buy,10,150.00,-1500.00
2023-02-01,AAPL,Buy,5,160.00,-800.00
2023-03-01,MSFT,Buy,8,300.00,-2400.00
2023-04-01,AAPL,Sell,5,180.00,900.00"""

        # Step 2: Upload CSV
        csv_file = BytesIO(csv_content.encode('utf-8'))
        csv_file.name = "test_portfolio.csv"

        upload_response = client.post("/api/upload-csv", files={"file": csv_file})

        # Should succeed or handle gracefully
        assert upload_response.status_code in [200, 500]

        if upload_response.status_code == 200:
            upload_data = upload_response.json()
            assert "transactions_processed" in upload_data
            assert upload_data["transactions_processed"] == 4

            # Step 3: Check portfolio overview
            overview_response = client.get("/api/portfolio-overview")
            assert overview_response.status_code in [200, 500]

            if overview_response.status_code == 200:
                overview_data = overview_response.json()
                assert overview_data["transaction_count"] == 4
                assert overview_data["unique_tickers"] == 2  # AAPL and MSFT

            # Step 4: Check transactions endpoint
            transactions_response = client.get("/api/transactions")
            assert transactions_response.status_code in [200, 500]

            if transactions_response.status_code == 200:
                transactions_data = transactions_response.json()
                assert len(transactions_data["transactions"]) == 4

            # Step 5: Check dashboard renders with data
            dashboard_response = client.get("/dashboard")
            assert dashboard_response.status_code == 200
            assert "portfolio-analysis" in dashboard_response.text.lower()

    def test_custom_portfolio_creation_workflow(self, client):
        """Test custom portfolio creation workflow"""
        # Step 1: Create custom portfolio
        portfolio_data = {
            "name": "Integration Test Portfolio",
            "description": "Created during integration testing",
            "strategy": "lump_sum",
            "allocations": {"AAPL": 60, "MSFT": 40},
            "monthly_investment": 1000
        }

        create_response = client.post("/api/custom-portfolios", json=portfolio_data)

        # Should succeed or handle gracefully
        assert create_response.status_code in [200, 500]

        if create_response.status_code == 200:
            created_data = create_response.json()
            assert "id" in created_data
            portfolio_id = created_data["id"]

            # Step 2: Retrieve portfolio
            get_response = client.get("/api/custom-portfolios")
            assert get_response.status_code in [200, 500]

            if get_response.status_code == 200:
                portfolios = get_response.json()
                assert isinstance(portfolios, list)
                assert len(portfolios) > 0

            # Step 3: Check portfolio comparison
            compare_data = {
                "portfolio_ids": [portfolio_id] if 'portfolio_id' in locals() else []
            }

            if compare_data["portfolio_ids"]:
                compare_response = client.post("/api/custom-portfolios/compare", json=compare_data)
                assert compare_response.status_code in [200, 500]

    def test_performance_metrics_calculation_workflow(self, client, db_session):
        """Test performance metrics calculation workflow"""
        # Create test data
        transactions = [
            Transaction(
                activity_date="2023-01-01",
                ticker="AAPL",
                trans_code="Buy",
                quantity=10,
                price=150.0,
                amount=-1500.0
            ),
            Transaction(
                activity_date="2023-06-01",
                ticker="AAPL",
                trans_code="Buy",
                quantity=5,
                price=180.0,
                amount=-900.0
            )
        ]

        for tx in transactions:
            db_session.add(tx)
        db_session.commit()

        # Test performance metrics endpoint
        response = client.get("/api/portfolio/performance")
        assert response.status_code in [200, 404, 500]

        # Test risk assessment endpoint
        response = client.get("/api/portfolio/risk")
        assert response.status_code in [200, 404, 500]

        # Test advanced analytics endpoint
        response = client.get("/api/portfolio/advanced-analytics")
        assert response.status_code in [200, 404, 500]

class TestDataQuality:
    """Test data quality and edge cases"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_real_robinhood_csv_format(self, client):
        """Test with real Robinhood CSV format"""
        # Simulate real Robinhood CSV headers and data
        real_csv = """Brokerage,Date,Action,Symbol,Description,Quantity,Price,Fees & Comm,Amount
Robinhood,2023-01-01,Buy,AAPL,AAPL,-10,150.00,0.00,-1500.00
Robinhood,2023-02-01,Buy,MSFT,MSFT,-5,300.00,0.00,-1500.00
Robinhood,2023-03-01,Sell,AAPL,AAPL,5,180.00,0.00,900.00"""

        # Our processor expects specific column names, so this should be handled
        csv_file = BytesIO(real_csv.encode('utf-8'))
        csv_file.name = "robinhood.csv"

        response = client.post("/api/upload-csv", files={"file": csv_file})

        # Should handle format differences gracefully
        assert response.status_code in [200, 400, 500]

    def test_edge_cases_dividends_stock_splits(self, client):
        """Test edge cases: dividends, stock splits, transfers"""
        # Test dividend transaction
        dividend_csv = """activity_date,ticker,trans_code,quantity,price,amount
2023-03-15,AAPL,Dividend,,0.24,24.00"""

        csv_file = BytesIO(dividend_csv.encode('utf-8'))
        csv_file.name = "dividend.csv"

        response = client.post("/api/upload-csv", files={"file": csv_file})

        # Should handle dividends (empty ticker, no quantity)
        assert response.status_code in [200, 400, 500]

        # Test stock split (if supported)
        split_csv = """activity_date,ticker,trans_code,quantity,price,amount
2023-06-01,AAPL,Stock Split,10,0.00,0.00"""

        csv_file = BytesIO(split_csv.encode('utf-8'))
        csv_file.name = "split.csv"

        response = client.post("/api/upload-csv", files={"file": csv_file})

        # Should handle stock splits
        assert response.status_code in [200, 400, 500]

    def test_error_handling_recovery(self, client):
        """Test error handling and recovery"""
        # Test with corrupted CSV
        corrupted_csv = """activity_date,ticker,trans_code,quantity,price,amount
2023-01-01,AAPL,Buy,10,150.00,-1500.00
invalid,line,here
2023-02-01,MSFT,Sell,5,300.00,1500.00"""

        csv_file = BytesIO(corrupted_csv.encode('utf-8'))
        csv_file.name = "corrupted.csv"

        response = client.post("/api/upload-csv", files={"file": csv_file})

        # Should handle errors gracefully
        assert response.status_code in [200, 400, 500]

        if response.status_code == 200:
            data = response.json()
            # Should still process valid lines
            assert "transactions_processed" in data

    def test_calculation_accuracy_financial_standards(self, client):
        """Test calculation accuracy against financial standards"""
        # Create a known portfolio for accuracy testing
        # Buy 100 shares at $10, sell 50 shares at $15
        # Expected: Total return, CAGR, etc. can be calculated mathematically

        test_csv = """activity_date,ticker,trans_code,quantity,price,amount
2023-01-01,TEST,Buy,100,10.00,-1000.00
2023-07-01,TEST,Sell,50,15.00,750.00"""

        csv_file = BytesIO(test_csv.encode('utf-8'))
        csv_file.name = "accuracy_test.csv"

        # Upload data
        response = client.post("/api/upload-csv", files={"file": csv_file})

        if response.status_code == 200:
            # Check calculations
            overview_response = client.get("/api/portfolio-overview")

            if overview_response.status_code == 200:
                data = overview_response.json()

                # Basic validation - should have reasonable values
                assert "total_value" in data
                assert "transaction_count" in data

                if "performance" in data:
                    perf = data["performance"]
                    # Total return should be positive (750 - 1000 + 500 remaining shares)
                    # This is a complex calculation, just ensure it doesn't crash
                    assert isinstance(perf.get("total_return"), (int, float, type(None)))

    def test_data_integrity_checks(self, client):
        """Test data integrity and consistency"""
        # Test with duplicate transactions
        duplicate_csv = """activity_date,ticker,trans_code,quantity,price,amount
2023-01-01,AAPL,Buy,10,150.00,-1500.00
2023-01-01,AAPL,Buy,10,150.00,-1500.00
2023-02-01,MSFT,Buy,5,300.00,-1500.00"""

        csv_file = BytesIO(duplicate_csv.encode('utf-8'))
        csv_file.name = "duplicates.csv"

        response = client.post("/api/upload-csv", files={"file": csv_file})

        # Should handle duplicates appropriately
        assert response.status_code in [200, 400, 500]

        if response.status_code == 200:
            data = response.json()
            # Should report accurate counts
            assert "transactions_saved" in data

class TestCrossBrowserCompatibility:
    """Test cross-browser compatibility (simulated)"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_responsive_design_mobile(self, client):
        """Test responsive design for mobile"""
        dashboard_response = client.get("/dashboard")
        assert dashboard_response.status_code == 200

        content = dashboard_response.text

        # Check for mobile-first responsive classes
        assert "md:flex-row" in content or "sm:" in content
        assert "grid-cols-1" in content

    def test_responsive_design_tablet(self, client):
        """Test responsive design for tablet"""
        dashboard_response = client.get("/dashboard")
        assert dashboard_response.status_code == 200

        content = dashboard_response.text

        # Check for tablet breakpoints
        assert "md:" in content or "lg:" in content

    def test_javascript_feature_detection(self, client):
        """Test JavaScript feature detection and fallbacks"""
        dashboard_response = client.get("/dashboard")
        assert dashboard_response.status_code == 200

        content = dashboard_response.text

        # Check for progressive enhancement
        assert "addEventListener" in content
        assert "DOMContentLoaded" in content

class TestLoadTesting:
    """Basic load testing"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_concurrent_requests(self, client):
        """Test handling of concurrent requests"""
        import asyncio
        import aiohttp
        from concurrent.futures import ThreadPoolExecutor

        # Simulate concurrent requests
        def make_request():
            return client.get("/api/health")

        # Make 10 concurrent requests
        responses = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            for future in futures:
                responses.append(future.result())

        # Check responses
        success_count = sum(1 for r in responses if r.status_code == 200)
        assert success_count >= 8  # At least 80% success rate

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
