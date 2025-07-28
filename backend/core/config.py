from pydantic_settings import BaseSettings
from typing import Optional, List
import os


class Settings(BaseSettings):
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Schema Diff Pro"
    VERSION: str = "1.0.0"
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # Database
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 3600
    
    
    # WebSocket
    WS_MESSAGE_QUEUE_SIZE: int = 100
    WS_HEARTBEAT_INTERVAL: int = 30
    
    # Comparison Engine
    MAX_PARALLEL_COMPARISONS: int = 5
    COMPARISON_TIMEOUT: int = 300  # 5 minutes
    BATCH_SIZE: int = 1000  # For large result sets
    
    # System databases to exclude
    SYSTEM_DATABASES: List[str] = [
        "information_schema",
        "performance_schema",
        "mysql",
        "sys",
        "percona_schema"
    ]
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
    ]
    
    @property
    def cors_origins(self) -> List[str]:
        """Get CORS origins from environment or use defaults"""
        origins = os.getenv("BACKEND_CORS_ORIGINS", "")
        if origins:
            return [origin.strip() for origin in origins.split(",")]
        return self.BACKEND_CORS_ORIGINS
    
    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings()