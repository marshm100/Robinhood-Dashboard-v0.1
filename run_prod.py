#!/usr/bin/env python3
"""
Production run script for Robinhood Portfolio Analysis
Uses Gunicorn with Uvicorn workers for production, Uvicorn for development
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config import settings

def main():
    """Main entry point"""
    print("🚀 Starting Robinhood Portfolio Analysis...")

    if settings.is_production:
        print("🏭 Running in PRODUCTION mode with Gunicorn")
        print(f"📊 Workers: {os.cpu_count() * 2 + 1}")
        print("📊 Access the dashboard at: http://localhost:8000/dashboard"
        print("📤 Upload CSV at: http://localhost:8000/upload"
        print("🛠️  API docs at: http://localhost:8000/api/docs"

        # Use gunicorn for production
        os.system("gunicorn -c gunicorn.conf.py src.main:app")
    else:
        print("🛠️  Running in DEVELOPMENT mode with Uvicorn")
        print("📊 Access the dashboard at: http://localhost:8000/dashboard"
        print("📤 Upload CSV at: http://localhost:8000/upload"
        print("🛠️  API docs at: http://localhost:8000/api/docs"

        # Use uvicorn for development
        import uvicorn
        uvicorn.run(
            "src.main:app",
            host=settings.host,
            port=settings.port,
            reload=settings.debug,
            log_level=settings.log_level.lower()
        )

if __name__ == "__main__":
    main()
