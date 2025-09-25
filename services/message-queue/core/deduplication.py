import asyncio
import redis.asyncio as redis
from datetime import timedelta
from typing import Optional
import structlog

from .message import HealthDataMessage
from config.settings import settings

logger = structlog.get_logger()

class RedisDeduplicationStore:
    """Redis-based persistent deduplication tracking"""

    def __init__(self, retention_hours: int = 72):
        self.redis_client = None
        # Convert retention to seconds for Redis TTL
        self.retention_seconds = int(timedelta(hours=retention_hours).total_seconds())

    async def initialize(self):
        """Initialize the Redis connection."""
        if self.redis_client:
            return
        try:
            self.redis_client = redis.from_url(
                settings.redis_url, decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("Deduplication store initialized", store="Redis")
        except Exception as e:
            logger.error("Failed to initialize Redis deduplication store", error=e)
            raise

    async def is_already_processed(self, idempotency_key: str) -> bool:
        """Check if message was already processed using EXISTS."""
        return await self.redis_client.exists(idempotency_key) > 0

    async def mark_processing_started(self, message: HealthDataMessage):
        """Mark message as processing started by setting a key with a short TTL."""
        # Set a short TTL for the "processing" state
        await self.redis_client.set(message.idempotency_key, "processing", ex=600) # 10 minutes

    async def mark_processing_completed(self, idempotency_key: str, processing_duration: float):
        """Mark message as successfully processed by setting the key with the full retention TTL."""
        await self.redis_client.set(idempotency_key, "completed", ex=self.retention_seconds)

    async def mark_processing_failed(self, idempotency_key: str, error_message: str):
        """Mark message as failed, also with the full retention TTL to prevent retries."""
        await self.redis_client.set(idempotency_key, "failed", ex=self.retention_seconds)

    async def cleanup_old_records(self):
        """This is a no-op for Redis as TTL handles expiration automatically."""
        logger.debug("Cleanup is handled automatically by Redis TTL.")
        pass

    async def _get_status_for_testing(self, idempotency_key: str) -> Optional[str]:
        """FOR TESTING ONLY: Gets the status of a message."""
        return await self.redis_client.get(idempotency_key)

    async def close(self):
        """Close the Redis connection."""
        if self.redis_client:
            await self.redis_client.aclose()
            logger.info("Deduplication store connection closed.")
