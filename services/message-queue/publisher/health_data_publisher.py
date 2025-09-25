import aio_pika
import asyncio
from datetime import datetime, timezone
from tenacity import retry, stop_after_attempt, wait_exponential
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.message import HealthDataMessage
from core.metrics import MessageQueueMetrics
from config.settings import settings
import structlog

logger = structlog.get_logger()

class HealthDataPublisher:
    """Reliable health data message publisher"""

    def __init__(self):
        self.connection = None
        self.channel = None
        self.metrics = MessageQueueMetrics()
        self._initialized = False


    async def initialize(self):
        """Initialize publisher, creating its own connection and channel."""
        if self._initialized:
            return

        try:
            self.connection = await aio_pika.connect_robust(
                settings.rabbitmq_url,
                heartbeat=60
            )
            self.channel = await self.connection.channel()

            # Declare the exchange on a new channel
            async with self.connection.channel() as channel:
                await channel.declare_exchange(
                    name=settings.main_exchange,
                    type=aio_pika.ExchangeType.TOPIC,
                    durable=True
                )



            self._initialized = True
            logger.info("Health data publisher initialized")

        except Exception as e:
            logger.error("Failed to initialize publisher", error=str(e))
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def publish_health_data_message(self, message: HealthDataMessage) -> bool:
        """Publish health data message with reliability guarantees"""
        if not self._initialized:
            await self.initialize()

        start_time = datetime.now(timezone.utc)

        try:
            # Get routing key
            routing_key = message.get_routing_key()

            # Create AMQP message
            amqp_message = aio_pika.Message(
                message.to_json().encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                message_id=message.message_id,
                correlation_id=message.correlation_id,
                timestamp=datetime.now(timezone.utc),
                headers={
                    'retry_count': message.retry_count,
                    'idempotency_key': message.idempotency_key,
                    'record_type': message.record_type,
                    'user_id': message.user_id,
                    'processing_priority': message.processing_priority
                }
            )

            # Get exchange
            exchange = await self.channel.get_exchange(settings.main_exchange)

            # Publish with mandatory flag
            await exchange.publish(
                amqp_message,
                routing_key=routing_key,
                mandatory=True
            )

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.metrics.record_publish_success(
                exchange=settings.main_exchange,
                routing_key=routing_key,
                duration=duration
            )

            logger.info("Message published successfully",
                       message_id=message.message_id,
                       correlation_id=message.correlation_id,
                       routing_key=routing_key)

            return True

        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            self.metrics.record_publish_failure(
                exchange=settings.main_exchange,
                error_type=type(e).__name__
            )

            logger.error("Failed to publish message",
                        message_id=message.message_id,
                        correlation_id=message.correlation_id,
                        error=str(e))
            raise

    async def publish_retry_message(self, message: HealthDataMessage) -> bool:
        """Publish message to retry queue with delay"""
        if message.retry_count >= message.max_retries:
            logger.error("Message exceeded max retries",
                        message_id=message.message_id,
                        retry_count=message.retry_count)
            return False

        # Increment retry count
        message.increment_retry()

        # Calculate delay
        delay_seconds = message.calculate_retry_delay()
        retry_queue_name = f"health_data_retry_{delay_seconds}s"

        # Create retry message
        retry_amqp_message = aio_pika.Message(
            message.to_json().encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            message_id=message.message_id,
            correlation_id=message.correlation_id,
            headers={
                'retry_count': message.retry_count,
                'original_routing_key': message.get_routing_key(),
                'retry_delay_seconds': delay_seconds
            }
        )

        # Publish to retry queue (will be auto-routed back after TTL)
        await self.channel.default_exchange.publish(
            retry_amqp_message,
            routing_key=retry_queue_name
        )

        self.metrics.record_retry_scheduled(
            record_type=message.record_type,
            retry_count=message.retry_count,
            delay_seconds=delay_seconds
        )

        logger.info("Message scheduled for retry",
                   message_id=message.message_id,
                   retry_count=message.retry_count,
                   delay_seconds=delay_seconds)

        return True

    async def close(self):
        """Close publisher connection."""
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
            self._initialized = False
            logger.info("Publisher connection closed")
