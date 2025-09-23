# Message Queue - Implementation Plan

A resilient messaging system using RabbitMQ with persistent deduplication, intelligent retry logic, and TTL-based delay patterns for reliable health data processing workflows.

## Overview

This message queue implementation provides reliable message delivery and processing for health data uploads, combining persistent deduplication tracking with intelligent retry mechanisms to ensure no data is lost or processed multiple times.

## Architecture Goals

- **Persistent Deduplication:** Use SQLite/file-based tracking for robust duplicate prevention
- **Intelligent Retry Logic:** TTL + Dead Letter Exchange pattern for exponential backoff
- **Operational Simplicity:** Leverage native RabbitMQ features without external dependencies
- **Message Intelligence:** Rich message format with embedded metadata for processing optimization

## Technology Stack

### Core Dependencies
```txt
pika==1.3.2
aio-pika==9.3.1
structlog==23.2.0
prometheus-client==0.19.0
tenacity==8.2.3
dataclasses-json==0.6.1
```

### Database for Deduplication
```txt
aiosqlite==0.19.0
```

## Implementation

### 1. Project Structure
```
message-queue/
├── config/
│   ├── __init__.py
│   ├── settings.py
│   └── rabbitmq_setup.py
├── core/
│   ├── __init__.py
│   ├── message.py
│   ├── deduplication.py
│   └── metrics.py
├── publisher/
│   ├── __init__.py
│   └── health_data_publisher.py
├── consumer/
│   ├── __init__.py
│   └── base_consumer.py
├── deployment/
│   ├── docker-compose.yml
│   ├── rabbitmq.conf
│   └── enabled_plugins
├── requirements.txt
└── README.md
```

### 2. Configuration (config/settings.py)
```python
from pydantic_settings import BaseSettings
from typing import Dict, Any

class MessageQueueSettings(BaseSettings):
    # RabbitMQ Connection
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672"
    rabbitmq_management_url: str = "http://localhost:15672"

    # Exchange Configuration
    main_exchange: str = "health_data_exchange"
    dlx_exchange: str = "health_data_dlx"

    # Queue Configuration
    processing_queue: str = "health_data_processing"
    failed_queue: str = "health_data_failed"

    # Retry Configuration
    max_retries: int = 3
    retry_delays: list = [30, 300, 900]  # 30s, 5m, 15m

    # Deduplication
    deduplication_db_path: str = "message_deduplication.db"
    deduplication_retention_hours: int = 72

    # Message Configuration
    message_ttl_seconds: int = 1800  # 30 minutes
    enable_publisher_confirms: bool = True

    # Monitoring
    enable_metrics: bool = True
    metrics_port: int = 8001

    class Config:
        env_file = ".env"
        env_prefix = "MQ_"

settings = MessageQueueSettings()
```

### 3. Message Format (core/message.py)
```python
from dataclasses import dataclass, asdict
from dataclasses_json import dataclass_json
from typing import Dict, Any, Optional
import json
import hashlib
from datetime import datetime

@dataclass_json
@dataclass
class HealthDataMessage:
    """Intelligent health data message format"""

    # Core message data
    bucket: str
    key: str
    user_id: str
    upload_timestamp_utc: str
    record_type: str

    # Message identification
    correlation_id: str
    message_id: str

    # Deduplication
    content_hash: str  # SHA256 of file content
    idempotency_key: str

    # Processing metadata
    retry_count: int = 0
    max_retries: int = 3
    processing_priority: str = "normal"  # low, normal, high

    # File metadata
    file_size_bytes: int
    record_count: Optional[int] = None

    # Optional health data metadata
    health_metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Generate idempotency key if not provided"""
        if not self.idempotency_key:
            key_input = f"{self.user_id}:{self.content_hash}:{self.upload_timestamp_utc}"
            self.idempotency_key = hashlib.sha256(key_input.encode()).hexdigest()[:16]

    def to_json(self) -> str:
        """Convert to JSON for publishing"""
        return json.dumps(asdict(self), default=str, separators=(',', ':'))

    @classmethod
    def from_json(cls, json_str: str) -> 'HealthDataMessage':
        """Create from JSON"""
        data = json.loads(json_str)
        return cls(**data)

    def get_routing_key(self) -> str:
        """Generate routing key for topic exchange"""
        return f"health.processing.{self.record_type.lower()}.{self.processing_priority}"

    def get_retry_routing_key(self) -> str:
        """Generate routing key for retry scenarios"""
        return f"health.retry.{self.record_type.lower()}.attempt_{self.retry_count}"

    def increment_retry(self) -> 'HealthDataMessage':
        """Create new message with incremented retry count"""
        self.retry_count += 1
        return self

    def calculate_retry_delay(self) -> int:
        """Calculate delay for current retry attempt"""
        from config.settings import settings
        delays = settings.retry_delays
        return delays[min(self.retry_count - 1, len(delays) - 1)]
```

