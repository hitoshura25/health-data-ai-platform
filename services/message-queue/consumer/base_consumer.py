import aio_pika
import asyncio
import time
import sys
import os
from abc import ABC, abstractmethod

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.message import HealthDataMessage
from core.deduplication import RedisDeduplicationStore
from core.metrics import MessageQueueMetrics
from publisher.health_data_publisher import HealthDataPublisher
from config.settings import settings
import structlog

logger = structlog.get_logger()

class BaseIdempotentConsumer(ABC):
    """Base class for idempotent message consumers"""

    def __init__(self, queue_name: str = None):
        self.queue_name = queue_name or settings.processing_queue
        self.connection = None
        self.channel = None
        self.deduplication_store = RedisDeduplicationStore(
            retention_hours=settings.deduplication_retention_hours
        )
        self.metrics = MessageQueueMetrics()
        self.publisher = HealthDataPublisher()  # For retry publishing
        self._consuming = False
        self._consumer_tag = None
        self._stopped_future = None

    async def initialize(self):
        """Initialize consumer and all its dependencies with a single connection."""
        await self.deduplication_store.initialize()

        self.connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        self.channel = await self.connection.channel()
        await self.channel.set_qos(prefetch_count=1)

        # Initialize the publisher with the consumer's channel
        await self.publisher.initialize(channel=self.channel)

        logger.info("Consumer initialized", queue=self.queue_name)

    async def start_consuming(self):
        """Start consuming messages using a callback."""
        if not self.connection:
            await self.initialize()

        queue = await self.channel.get_queue(self.queue_name)

        logger.info("Started consuming messages", queue=self.queue_name)
        self._consuming = True
        self._stopped_future = asyncio.Future()

        self._consumer_tag = await queue.consume(self._process_message_with_idempotency)

        # Wait until the consumer is stopped
        await self._stopped_future

    async def _process_message_with_idempotency(self, message: aio_pika.IncomingMessage):
        """Process message with comprehensive idempotency checking"""
        start_time = time.time()
        health_message = None

        try:
            health_message = HealthDataMessage.from_json(message.body.decode())

            with structlog.contextvars.bound_contextvars(
                message_id=health_message.message_id,
                correlation_id=health_message.correlation_id,
                idempotency_key=health_message.idempotency_key
            ):
                if await self.deduplication_store.is_already_processed(health_message.idempotency_key):
                    logger.info("Duplicate message detected, skipping")
                    await message.ack()
                    self.metrics.record_duplicate_message(health_message.record_type)
                    return

                await self.deduplication_store.mark_processing_started(health_message)

                success = await self.process_health_message(health_message)

                processing_time = time.time() - start_time

                if success:
                    await self.deduplication_store.mark_processing_completed(
                        health_message.idempotency_key,
                        processing_time
                    )
                    await message.ack()
                    self.metrics.record_processing_success(
                        queue=self.queue_name,
                        record_type=health_message.record_type,
                        duration=processing_time
                    )
                    logger.info("Message processed successfully", processing_time=processing_time)
                else:
                    await self._handle_processing_failure(message, health_message)

        except Exception as e:
            logger.error("Error processing message", error=str(e))
            if message.acknowledged:
                return
            await self._handle_processing_failure(message, health_message)

    async def _handle_processing_failure(
        self,
        message: aio_pika.IncomingMessage,
        health_message: HealthDataMessage
    ):
        """Handle message processing failures with intelligent retry"""
        try:
            if health_message and health_message.retry_count < health_message.max_retries:
                retry_success = await self.publisher.publish_retry_message(health_message)
                if retry_success:
                    await message.ack()
                    self.metrics.record_retry_attempt(
                        record_type=health_message.record_type,
                        retry_count=health_message.retry_count
                    )
                    logger.info("Message scheduled for retry", retry_count=health_message.retry_count)
                    return

            # If retry fails or not possible, reject to DLX
            await message.reject(requeue=False)
            if health_message:
                await self.deduplication_store.mark_processing_failed(
                    health_message.idempotency_key,
                    "max_retries_exceeded"
                )
                self.metrics.record_permanent_failure(health_message.record_type)
            logger.error("Message permanently failed")
        except Exception as e:
            logger.error("Critical error in failure handler", error=str(e))
            # Ensure message is not lost even if handler fails
            if not message.acknowledged:
                await message.reject(requeue=False)

    @abstractmethod
    async def process_health_message(self, message: HealthDataMessage) -> bool:
        """Process the health message - implemented by subclasses"""
        pass

    async def _periodic_cleanup(self):
        """Periodic cleanup of old deduplication records"""
        while self._consuming:
            try:
                await asyncio.sleep(3600)  # Run every hour
                await self.deduplication_store.cleanup_old_records()
            except asyncio.CancelledError:
                break # Stop cleanup on consumer stop
            except Exception as e:
                logger.error("Cleanup task failed", error=str(e))

    async def stop(self):
        """Stop consuming messages gracefully."""
        if not self._consuming:
            return

        logger.info("Stopping consumer...")
        self._consuming = False

        if self._consumer_tag and self.channel:
            try:
                await self.channel.cancel(self._consumer_tag)
            except aio_pika.exceptions.ChannelClosed:
                pass # Channel might already be closed

        await self.publisher.close() # This is safe, does nothing for external channel
        await self.deduplication_store.close()

        if self.connection and not self.connection.is_closed:
            await self.connection.close()
        
        if self._stopped_future and not self._stopped_future.done():
            self._stopped_future.set_result(True)

        logger.info("Consumer stopped")
