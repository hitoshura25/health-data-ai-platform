import aio_pika
import json
from tenacity import retry, stop_after_attempt, wait_exponential
from app.config import settings
from datetime import datetime, timezone
import structlog

logger = structlog.get_logger()

class RabbitMQService:
    def __init__(self):
        self.connection = None
        self.channel = None

    async def initialize(self):
        """Initialize RabbitMQ connection"""
        self.connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        self.channel = await self.connection.channel()
        await self.channel.declare_exchange(
            name=settings.RABBITMQ_MAIN_EXCHANGE,
            type=aio_pika.ExchangeType.TOPIC,
            durable=True
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5)
    )
    async def publish_health_data_message(self, message_data: dict) -> bool:
        """Publish health data processing message"""
        try:
            # Create message with persistence
            message = aio_pika.Message(
                json.dumps(message_data).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                timestamp=datetime.now(timezone.utc)
            )

            # Publish to topic exchange
            exchange = await self.channel.get_exchange(settings.RABBITMQ_MAIN_EXCHANGE, ensure=True)
            routing_key = f"health.processing.{message_data.get('record_type', 'unknown').lower()}"

            await exchange.publish(message, routing_key=routing_key, mandatory=True)

            logger.info("Message published successfully",
                       correlation_id=message_data.get('correlation_id'),
                       routing_key=routing_key)
            return True

        except Exception as e:
            logger.error("Message publishing failed", error=str(e))
            raise

    async def check_connection(self) -> bool:
        """Check RabbitMQ connection health"""
        try:
            if self.connection and not self.connection.is_closed:
                return True
        except Exception:
            pass
        return False

    async def close(self):
        """Close RabbitMQ connection"""
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