### 4. Persistent Deduplication (core/deduplication.py)
```python
import aiosqlite
import asyncio
from datetime import datetime, timedelta
from typing import Optional
import structlog

logger = structlog.get_logger()

class PersistentDeduplicationStore:
    """SQLite-based persistent deduplication tracking"""

    def __init__(self, db_path: str, retention_hours: int = 72):
        self.db_path = db_path
        self.retention_hours = retention_hours
        self._lock = asyncio.Lock()

    async def initialize(self):
        """Initialize database tables"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS processed_messages (
                    idempotency_key TEXT PRIMARY KEY,
                    message_id TEXT NOT NULL,
                    correlation_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    record_type TEXT NOT NULL,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processing_duration_seconds REAL,
                    status TEXT DEFAULT 'completed'
                )
            """)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_processed_at
                ON processed_messages(processed_at)
            """)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_record_type
                ON processed_messages(user_id, record_type)
            """)

            await db.commit()

        logger.info("Deduplication store initialized", db_path=self.db_path)

    async def is_already_processed(self, idempotency_key: str) -> bool:
        """Check if message was already processed"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT 1 FROM processed_messages WHERE idempotency_key = ?",
                    (idempotency_key,)
                )
                result = await cursor.fetchone()
                return result is not None

    async def mark_processing_started(self, message: 'HealthDataMessage'):
        """Mark message as processing started"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO processed_messages
                    (idempotency_key, message_id, correlation_id, user_id, record_type, status)
                    VALUES (?, ?, ?, ?, ?, 'processing')
                """, (
                    message.idempotency_key,
                    message.message_id,
                    message.correlation_id,
                    message.user_id,
                    message.record_type
                ))
                await db.commit()

    async def mark_processing_completed(
        self,
        idempotency_key: str,
        processing_duration: float
    ):
        """Mark message as successfully processed"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    UPDATE processed_messages
                    SET status = 'completed', processing_duration_seconds = ?
                    WHERE idempotency_key = ?
                """, (processing_duration, idempotency_key))
                await db.commit()

    async def mark_processing_failed(self, idempotency_key: str, error_message: str):
        """Mark message as failed"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    UPDATE processed_messages
                    SET status = 'failed'
                    WHERE idempotency_key = ?
                """, (idempotency_key,))
                await db.commit()

    async def cleanup_old_records(self):
        """Remove old processed message records"""
        cutoff_time = datetime.utcnow() - timedelta(hours=self.retention_hours)

        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "DELETE FROM processed_messages WHERE processed_at < ?",
                    (cutoff_time.isoformat(),)
                )
                deleted_count = cursor.rowcount
                await db.commit()

        logger.info("Cleaned up old deduplication records",
                   deleted_count=deleted_count,
                   cutoff_time=cutoff_time)

    async def get_processing_stats(self) -> dict:
        """Get processing statistics"""
        async with aiosqlite.connect(self.db_path) as db:
            # Total processed messages
            cursor = await db.execute("SELECT COUNT(*) FROM processed_messages")
            total_processed = (await cursor.fetchone())[0]

            # Messages by status
            cursor = await db.execute("""
                SELECT status, COUNT(*)
                FROM processed_messages
                GROUP BY status
            """)
            status_counts = dict(await cursor.fetchall())

            # Messages by record type (last 24 hours)
            cursor = await db.execute("""
                SELECT record_type, COUNT(*)
                FROM processed_messages
                WHERE processed_at > datetime('now', '-24 hours')
                GROUP BY record_type
            """)
            recent_by_type = dict(await cursor.fetchall())

            return {
                "total_processed": total_processed,
                "status_distribution": status_counts,
                "recent_24h_by_type": recent_by_type
            }
```

