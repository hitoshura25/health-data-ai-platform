import os
from pydantic_settings import BaseSettings
from typing import Dict, Any, List

class MessageQueueSettings(BaseSettings):
    # RabbitMQ Connection
    rabbitmq_url: str = os.getenv("MQ_RABBITMQ_URL")
    rabbitmq_management_url: str = os.getenv("MQ_RABBITMQ_MANAGEMENT_URL")
    mq_rabbitmq_user: str = os.getenv("MQ_RABBITMQ_USER")
    mq_rabbitmq_pass: str = os.getenv("MQ_RABBITMQ_PASS")

    # Exchange Configuration
    main_exchange: str = "health_data_exchange"
    dlx_exchange: str = "health_data_dlx"

    # Queue Configuration
    processing_queue: str = "health_data_processing"
    failed_queue: str = "health_data_failed"

    # Retry Configuration
    max_retries: int = 3
    retry_delays: List[int] = [30, 300, 900]  # 30s, 5m, 15m

    # Redis
    redis_url: str = os.getenv("MQ_REDIS_URL")

    # Deduplication

    deduplication_retention_hours: int = 72

    # Message Configuration
    message_ttl_seconds: int = 1800  # 30 minutes
    enable_publisher_confirms: bool = True

    # Monitoring
    enable_metrics: bool = True
    metrics_port: int = 8001

    model_config = {
        "env_file": ".env",
        "env_prefix": "MQ_"
    }

settings = MessageQueueSettings()
