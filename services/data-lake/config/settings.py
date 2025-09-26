from pydantic_settings import BaseSettings
from typing import List, Dict, Any

class DataLakeSettings(BaseSettings):
    # MinIO Connection
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str
    minio_secret_key: str
    minio_kms_secret_key: str = ""
    minio_secure: bool = False
    minio_region: str = "us-east-1"

    # Bucket Configuration
    bucket_name: str = "health-data"
    create_bucket_on_startup: bool = True

    # Object Naming
    max_object_key_length: int = 1024
    hash_length: int = 8

    # Data Quality
    enable_quality_validation: bool = True
    quality_threshold: float = 0.7
    quarantine_retention_days: int = 30

    # Lifecycle Management
    raw_data_glacier_days: int = 90
    raw_data_deep_archive_days: int = 365
    raw_data_expiration_days: int = 2555  # 7 years
    processed_data_glacier_days: int = 180
    processed_data_expiration_days: int = 3650  # 10 years

    # Security
    enable_encryption: bool = False
    enable_versioning: bool = True
    enable_audit_logging: bool = True

    # Monitoring
    enable_metrics: bool = True
    metrics_port: int = 8002
    analytics_update_interval_hours: int = 6

    # Storage Classes
    storage_classes: Dict[str, str] = {
        "standard": "STANDARD",
        "glacier": "GLACIER",
        "deep_archive": "DEEP_ARCHIVE"
    }

    model_config = {
        "env_prefix": "DATALAKE_",
        "env_file": ".env"
    }

settings = DataLakeSettings()