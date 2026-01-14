#!/usr/bin/env python3
"""
Run script for Robinhood Portfolio Analysis
"""

import uvicorn
from src.main import app

if __name__ == "__main__":
    print("Starting Robinhood Portfolio Analysis...")
    print("Access the dashboard at: http://localhost:8000/dashboard")
    print("Upload CSV at: http://localhost:8000/upload")
    print("API docs at: http://localhost:8000/api/docs")

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["src", "templates", "static"],
        log_level="info"
    )
