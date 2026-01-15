"""
Temporary test to verify /api/portfolio-overview includes sector_allocation data.
Patches PortfolioCalculator to avoid DB dependency and returns synthetic data.
"""

import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

import src.services as services
from src.main import app
from src.database import get_db_sync


class DummyDB:
    """Minimal dummy DB/session object."""

    def __getattr__(self, item):
        raise AttributeError(item)


class DummyPortfolioCalculator:
    def __init__(self, db=None):
        pass

    def get_portfolio_summary(self):
        return {
            "has_data": True,
            "transaction_count": 3,
            "unique_tickers": 3,
            "current_holdings_count": 3,
            "holdings": {"AAPL": 10, "MSFT": 5, "XLF": 2},
            "performance": {
                "total_return": 12.3,
                "total_value": 12345.67,
                "start_value": 10000,
                "start_date": "2024-01-01",
                "end_date": "2024-06-30",
            },
        }

    def calculate_performance_metrics(self):
        return {"sharpe_ratio": 1.2}

    def get_risk_assessment(self):
        return {"volatility": 15.0}

    def get_advanced_analytics(self):
        return {"position_weights": {"AAPL": 50, "MSFT": 30, "XLF": 20}}

    def get_sector_allocation(self):
        return {
            "sector_allocation": {"Technology": 80, "Financials": 20},
            "sector_count": 2,
            "largest_sector": ("Technology", 80),
        }


# Patch PortfolioCalculator
services.PortfolioCalculator = DummyPortfolioCalculator

# Disable startup events (DB init/maintenance)
app.router.on_startup.clear()

# Override DB dependency to avoid real DB hits
app.dependency_overrides[get_db_sync] = lambda: DummyDB()

client = TestClient(app)
response = client.get("/api/portfolio-overview")

print("status", response.status_code)
print(json.dumps(response.json(), indent=2))