### 5. Publisher Implementation (publisher/health_data_publisher.py)
```python
import aio_pika
import asyncio
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential
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
        """Initialize publisher connection and exchanges"""
        if self._initialized:
            return

        try:
            # Create robust connection with heartbeat
            self.connection = await aio_pika.connect_robust(
                settings.rabbitmq_url,
                heartbeat=60
            )

            self.channel = await self.connection.channel()

            # Enable publisher confirms for reliability
            if settings.enable_publisher_confirms:
                await self.channel.confirm_delivery()

            # Declare exchanges
            await self._declare_exchanges()

            # Declare queues
            await self._declare_queues()

            self._initialized = True
            logger.info("Health data publisher initialized")

        except Exception as e:
            logger.error("Failed to initialize publisher", error=str(e))
            raise

    async def _declare_exchanges(self):
        """Declare required exchanges"""
        # Main exchange for health data
        await self.channel.declare_exchange(
            settings.main_exchange,
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )

        # Dead letter exchange for failed messages
        await self.channel.declare_exchange(
            settings.dlx_exchange,
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )

    async def _declare_queues(self):
        """Declare required queues with proper configuration"""
        # Main processing queue
        processing_queue = await self.channel.declare_queue(
            settings.processing_queue,
            durable=True,
            arguments={
                "x-message-ttl": settings.message_ttl_seconds * 1000,
                "x-dead-letter-exchange": settings.dlx_exchange,
                "x-dead-letter-routing-key": "failed.processing"
            }
        )

        # Bind processing queue to main exchange
        await processing_queue.bind(
            settings.main_exchange,
            "health.processing.*"
        )

        # Failed messages queue
        failed_queue = await self.channel.declare_queue(
            settings.failed_queue,
            durable=True
        )

        # Bind failed queue to DLX
        await failed_queue.bind(
            settings.dlx_exchange,
            "failed.#"
        )

        # Create retry queues with TTL
        for i, delay in enumerate(settings.retry_delays):
            retry_queue_name = f"health_data_retry_{delay}s"
            retry_queue = await self.channel.declare_queue(
                retry_queue_name,
                durable=True,
                arguments={
                    "x-message-ttl": delay * 1000,  # Convert to milliseconds
                    "x-dead-letter-exchange": settings.main_exchange,
                    "x-dead-letter-routing-key": "health.processing.retry"
                }
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def publish_health_data_message(self, message: HealthDataMessage) -> bool:
        """Publish health data message with reliability guarantees"""
        if not self._initialized:
            await self.initialize()

        start_time = datetime.utcnow()

        try:
            # Get routing key
            routing_key = message.get_routing_key()

            # Create AMQP message
            amqp_message = aio_pika.Message(
                message.to_json().encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                message_id=message.message_id,
                correlation_id=message.correlation_id,
                timestamp=datetime.utcnow(),
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
            if settings.enable_publisher_confirms:
                confirmed = await exchange.publish(
                    amqp_message,
                    routing_key=routing_key,
                    mandatory=True
                )

                if not confirmed:
                    raise Exception("Message publish not confirmed by broker")
            else:
                await exchange.publish(
                    amqp_message,
                    routing_key=routing_key,
                    mandatory=True
                )

            # Record metrics
            duration = (datetime.utcnow() - start_time).total_seconds()
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
        """Close publisher connection"""
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
            self._initialized = False
            logger.info("Publisher connection closed")
```

