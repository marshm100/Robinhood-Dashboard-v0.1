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

def ensure_directories():
    """Ensure required directories exist before starting"""
    dirs = [
        Path("data"),
        Path("data/uploads"),
        Path("data/stockr_backbone"),
        Path("data/temp"),
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        print(f"✓ Directory ensured: {d}")

def main():
    """Main entry point"""
    print("🚀 Starting Robinhood Portfolio Analysis...")
    
    # Ensure directories exist
    ensure_directories()
    
    # Import settings after ensuring directories
    from src.config import settings

    port = int(os.getenv("PORT", settings.port))
    
    if settings.is_production:
        print("🏭 Running in PRODUCTION mode with Gunicorn")
        print(f"📊 Port: {port}")
        print(f"📊 Workers: {min(os.cpu_count() * 2 + 1, 4)}")
        
        # Use exec to replace the process with gunicorn
        # This ensures proper signal handling in containers
        os.execvp("gunicorn", [
            "gunicorn",
            "-c", "gunicorn.conf.py",
            "src.main:app"
        ])
    else:
        print("🛠️  Running in DEVELOPMENT mode with Uvicorn")
        print(f"📊 Access the dashboard at: http://localhost:{port}/dashboard")
        print(f"📤 Upload CSV at: http://localhost:{port}/upload")
        print(f"🛠️  API docs at: http://localhost:{port}/api/docs")

        # Use uvicorn for development
        import uvicorn
        uvicorn.run(
            "src.main:app",
            host=settings.host,
            port=port,
            reload=settings.debug,
            log_level=settings.log_level.lower()
        )

if __name__ == "__main__":
    main()
