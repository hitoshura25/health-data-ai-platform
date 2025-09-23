"""
Configuration management for Health Data AI Platform.
"""

from pydantic import BaseSettings, validator
from typing import Optional, List
import os
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Environment
    environment: str = "development"
    debug: bool = False

    # Database
    database_url: str = "postgresql://health_user:health_password@localhost:5432/health_platform"

    # Message Queue
    rabbitmq_url: str = "amqp://health_user:health_password@localhost:5672/health_data"

    # Object Storage (MinIO/S3)
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "admin"
    minio_secret_key: str = "password123"
    minio_bucket: str = "health-data"
    minio_secure: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379"

    # MLflow
    mlflow_tracking_uri: str = "http://localhost:5000"

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 1

    # Security
    secret_key: str = "development-secret-key-change-in-production"
    jwt_secret: str = "development-jwt-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24

    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8080"]

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 60

    # File Upload
    max_file_size_mb: int = 100
    allowed_file_types: List[str] = [".avro"]

    # Processing
    processing_timeout_seconds: int = 300
    max_retry_attempts: int = 3

    # Health Checks
    health_check_interval_seconds: int = 30

    # Monitoring
    metrics_enabled: bool = True
    metrics_port: int = 9090

    @validator("environment")
    def validate_environment(cls, v):
        """Validate environment value."""
        valid_environments = ["development", "staging", "production"]
        if v not in valid_environments:
            raise ValueError(f"Environment must be one of: {valid_environments}")
        return v

    @validator("database_url")
    def validate_database_url(cls, v):
        """Validate database URL format."""
        if not v.startswith(("postgresql://", "postgres://")):
            raise ValueError("Database URL must be a PostgreSQL connection string")
        return v

    @validator("rabbitmq_url")
    def validate_rabbitmq_url(cls, v):
        """Validate RabbitMQ URL format."""
        if not v.startswith("amqp://"):
            raise ValueError("RabbitMQ URL must be an AMQP connection string")
        return v

    @validator("redis_url")
    def validate_redis_url(cls, v):
        """Validate Redis URL format."""
        if not v.startswith("redis://"):
            raise ValueError("Redis URL must be a Redis connection string")
        return v

    @validator("log_level")
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()

    @validator("log_format")
    def validate_log_format(cls, v):
        """Validate log format."""
        valid_formats = ["json", "console"]
        if v not in valid_formats:
            raise ValueError(f"Log format must be one of: {valid_formats}")
        return v

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"

    def get_database_config(self) -> dict:
        """Get database configuration."""
        return {
            "url": self.database_url,
            "echo": self.debug and not self.is_production(),
            "pool_pre_ping": True,
            "pool_recycle": 3600,
        }

    def get_minio_config(self) -> dict:
        """Get MinIO configuration."""
        return {
            "endpoint": self.minio_endpoint,
            "access_key": self.minio_access_key,
            "secret_key": self.minio_secret_key,
            "secure": self.minio_secure,
            "bucket": self.minio_bucket,
        }

    def get_cors_config(self) -> dict:
        """Get CORS configuration."""
        return {
            "allow_origins": self.cors_origins,
            "allow_credentials": True,
            "allow_methods": ["*"],
            "allow_headers": ["*"],
        }

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


class ServiceSettings(Settings):
    """Extended settings for specific services."""

    service_name: str = "unknown"

    # Service-specific overrides can be added here
    def __init__(self, service_name: str, **kwargs):
        super().__init__(service_name=service_name, **kwargs)


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()


@lru_cache()
def get_service_settings(service_name: str) -> ServiceSettings:
    """Get cached service-specific settings."""
    return ServiceSettings(service_name=service_name)


def get_env_var(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get environment variable with optional default."""
    return os.getenv(key, default)


def is_testing() -> bool:
    """Check if running in test environment."""
    return get_env_var("TESTING", "false").lower() == "true"


def get_connection_string_for_service(service: str) -> str:
    """Get appropriate connection string for a service."""
    settings = get_settings()

    connection_map = {
        "database": settings.database_url,
        "rabbitmq": settings.rabbitmq_url,
        "redis": settings.redis_url,
        "mlflow": settings.mlflow_tracking_uri,
    }

    return connection_map.get(service, "")


# Environment-specific configurations
DEVELOPMENT_CONFIG = {
    "debug": True,
    "log_level": "DEBUG",
    "log_format": "console",
    "api_workers": 1,
}

STAGING_CONFIG = {
    "debug": False,
    "log_level": "INFO",
    "log_format": "json",
    "api_workers": 2,
}

PRODUCTION_CONFIG = {
    "debug": False,
    "log_level": "WARNING",
    "log_format": "json",
    "api_workers": 4,
    "cors_origins": [],  # Should be explicitly set in production
}