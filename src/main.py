"""
Robinhood Portfolio Analysis Web Application
Main FastAPI application entry point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
from pathlib import Path
from typing import Optional

from .config import settings
from .database import init_db_sync, get_db_sync
from .routes import api_router, web_router

# Initialize FastAPI app
app = FastAPI(
    title="Robinhood Portfolio Analysis",
    description="Comprehensive portfolio analysis tool with cyberpunk aesthetics",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Configure CORS with security
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=86400,  # Cache preflight for 24 hours
)

# Security middleware for additional headers
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    
    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    
    # API versioning header
    if request.url.path.startswith("/api/"):
        response.headers["API-Version"] = "1.0.0"
    
    return response

# Mount static files
static_path = Path(__file__).parent / "static"
static_path.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Mount templates
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# Include routers
app.include_router(api_router, prefix="/api", tags=["API"])
app.include_router(web_router, tags=["Web"])

@app.on_event("startup")
def startup_event():
    """
    Initialize application on startup.
    
    This includes:
    1. Database initialization
    2. Starting the stockr_backbone maintenance service (CORE ARCHITECTURE)
    """
    # Initialize main application database
    init_db_sync()
    
    # Start stockr_backbone maintenance service
    # This is a CORE ARCHITECTURAL COMPONENT that maintains the stock database
    # It runs continuously in the background to keep stock data up-to-date
    try:
        import sys
        from pathlib import Path
        
        # Add stockr_backbone to Python path
        project_root = Path(__file__).parent.parent
        stockr_path = project_root / "stockr_backbone"
        if str(stockr_path) not in sys.path:
            sys.path.insert(0, str(stockr_path))
        
        from src.background_maintenance import start_maintenance_service
        
        # Start the maintenance service (refreshes every 60 minutes by default)
        # This ensures all tracked stocks are kept up-to-date automatically
        start_maintenance_service(refresh_interval_minutes=60)
        print("✓ Stockr_backbone maintenance service started (CORE ARCHITECTURE)")
        
    except Exception as e:
        # Log error but don't fail startup - app can still work without it
        print(f"Warning: Failed to start stockr_backbone maintenance service: {e}")
        import traceback
        traceback.print_exc()


@app.on_event("shutdown")
def shutdown_event():
    """Cleanup on application shutdown"""
    try:
        import sys
        from pathlib import Path
        
        project_root = Path(__file__).parent.parent
        stockr_path = project_root / "stockr_backbone"
        if str(stockr_path) not in sys.path:
            sys.path.insert(0, str(stockr_path))
        
        from src.background_maintenance import stop_maintenance_service
        stop_maintenance_service()
        print("✓ Stockr_backbone maintenance service stopped")
    except Exception as e:
        print(f"Warning: Error stopping maintenance service: {e}")

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Robinhood Portfolio Analysis API", "status": "running"}

@app.get("/health")
async def health_check():
    """
    Comprehensive health check endpoint.
    
    Checks:
    1. Main application database connectivity
    2. stockr_backbone maintenance service status (CORE ARCHITECTURE)
    """
    from .database import get_db_sync
    import time
    
    health_status = {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "1.0.0",
        "environment": settings.environment,
        "checks": {}
    }
    
    # Check main application database
    try:
        db = next(get_db_sync())
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        health_status["checks"]["database"] = {"status": "ok", "message": "Database connection successful"}
        db.close()
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["checks"]["database"] = {"status": "error", "message": f"Database connection failed: {str(e)}"}
    
    # Check stockr_backbone maintenance service (CORE ARCHITECTURAL COMPONENT)
    try:
        import sys
        from pathlib import Path
        
        project_root = Path(__file__).parent.parent
        stockr_path = project_root / "stockr_backbone"
        if str(stockr_path) not in sys.path:
            sys.path.insert(0, str(stockr_path))
        
        from src.background_maintenance import get_maintenance_service
        
        service = get_maintenance_service()
        stockr_status = service.get_status()
        
        if stockr_status.get("running", False):
            health_status["checks"]["stockr_backbone"] = {
                "status": "ok",
                "message": "Maintenance service running",
                "details": {
                    "running": True,
                    "refresh_count": stockr_status.get("refresh_count", 0),
                    "last_refresh": stockr_status.get("last_refresh"),
                    "tracked_stocks": stockr_status.get("tracked_stocks_count", 0),
                    "refresh_interval_minutes": stockr_status.get("refresh_interval_minutes", 60)
                },
                "importance": "CRITICAL - Core architectural component"
            }
        else:
            health_status["status"] = "degraded"
            health_status["checks"]["stockr_backbone"] = {
                "status": "warning",
                "message": "Maintenance service not running",
                "details": stockr_status,
                "importance": "CRITICAL - Core architectural component"
            }
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["checks"]["stockr_backbone"] = {
            "status": "error",
            "message": f"Failed to check maintenance service: {str(e)}",
            "importance": "CRITICAL - Core architectural component"
        }
    
    return health_status

@app.get("/metrics")
async def metrics():
    """Basic application metrics endpoint"""
    if not settings.enable_metrics:
        return {"error": "Metrics endpoint disabled"}
    
    import time
    
    return {
        "timestamp": time.time(),
        "environment": settings.environment,
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/api/stockr-status")
async def get_stockr_status():
    """
    Get status of stockr_backbone maintenance service.
    
    This endpoint provides visibility into the core architectural component
    that maintains the stock database.
    """
    try:
        import sys
        from pathlib import Path
        
        project_root = Path(__file__).parent.parent
        stockr_path = project_root / "stockr_backbone"
        if str(stockr_path) not in sys.path:
            sys.path.insert(0, str(stockr_path))
        
        from src.background_maintenance import get_maintenance_service
        
        service = get_maintenance_service()
        status = service.get_status()
        
        return {
            "status": "ok",
            "stockr_backbone": {
                "maintenance_service": status,
                "description": "Core architectural component for maintaining stock database",
                "importance": "CRITICAL - This service maintains the internal stock database"
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "stockr_backbone": {
                "maintenance_service": {"running": False},
                "error": "Failed to get status"
            }
        }

if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )
