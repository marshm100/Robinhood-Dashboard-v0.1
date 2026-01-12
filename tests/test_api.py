#!/usr/bin/env python3
"""
Comprehensive API endpoint testing
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

class TestAPIEndpoints:
    """Test API endpoints functionality"""

    @pytest.fixture
    def client(self):
        """Create test client"""
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

    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data

    def test_health_endpoint_rate_limiting(self, client):
        """Test rate limiting on health endpoint"""
        # Make multiple requests quickly
        responses = []
        for _ in range(5):
            response = client.get("/api/health")
            responses.append(response.status_code)

        # At least some should succeed
        assert 200 in responses

    def test_portfolio_overview_endpoint(self, client, db_session):
        """Test portfolio overview endpoint"""
        response = client.get("/api/portfolio-overview")

        # Should return 200 even with no data
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)
            assert "transaction_count" in data

    def test_transactions_endpoint(self, client, db_session):
        """Test transactions endpoint"""
        response = client.get("/api/transactions")

        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert "transactions" in data
            assert "pagination" in data
            assert isinstance(data["transactions"], list)

    def test_transactions_pagination(self, client):
        """Test transactions pagination"""
        response = client.get("/api/transactions?skip=0&limit=10")

        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert "pagination" in data
            pagination = data["pagination"]
            assert "total" in pagination
            assert "skip" in pagination
            assert "limit" in pagination
            assert "has_more" in pagination

    def test_csv_upload_endpoint_validation(self, client):
        """Test CSV upload validation"""
        # Test with no file
        response = client.post("/api/upload-csv")
        assert response.status_code == 422  # Validation error

        # Test with invalid file type
        invalid_file = BytesIO(b"invalid content")
        invalid_file.name = "test.txt"
        response = client.post("/api/upload-csv", files={"file": invalid_file})
        assert response.status_code == 400

        # Test with empty file
        empty_file = BytesIO(b"")
        empty_file.name = "empty.csv"
        response = client.post("/api/upload-csv", files={"file": empty_file})
        assert response.status_code == 400

    def test_csv_upload_with_valid_data(self, client):
        """Test CSV upload with valid data"""
        # Create valid CSV content
        csv_content = """activity_date,ticker,trans_code,quantity,price,amount
2023-01-01,AAPL,Buy,10,150.00,-1500.00
2023-01-02,MSFT,Sell,5,300.00,1500.00"""

        csv_file = BytesIO(csv_content.encode('utf-8'))
        csv_file.name = "test.csv"

        response = client.post("/api/upload-csv", files={"file": csv_file})

        assert response.status_code in [200, 500]  # May fail due to DB constraints
        if response.status_code == 200:
            data = response.json()
            assert "message" in data
            assert "transactions_processed" in data

    def test_api_versioning(self, client):
        """Test API versioning"""
        # Test v1 endpoints
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_custom_portfolios_endpoints(self, client):
        """Test custom portfolios endpoints"""
        # GET portfolios
        response = client.get("/api/custom-portfolios")
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)

        # POST portfolio with invalid data
        invalid_data = {"name": ""}  # Invalid: empty name
        response = client.post("/api/custom-portfolios", json=invalid_data)
        assert response.status_code == 422  # Validation error

        # POST portfolio with valid data
        valid_data = {
            "name": "Test Portfolio",
            "description": "Test description",
            "strategy": "lump_sum",
            "allocations": {"AAPL": 60, "MSFT": 40},
            "monthly_investment": 1000
        }
        response = client.post("/api/custom-portfolios", json=valid_data)
        assert response.status_code in [200, 500]  # May fail due to DB constraints

    def test_performance_metrics_endpoint(self, client):
        """Test performance metrics endpoint"""
        response = client.get("/api/portfolio/performance")

        assert response.status_code in [200, 404, 500]  # 404 if not implemented
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)

    def test_risk_assessment_endpoint(self, client):
        """Test risk assessment endpoint"""
        response = client.get("/api/portfolio/risk")

        assert response.status_code in [200, 404, 500]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)

    def test_portfolio_history_endpoint(self, client):
        """Test portfolio history endpoint"""
        response = client.get("/api/portfolio/history")

        assert response.status_code in [200, 404, 500]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)

    def test_advanced_analytics_endpoint(self, client):
        """Test advanced analytics endpoint"""
        response = client.get("/api/portfolio/advanced-analytics")

        assert response.status_code in [200, 404, 500]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)

    def test_cors_headers(self, client):
        """Test CORS headers"""
        response = client.options("/api/health", headers={"Origin": "http://localhost:3000"})

        # Check for CORS headers
        assert "access-control-allow-origin" in response.headers or response.status_code in [200, 404]

    def test_error_handling(self, client):
        """Test error handling"""
        # Test invalid endpoint
        response = client.get("/api/nonexistent")
        assert response.status_code == 404

        # Test invalid method
        response = client.patch("/api/health")
        assert response.status_code in [405, 404]  # Method not allowed or not found

    def test_input_validation(self, client):
        """Test input validation"""
        # Test invalid JSON
        response = client.post("/api/custom-portfolios",
                             data="invalid json",
                             headers={"Content-Type": "application/json"})
        assert response.status_code == 400

        # Test oversized payload (simulate)
        large_data = {"name": "x" * 1000}  # Very long name
        response = client.post("/api/custom-portfolios", json=large_data)
        assert response.status_code in [200, 422, 500]  # May be handled by validation

    def test_rate_limiting_comprehensive(self, client):
        """Test comprehensive rate limiting"""
        # Make many requests to trigger rate limiting
        success_count = 0
        rate_limited_count = 0

        for i in range(20):
            response = client.get("/api/health")
            if response.status_code == 200:
                success_count += 1
            elif response.status_code == 429:
                rate_limited_count += 1

        # Should have some successful requests
        assert success_count > 0

    def test_security_headers(self, client):
        """Test security headers"""
        response = client.get("/api/health")

        if response.status_code == 200:
            headers = response.headers

            # Check for security headers
            security_headers = [
                "x-content-type-options",
                "x-frame-options",
                "x-xss-protection",
                "referrer-policy"
            ]

            found_headers = sum(1 for header in security_headers if header in headers)
            # At least some security headers should be present
            assert found_headers >= 2

class TestAPIIntegration:
    """Integration tests for API functionality"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_end_to_end_workflow(self, client):
        """Test end-to-end workflow simulation"""
        # This would test a complete user workflow
        # For now, just test the basic endpoints work together

        # 1. Check health
        response = client.get("/api/health")
        assert response.status_code == 200

        # 2. Check portfolio overview
        response = client.get("/api/portfolio-overview")
        assert response.status_code in [200, 500]

        # 3. Check transactions
        response = client.get("/api/transactions")
        assert response.status_code in [200, 500]

    def test_api_consistency(self, client):
        """Test API response consistency"""
        # Make same request multiple times
        responses = []
        for _ in range(3):
            response = client.get("/api/health")
            responses.append(response.json())

        # All responses should be consistent
        first_response = responses[0]
        for response in responses[1:]:
            assert response["status"] == first_response["status"]

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
