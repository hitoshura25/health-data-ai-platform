"""
Configuration settings for ETL Narrative Engine using Pydantic.

All settings can be configured via environment variables with ETL_ prefix.
"""

from enum import Enum

from pydantic_settings import BaseSettings, SettingsConfigDict


class DeduplicationStore(str, Enum):
    """Type of deduplication store to use"""
    SQLITE = "sqlite"
    REDIS = "redis"


class ConsumerSettings(BaseSettings):
    """Main configuration for ETL Narrative Engine"""

    # Service metadata
    service_name: str = "etl-narrative-engine"
    version: str = "v3.0"
    environment: str = "development"

    # Message Queue (RabbitMQ)
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    queue_name: str = "health_data_processing"
    exchange_name: str = "health_data_exchange"
    exchange_type: str = "topic"
    routing_key_pattern: str = "health.processing.#"
    dead_letter_queue: str = "health_data_dlq"
    prefetch_count: int = 1
    max_retries: int = 3
    retry_delays: list[int] = [30, 300, 900]  # 30s, 5m, 15m

    # Storage (S3/MinIO)
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket_name: str = "health-data"
    s3_region: str = "us-east-1"
    s3_use_ssl: bool = False

    # Deduplication
    deduplication_store: DeduplicationStore = DeduplicationStore.SQLITE
    deduplication_db_path: str = "/data/etl_processed_messages.db"
    deduplication_redis_url: str = "redis://localhost:6379/2"
    deduplication_retention_hours: int = 168  # 7 days

    # Processing limits
    max_file_size_mb: int = 100
    processing_timeout_seconds: int = 300
    data_quality_threshold: float = 0.7

    # Output paths in S3
    training_data_prefix: str = "training"
    quarantine_prefix: str = "quarantine"
    raw_data_prefix: str = "raw"

    # Logging
    log_level: str = "INFO"
    log_json: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ETL_",
        case_sensitive=False,
        extra="ignore"
    )


# Singleton settings instance
settings = ConsumerSettings()
