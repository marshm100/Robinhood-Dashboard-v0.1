"""
Application configuration settings

This module provides configuration for Docker/Railway deployment with persistent
volume storage. Database and uploads are stored in ./data directory which is
mounted as a Docker volume for persistence.
"""

import os
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator


# Project root directory (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent


def _get_absolute_db_url() -> str:
    """
    Get database URL with absolute path.
    
    This ensures the database file is always in the same location
    regardless of the current working directory when the app starts.
    
    Default path: ./data/portfolio.db (persisted via Docker volume)
    
    If DATABASE_URL env var is set:
      - PostgreSQL URLs are used as-is
      - SQLite relative paths are converted to absolute paths
    If not set:
      - Uses absolute path to ./data/portfolio.db
    """
    env_url = os.getenv('DATABASE_URL')
    project_root = Path(__file__).parent.parent
    
    if env_url:
        # If it's not SQLite, return as-is (e.g., PostgreSQL)
        if not env_url.startswith("sqlite:///"):
            return env_url
        
        # Extract the path from SQLite URL
        db_path_str = env_url.replace("sqlite:///", "")
        db_path = Path(db_path_str)
        
        # If already absolute, return as-is
        if db_path.is_absolute():
            return env_url
        
        # Convert relative path to absolute (relative to project root)
        absolute_path = (project_root / db_path).resolve()
        return f"sqlite:///{absolute_path}"
    
    # Default: Use ./data/portfolio.db for Docker volume persistence
    db_file = project_root / "data" / "portfolio.db"
    return f"sqlite:///{db_file.resolve()}"


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Environment
    environment: str = "development"

    # Database - use absolute path for consistent persistence
    database_url: str = _get_absolute_db_url()

    # API Keys
    alpha_vantage_key: Optional[str] = None
    finnhub_key: Optional[str] = None

    # Stockr Database (persisted via Docker volume in ./data)
    stockr_db_path: str = "./data/stockr_backbone/stockr.db"

    # Application
    debug: bool = True
    secret_key: str = "your-secret-key-change-in-production"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # File Upload (persisted via Docker volume in ./data/uploads)
    upload_dir: str = "data/uploads"
    max_upload_size: int = 10 * 1024 * 1024  # 10MB

    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000"]

    # Security
    force_https: bool = False
    forward_allow_ips: str = "*"

    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = None

    # Monitoring
    enable_metrics: bool = False
    metrics_token: Optional[str] = None

    # Backup
    enable_backups: bool = False
    backup_interval: int = 24  # hours
    backup_retention_days: int = 30

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from environment

    @field_validator('database_url', mode='after')
    @classmethod
    def ensure_absolute_db_path(cls, v: str) -> str:
        """
        Ensure database URL uses absolute path for SQLite databases.
        
        This validator runs AFTER Pydantic loads the value from env vars or .env,
        converting any relative SQLite paths to absolute paths based on project root.
        """
        if not v.startswith("sqlite:///"):
            # Not SQLite (e.g., PostgreSQL), return as-is
            return v
        
        # Extract path from SQLite URL
        db_path_str = v.replace("sqlite:///", "")
        db_path = Path(db_path_str)
        
        # If already absolute, return as-is
        if db_path.is_absolute():
            return v
        
        # Convert relative path to absolute (relative to project root)
        absolute_path = (PROJECT_ROOT / db_path).resolve()
        return f"sqlite:///{absolute_path}"

    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.environment.lower() == "development"

    @property
    def cors_origins_list(self) -> List[str]:
        """Get CORS origins as a list"""
        if isinstance(self.cors_origins, str):
            return [origin.strip() for origin in self.cors_origins.split(",")]
        return self.cors_origins


# Global settings instance
settings = Settings()


def get_upload_path() -> Path:
    """
    Get the upload directory path.
    
    Default: ./data/uploads (persisted via Docker volume)
    
    Returns:
        Path: Absolute path to the upload directory.
    """
    upload_path = PROJECT_ROOT / settings.upload_dir
    return upload_path


def get_temp_file_path(filename: str) -> Path:
    """
    Get a path for a temporary file.
    
    Temp files are stored in ./data/temp for Docker volume persistence.
    
    Args:
        filename: The name of the temporary file.
        
    Returns:
        Path: Absolute path to the temporary file location.
    """
    temp_dir = PROJECT_ROOT / "data" / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir / filename


# Create upload directory (Docker volume mounted at ./data)
upload_path = get_upload_path()
upload_path.mkdir(parents=True, exist_ok=True)
