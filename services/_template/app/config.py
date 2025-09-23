"""
Service Configuration Template

This module provides configuration management for your service.
It extends the shared configuration with service-specific settings.
"""

from typing import Optional, List
from pydantic import Field, validator
from shared.common.config import BaseSettings


class Settings(BaseSettings):
    """Service-specific configuration settings."""

    # Service identification
    service_name: str = "your-service-name"
    service_version: str = "0.1.0"

    # Server configuration (for web services)
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")

    # Database configuration (if your service uses a database)
    database_url: Optional[str] = Field(default=None, env="DATABASE_URL")
    database_pool_size: int = Field(default=5, env="DATABASE_POOL_SIZE")

    # Message queue configuration (if your service uses messaging)
    rabbitmq_url: Optional[str] = Field(default=None, env="RABBITMQ_URL")
    queue_name: str = Field(default="your_service_queue", env="QUEUE_NAME")

    # Redis configuration (if your service uses caching)
    redis_url: Optional[str] = Field(default=None, env="REDIS_URL")
    cache_ttl: int = Field(default=3600, env="CACHE_TTL")  # 1 hour

    # Object storage configuration (if your service uses storage)
    minio_endpoint: Optional[str] = Field(default=None, env="MINIO_ENDPOINT")
    minio_access_key: Optional[str] = Field(default=None, env="MINIO_ACCESS_KEY")
    minio_secret_key: Optional[str] = Field(default=None, env="MINIO_SECRET_KEY")
    storage_bucket: str = Field(default="your-service-data", env="STORAGE_BUCKET")

    # Authentication (if your service requires auth)
    secret_key: Optional[str] = Field(default=None, env="SECRET_KEY")
    jwt_secret: Optional[str] = Field(default=None, env="JWT_SECRET")
    jwt_expires_hours: int = Field(default=24, env="JWT_EXPIRES_HOURS")

    # External APIs (if your service calls external services)
    external_api_url: Optional[str] = Field(default=None, env="EXTERNAL_API_URL")
    external_api_key: Optional[str] = Field(default=None, env="EXTERNAL_API_KEY")
    external_api_timeout: int = Field(default=30, env="EXTERNAL_API_TIMEOUT")

    # ML specific configuration (for ML services)
    model_path: Optional[str] = Field(default=None, env="MODEL_PATH")
    model_version: Optional[str] = Field(default="latest", env="MODEL_VERSION")
    mlflow_tracking_uri: Optional[str] = Field(default=None, env="MLFLOW_TRACKING_URI")
    inference_batch_size: int = Field(default=32, env="INFERENCE_BATCH_SIZE")

    # Processing configuration
    max_workers: int = Field(default=4, env="MAX_WORKERS")
    request_timeout: int = Field(default=300, env="REQUEST_TIMEOUT")  # 5 minutes
    max_retries: int = Field(default=3, env="MAX_RETRIES")

    # Health check configuration
    health_check_interval: int = Field(default=30, env="HEALTH_CHECK_INTERVAL")
    health_check_timeout: int = Field(default=10, env="HEALTH_CHECK_TIMEOUT")

    # CORS settings (for web services)
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        env="CORS_ORIGINS"
    )

    # Rate limiting (for API services)
    rate_limit_requests: int = Field(default=100, env="RATE_LIMIT_REQUESTS")
    rate_limit_window: int = Field(default=60, env="RATE_LIMIT_WINDOW")  # seconds

    @validator('cors_origins', pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',')]
        return v

    @validator('secret_key')
    def validate_secret_key(cls, v, values):
        """Validate secret key in production."""
        environment = values.get('environment')
        if environment == 'production' and (not v or v == 'development-secret-key-change-in-production'):
            raise ValueError('Secret key must be set in production')
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def get_database_settings(self) -> dict:
        """Get database connection settings."""
        if not self.database_url:
            return {}

        return {
            "url": self.database_url,
            "pool_size": self.database_pool_size,
            "echo": self.environment == "development",
        }

    def get_cors_settings(self) -> dict:
        """Get CORS middleware settings."""
        return {
            "allow_origins": self.cors_origins,
            "allow_credentials": True,
            "allow_methods": ["*"],
            "allow_headers": ["*"],
        }

    def get_rate_limit_settings(self) -> dict:
        """Get rate limiting settings."""
        return {
            "requests": self.rate_limit_requests,
            "window": self.rate_limit_window,
        }


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get the global settings instance."""
    return settings