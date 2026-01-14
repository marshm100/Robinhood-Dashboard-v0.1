"""
Application configuration settings
"""

import os
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator


# Project root directory (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent


def _is_serverless_environment() -> bool:
    """
    Detect if running in a serverless environment (Vercel, AWS Lambda, etc.).
    
    In serverless environments, the filesystem is read-only except for /tmp.
    This function checks for common environment variables that indicate
    a serverless deployment.
    """
    serverless_indicators = [
        'VERCEL',           # Vercel deployment
        'AWS_LAMBDA_FUNCTION_NAME',  # AWS Lambda
        'LAMBDA_TASK_ROOT',  # AWS Lambda
        'GOOGLE_CLOUD_PROJECT',  # Google Cloud Functions
        'FUNCTIONS_WORKER_RUNTIME',  # Azure Functions
    ]
    return any(os.getenv(var) for var in serverless_indicators)


def _get_writable_temp_dir() -> Path:
    """
    Get a writable temporary directory path.
    
    NOTE: In Vercel/Lambda serverless environments, the filesystem is read-only
    except for /tmp. This function returns /tmp for serverless environments
    and the project root for local development.
    
    Returns:
        Path: A writable directory path appropriate for the environment.
    """
    if _is_serverless_environment():
        # Serverless environments (Vercel, Lambda) only allow writing to /tmp
        return Path("/tmp")
    else:
        # Local development - use project root
        return PROJECT_ROOT


def _get_absolute_db_url() -> str:
    """
    Get database URL with absolute path.
    
    This ensures the database file is always in the same location
    regardless of the current working directory when the app starts.
    
    If DATABASE_URL env var is set:
      - PostgreSQL URLs are used as-is
      - SQLite relative paths are converted to absolute paths
    If not set:
      - Uses absolute path to portfolio.db in project root
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
    
    # Default: Use absolute path to portfolio.db in project root
    db_file = project_root / "portfolio.db"
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

    # Stockr Database
    stockr_db_path: str = "./stockr_backbone/stockr.db"

    # Application
    debug: bool = True
    secret_key: str = "your-secret-key-change-in-production"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # File Upload
    # NOTE: upload_dir is relative - actual path is computed via get_upload_path()
    # In serverless environments (Vercel/Lambda), files are written to /tmp
    upload_dir: str = "uploads"
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
    Get the upload directory path appropriate for the current environment.
    
    IMPORTANT: In Vercel/Lambda serverless environments, the filesystem is 
    read-only except for /tmp. This function ensures uploads go to a writable
    location regardless of deployment environment.
    
    Returns:
        Path: Absolute path to the upload directory.
    """
    base_dir = _get_writable_temp_dir()
    upload_dir = base_dir / settings.upload_dir
    return upload_dir


def get_temp_file_path(filename: str) -> Path:
    """
    Get a path for a temporary file in a writable location.
    
    Use this for any temporary files that need to be written during request
    processing (debug logs, temp uploads, etc.).
    
    Args:
        filename: The name of the temporary file.
        
    Returns:
        Path: Absolute path to the temporary file location.
    """
    base_dir = _get_writable_temp_dir()
    return base_dir / filename


# Create upload directory
# NOTE: In serverless environments (Vercel, AWS Lambda), only /tmp is writable.
# This path will be /tmp/uploads in those environments, or ./uploads locally.
upload_path = get_upload_path()
try:
    upload_path.mkdir(parents=True, exist_ok=True)
except OSError as e:
    # If directory creation fails (e.g., read-only filesystem), log warning
    # but don't crash - the path will be created on first write if possible
    import logging
    logging.warning(f"Could not create upload directory {upload_path}: {e}")
