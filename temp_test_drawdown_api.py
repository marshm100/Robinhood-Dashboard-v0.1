"""
Temporary test script to exercise /api/drawdown-analysis without hitting the real DB.
It patches PortfolioCalculator to return synthetic data, then calls the FastAPI endpoint
via TestClient.
"""

import json

from fastapi.testclient import TestClient

import src.services as services
from src.main import app


class DummyPortfolioCalculator:
    def __init__(self, db=None):
        pass

    def get_drawdown_analysis(self):
        return {
            "drawdown_series": [
                {"date": "2024-01-01", "drawdown": 0.0},
                {"date": "2024-01-02", "drawdown": -1.2},
            ],
            "max_drawdown": -1.2,
            "max_drawdown_date": "2024-01-02",
            "recovery_time_days": 3,
            "drawdown_periods": [
                {
                    "start": "2024-01-02",
                    "bottom": "2024-01-02",
                    "end": "2024-01-05",
                    "depth": -1.2,
                }
            ],
        }


# Patch to avoid DB dependency for this endpoint test
services.PortfolioCalculator = DummyPortfolioCalculator

# Disable startup event (db init / maintenance) for this test client
app.router.on_startup.clear()

client = TestClient(app)
response = client.get("/api/drawdown-analysis")
print("status", response.status_code)
print(json.dumps(response.json(), indent=2))