### 6. Base Consumer (consumer/base_consumer.py)
```python
import aio_pika
import asyncio
import time
from abc import ABC, abstractmethod
from core.message import HealthDataMessage
from core.deduplication import PersistentDeduplicationStore
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
        self.deduplication_store = PersistentDeduplicationStore(
            settings.deduplication_db_path,
            settings.deduplication_retention_hours
        )
        self.metrics = MessageQueueMetrics()
        self.publisher = HealthDataPublisher()  # For retry publishing
        self._consuming = False

    async def initialize(self):
        """Initialize consumer"""
        # Initialize deduplication store
        await self.deduplication_store.initialize()

        # Initialize publisher for retries
        await self.publisher.initialize()

        # Create connection
        self.connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        self.channel = await self.connection.channel()

        # Set QoS for fair distribution
        await self.channel.set_qos(prefetch_count=1)

        logger.info("Consumer initialized", queue=self.queue_name)

    async def start_consuming(self):
        """Start consuming messages"""
        if not self.connection:
            await self.initialize()

        queue = await self.channel.get_queue(self.queue_name)

        async def message_handler(message: aio_pika.IncomingMessage):
            await self._process_message_with_idempotency(message)

        await queue.consume(message_handler, auto_ack=False)
        self._consuming = True

        logger.info("Started consuming messages", queue=self.queue_name)

        # Start background cleanup task
        asyncio.create_task(self._periodic_cleanup())

        try:
            # Keep consuming until stopped
            await asyncio.Future()  # Run forever
        except asyncio.CancelledError:
            logger.info("Consumer cancelled")
        finally:
            self._consuming = False

    async def _process_message_with_idempotency(self, message: aio_pika.IncomingMessage):
        """Process message with comprehensive idempotency checking"""
        start_time = time.time()
        health_message = None

        try:
            # Parse message
            health_message = HealthDataMessage.from_json(message.body.decode())

            with structlog.contextvars.bound_contextvars(
                message_id=health_message.message_id,
                correlation_id=health_message.correlation_id,
                idempotency_key=health_message.idempotency_key
            ):
                # Check for duplicate
                if await self.deduplication_store.is_already_processed(health_message.idempotency_key):
                    logger.info("Duplicate message detected, skipping")
                    await message.ack()
                    self.metrics.record_duplicate_message(health_message.record_type)
                    return

                # Mark as processing started
                await self.deduplication_store.mark_processing_started(health_message)

                # Process message (implemented by subclass)
                success = await self.process_health_message(health_message)

                processing_time = time.time() - start_time

                if success:
                    # Mark as completed
                    await self.deduplication_store.mark_processing_completed(
                        health_message.idempotency_key,
                        processing_time
                    )

                    # Acknowledge message
                    await message.ack()

                    # Record metrics
                    self.metrics.record_processing_success(
                        queue=self.queue_name,
                        record_type=health_message.record_type,
                        duration=processing_time
                    )

                    logger.info("Message processed successfully",
                               processing_time=processing_time)
                else:
                    await self._handle_processing_failure(message, health_message)

        except Exception as e:
            logger.error("Error processing message", error=str(e))
            await self._handle_processing_failure(message, health_message)

    async def _handle_processing_failure(
        self,
        message: aio_pika.IncomingMessage,
        health_message: HealthDataMessage
    ):
        """Handle message processing failures with intelligent retry"""

        if health_message and health_message.retry_count < health_message.max_retries:
            # Attempt retry
            retry_success = await self.publisher.publish_retry_message(health_message)

            if retry_success:
                # Acknowledge original message (retry is now queued)
                await message.ack()

                self.metrics.record_retry_attempt(
                    record_type=health_message.record_type,
                    retry_count=health_message.retry_count
                )

                logger.info("Message scheduled for retry",
                           retry_count=health_message.retry_count)
            else:
                # Failed to schedule retry - send to DLX
                await message.reject(requeue=False)
                self.metrics.record_permanent_failure(health_message.record_type)
        else:
            # Max retries exceeded or invalid message - send to DLX
            await message.reject(requeue=False)

            if health_message:
                await self.deduplication_store.mark_processing_failed(
                    health_message.idempotency_key,
                    "max_retries_exceeded"
                )
                self.metrics.record_permanent_failure(health_message.record_type)

            logger.error("Message permanently failed")

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
            except Exception as e:
                logger.error("Cleanup task failed", error=str(e))

    async def stop(self):
        """Stop consuming messages"""
        self._consuming = False
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
        await self.publisher.close()
        logger.info("Consumer stopped")
```

