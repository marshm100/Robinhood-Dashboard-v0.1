"""
Application configuration settings
"""

import os
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Environment
    environment: str = "development"

    # Database
    database_url: str = "sqlite:///./portfolio.db"

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

# Create upload directory
upload_path = Path(settings.upload_dir)
upload_path.mkdir(exist_ok=True)