### 7. Metrics (core/metrics.py)
```python
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import structlog

logger = structlog.get_logger()

class MessageQueueMetrics:
    """Comprehensive message queue metrics"""

    def __init__(self):
        # Publisher metrics
        self.messages_published = Counter(
            'mq_messages_published_total',
            'Total published messages',
            ['exchange', 'routing_key', 'status']
        )

        self.publish_duration = Histogram(
            'mq_publish_duration_seconds',
            'Message publish duration',
            ['exchange']
        )

        # Consumer metrics
        self.messages_processed = Counter(
            'mq_messages_processed_total',
            'Total processed messages',
            ['queue', 'record_type', 'status']
        )

        self.processing_duration = Histogram(
            'mq_processing_duration_seconds',
            'Message processing duration',
            ['queue', 'record_type']
        )

        # Retry metrics
        self.retry_attempts = Counter(
            'mq_retry_attempts_total',
            'Total retry attempts',
            ['record_type', 'retry_count']
        )

        self.retry_scheduled = Counter(
            'mq_retry_scheduled_total',
            'Total retries scheduled',
            ['record_type', 'delay_seconds']
        )

        # Deduplication metrics
        self.duplicate_messages = Counter(
            'mq_duplicate_messages_total',
            'Duplicate messages detected',
            ['record_type']
        )

        # Failure metrics
        self.permanent_failures = Counter(
            'mq_permanent_failures_total',
            'Permanent message failures',
            ['record_type']
        )

        # System metrics
        self.active_connections = Gauge(
            'mq_active_connections',
            'Number of active connections'
        )

    def record_publish_success(self, exchange: str, routing_key: str, duration: float):
        self.messages_published.labels(exchange=exchange, routing_key=routing_key, status="success").inc()
        self.publish_duration.labels(exchange=exchange).observe(duration)

    def record_publish_failure(self, exchange: str, error_type: str):
        self.messages_published.labels(exchange=exchange, routing_key="unknown", status="failed").inc()

    def record_processing_success(self, queue: str, record_type: str, duration: float):
        self.messages_processed.labels(queue=queue, record_type=record_type, status="success").inc()
        self.processing_duration.labels(queue=queue, record_type=record_type).observe(duration)

    def record_retry_attempt(self, record_type: str, retry_count: int):
        self.retry_attempts.labels(record_type=record_type, retry_count=str(retry_count)).inc()

    def record_retry_scheduled(self, record_type: str, retry_count: int, delay_seconds: int):
        self.retry_scheduled.labels(record_type=record_type, delay_seconds=str(delay_seconds)).inc()

    def record_duplicate_message(self, record_type: str):
        self.duplicate_messages.labels(record_type=record_type).inc()

    def record_permanent_failure(self, record_type: str):
        self.permanent_failures.labels(record_type=record_type).inc()

    def start_metrics_server(self, port: int = 8001):
        """Start Prometheus metrics server"""
        start_http_server(port)
        logger.info("Metrics server started", port=port)
```

### 8. RabbitMQ Setup (config/rabbitmq_setup.py)
```python
import aio_pika
from config.settings import settings
import structlog

logger = structlog.get_logger()

async def setup_rabbitmq_infrastructure():
    """Set up RabbitMQ exchanges and queues"""
    connection = await aio_pika.connect(settings.rabbitmq_url)
    channel = await connection.channel()

    try:
        # Declare exchanges
        main_exchange = await channel.declare_exchange(
            settings.main_exchange,
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )

        dlx_exchange = await channel.declare_exchange(
            settings.dlx_exchange,
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )

        # Declare main processing queue
        processing_queue = await channel.declare_queue(
            settings.processing_queue,
            durable=True,
            arguments={
                "x-message-ttl": settings.message_ttl_seconds * 1000,
                "x-dead-letter-exchange": settings.dlx_exchange,
                "x-dead-letter-routing-key": "failed.processing"
            }
        )

        # Bind processing queue
        await processing_queue.bind(main_exchange, "health.processing.#")

        # Declare failed queue
        failed_queue = await channel.declare_queue(
            settings.failed_queue,
            durable=True
        )

        # Bind failed queue
        await failed_queue.bind(dlx_exchange, "failed.#")

        # Create retry queues
        for delay in settings.retry_delays:
            retry_queue = await channel.declare_queue(
                f"health_data_retry_{delay}s",
                durable=True,
                arguments={
                    "x-message-ttl": delay * 1000,
                    "x-dead-letter-exchange": settings.main_exchange,
                    "x-dead-letter-routing-key": "health.processing.retry"
                }
            )

        logger.info("RabbitMQ infrastructure setup completed")

    finally:
        await connection.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(setup_rabbitmq_infrastructure())
```

### 9. Docker Configuration

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  rabbitmq:
    image: rabbitmq:3.12-management
    container_name: health-rabbitmq
    environment:
      RABBITMQ_DEFAULT_USER: ${RABBITMQ_USER:-guest}
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASS:-guest}
      RABBITMQ_DEFAULT_VHOST: /
    ports:
      - "5672:5672"    # AMQP port
      - "15672:15672"  # Management UI
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
      - ./deployment/rabbitmq.conf:/etc/rabbitmq/rabbitmq.conf:ro
      - ./deployment/enabled_plugins:/etc/rabbitmq/enabled_plugins:ro
    healthcheck:
      test: rabbitmq-diagnostics -q ping
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  message-queue-setup:
    build: .
    command: python config/rabbitmq_setup.py
    environment:
      MQ_RABBITMQ_URL: amqp://guest:guest@rabbitmq:5672
    depends_on:
      - rabbitmq
    restart: "no"

volumes:
  rabbitmq_data:
```

**deployment/rabbitmq.conf:**
```ini
# Memory and disk settings
vm_memory_high_watermark.relative = 0.6
disk_free_limit.relative = 2.0

# Connection settings
heartbeat = 60
frame_max = 131072

# Logging
log.file.level = info
log.connection.level = info

# Management plugin
management.tcp.port = 15672
management.tcp.ip = 0.0.0.0

# Queue settings
queue_master_locator = min-masters

# Message store settings
msg_store_file_size_limit = 16777216
```

**deployment/enabled_plugins:**
```
[rabbitmq_management,rabbitmq_management_agent].
```

### 10. Environment Configuration (.env.example)
```bash
# RabbitMQ Configuration
MQ_RABBITMQ_URL=amqp://guest:guest@localhost:5672
MQ_RABBITMQ_MANAGEMENT_URL=http://localhost:15672

# Exchange and Queue Names
MQ_MAIN_EXCHANGE=health_data_exchange
MQ_DLX_EXCHANGE=health_data_dlx
MQ_PROCESSING_QUEUE=health_data_processing
MQ_FAILED_QUEUE=health_data_failed

# Retry Configuration
MQ_MAX_RETRIES=3
MQ_RETRY_DELAYS=[30, 300, 900]

# Deduplication
MQ_DEDUPLICATION_DB_PATH=message_deduplication.db
MQ_DEDUPLICATION_RETENTION_HOURS=72

# Message Settings
MQ_MESSAGE_TTL_SECONDS=1800
MQ_ENABLE_PUBLISHER_CONFIRMS=true

# Monitoring
MQ_ENABLE_METRICS=true
MQ_METRICS_PORT=8001
```

## Usage Examples

### Publisher Usage
```python
from publisher.health_data_publisher import HealthDataPublisher
from core.message import HealthDataMessage

async def publish_example():
    publisher = HealthDataPublisher()
    await publisher.initialize()

    message = HealthDataMessage(
        bucket="health-data",
        key="raw/BloodGlucoseRecord/2025/09/22/user123_20250922_120000_abc12345.avro",
        user_id="user123",
        upload_timestamp_utc="2025-09-22T12:00:00Z",
        record_type="BloodGlucoseRecord",
        correlation_id="corr-123",
        message_id="msg-456",
        content_hash="sha256-hash-here",
        idempotency_key="",  # Will be auto-generated
        file_size_bytes=1024,
        record_count=10
    )

    success = await publisher.publish_health_data_message(message)
    print(f"Message published: {success}")
```

### Consumer Implementation
```python
from consumer.base_consumer import BaseIdempotentConsumer
from core.message import HealthDataMessage

class HealthDataETLConsumer(BaseIdempotentConsumer):
    async def process_health_message(self, message: HealthDataMessage) -> bool:
        try:
            # Your ETL processing logic here
            print(f"Processing {message.record_type} for user {message.user_id}")

            # Simulate processing
            await asyncio.sleep(1)

            return True  # Success
        except Exception as e:
            print(f"Processing failed: {e}")
            return False  # Will trigger retry

# Usage
async def run_consumer():
    consumer = HealthDataETLConsumer()
    await consumer.start_consuming()
```

## Deployment Instructions

### Development
1. **Install dependencies:** `pip install -r requirements.txt`
2. **Start RabbitMQ:** `docker-compose up -d rabbitmq`
3. **Setup infrastructure:** `python config/rabbitmq_setup.py`
4. **Run publisher/consumer:** Use the examples above

### Production
1. **Configure environment:** Set all required environment variables
2. **Deploy:** `docker-compose up -d`
3. **Monitor:** Access metrics at `http://localhost:8001/metrics`

## Monitoring and Operations

- **RabbitMQ Management:** `http://localhost:15672`
- **Prometheus Metrics:** `http://localhost:8001/metrics`
- **Deduplication Stats:** Query the SQLite database for processing statistics
- **Queue Monitoring:** Use RabbitMQ management interface for queue depths and rates

## Integration Points

- **API Service:** Publishes health data messages after file upload
- **ETL Engine:** Consumes messages for data processing
- **Monitoring:** Exports metrics for Prometheus scraping

This implementation provides enterprise-grade message reliability with persistent deduplication and intelligent retry logic while maintaining operational simplicity through native RabbitMQ features.