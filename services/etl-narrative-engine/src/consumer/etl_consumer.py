"""
Main ETL consumer for processing health data messages from RabbitMQ.

This consumer:
1. Receives messages from RabbitMQ
2. Checks deduplication
3. Downloads files from S3/MinIO
4. Parses Avro records
5. Routes to appropriate clinical processor
6. Handles errors with retry logic
"""

import asyncio
import json
import time
from typing import Any

import structlog
from aio_pika import ExchangeType, IncomingMessage, Message, connect_robust

from ..config.settings import settings
from ..processors.processor_factory import MOCK_QUALITY_SCORE, ProcessorFactory
from ..storage.avro_parser import AvroParser
from ..storage.s3_client import S3Client
from .deduplication import DeduplicationStore, RedisDeduplicationStore, SQLiteDeduplicationStore
from .error_recovery import ErrorRecoveryManager

logger = structlog.get_logger()


class ETLConsumer:
    """
    Main consumer for ETL Narrative Engine.

    Consumes messages from RabbitMQ, processes health data files,
    and ensures idempotent processing with robust error handling.
    """

    def __init__(self):
        """Initialize the consumer"""
        self.logger = structlog.get_logger(service=settings.service_name)
        self.settings = settings

        # Initialize components (will be set up in initialize())
        self.dedup_store: DeduplicationStore | None = None
        self.error_manager: ErrorRecoveryManager | None = None
        self.processor_factory: ProcessorFactory | None = None
        self.s3_client: S3Client | None = None
        self.avro_parser: AvroParser | None = None

        # RabbitMQ connection (will be created in start_consuming)
        self._connection = None
        self._channel = None
        self._queue = None
        self._should_stop = False

    async def initialize(self) -> None:
        """
        Initialize all consumer components.

        Sets up:
        - Deduplication store (SQLite or Redis)
        - Error recovery manager
        - Processor factory
        - S3 client
        - Avro parser
        """
        self.logger.info("initializing_etl_consumer")

        # Initialize deduplication store
        if self.settings.deduplication_store.value == "sqlite":
            self.dedup_store = SQLiteDeduplicationStore(
                db_path=self.settings.deduplication_db_path,
                retention_hours=self.settings.deduplication_retention_hours
            )
        else:
            self.dedup_store = RedisDeduplicationStore(
                redis_url=self.settings.deduplication_redis_url,
                retention_hours=self.settings.deduplication_retention_hours
            )

        await self.dedup_store.initialize()

        # Initialize error recovery manager
        self.error_manager = ErrorRecoveryManager(
            max_retries=self.settings.max_retries,
            retry_delays=self.settings.retry_delays
        )

        # Initialize processor factory
        self.processor_factory = ProcessorFactory()
        await self.processor_factory.initialize()

        # Initialize S3 client
        self.s3_client = S3Client(
            endpoint_url=self.settings.s3_endpoint_url,
            access_key=self.settings.s3_access_key,
            secret_key=self.settings.s3_secret_key,
            bucket_name=self.settings.s3_bucket_name,
            region=self.settings.s3_region,
            use_ssl=self.settings.s3_use_ssl
        )

        # Initialize Avro parser
        self.avro_parser = AvroParser()

        self.logger.info("etl_consumer_initialized")

    async def start_consuming(self) -> None:
        """
        Start consuming messages from RabbitMQ.

        Connects to RabbitMQ and starts processing messages from the queue.
        """
        self.logger.info(
            "starting_consumer",
            queue=self.settings.queue_name,
            exchange=self.settings.exchange_name
        )

        # Connect to RabbitMQ with automatic reconnection
        self._connection = await connect_robust(
            self.settings.rabbitmq_url,
            client_properties={
                "connection_name": f"{self.settings.service_name}-consumer"
            }
        )

        # Create channel
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=self.settings.prefetch_count)

        # Declare exchange
        exchange = await self._channel.declare_exchange(
            self.settings.exchange_name,
            type=ExchangeType.TOPIC,
            durable=True
        )

        # Declare main queue
        self._queue = await self._channel.declare_queue(
            self.settings.queue_name,
            durable=True
        )

        # Bind queue to exchange
        await self._queue.bind(
            exchange,
            routing_key=self.settings.routing_key_pattern
        )

        # Declare dead letter queue
        await self._channel.declare_queue(
            self.settings.dead_letter_queue,
            durable=True
        )

        self.logger.info(
            "consumer_started",
            queue=self.settings.queue_name,
            prefetch=self.settings.prefetch_count
        )

        # Start consuming messages
        await self._queue.consume(self._process_message)

        # Keep running until stopped
        while not self._should_stop:
            await asyncio.sleep(1)

    async def _process_message(self, message: IncomingMessage) -> None:
        """
        Process a single message from RabbitMQ.

        Args:
            message: Incoming RabbitMQ message
        """
        async with message.process(ignore_processed=True):
            processing_start = time.time()

            try:
                # Parse message body
                message_data = self._parse_message_body(message)

                # Preserve original routing key for retries
                if message.routing_key:
                    message_data['routing_key'] = message.routing_key

                self.logger.info(
                    "message_received",
                    message_id=message_data.get("message_id"),
                    record_type=message_data.get("record_type"),
                    correlation_id=message_data.get("correlation_id")
                )

                # Check deduplication
                idempotency_key = message_data.get("idempotency_key")
                if await self.dedup_store.is_already_processed(idempotency_key):
                    self.logger.info(
                        "message_already_processed_skipping",
                        idempotency_key=idempotency_key
                    )
                    await message.ack()
                    return

                # Mark as processing started
                await self.dedup_store.mark_processing_started(
                    message_data,
                    idempotency_key
                )

                # Process the message
                await self._handle_message_processing(message_data)

                # Mark as completed
                processing_time = time.time() - processing_start
                # Note: In Module 4, we'll get actual narrative and quality score
                await self.dedup_store.mark_processing_completed(
                    idempotency_key=idempotency_key,
                    processing_time=processing_time,
                    records_processed=message_data.get("record_count", 0),
                    narrative="Processing completed (Module 1 stub)",
                    quality_score=MOCK_QUALITY_SCORE
                )

                # ACK message
                await message.ack()

                self.logger.info(
                    "message_processed_successfully",
                    message_id=message_data.get("message_id"),
                    processing_time=processing_time
                )

            except Exception as e:
                # Classify error
                error_type = self.error_manager.classify_error(e)
                retry_count = message_data.get("retry_count", 0) if 'message_data' in locals() else 0

                self.logger.error(
                    "message_processing_failed",
                    error_type=error_type.value,
                    error_message=str(e),
                    retry_count=retry_count
                )

                # Determine action
                if self.error_manager.should_retry(error_type, retry_count):
                    # Publish to retry with delay
                    delay = self.error_manager.get_retry_delay(retry_count)
                    self.logger.info(
                        "scheduling_retry_with_delay",
                        retry_count=retry_count + 1,
                        delay_seconds=delay
                    )

                    # Update retry count in message data
                    if 'message_data' in locals():
                        message_data['retry_count'] = retry_count + 1
                        try:
                            await self._publish_delayed_retry(message_data, delay)
                            # ACK original message (it's been requeued with delay)
                            await message.ack()
                        except Exception as retry_error:
                            self.logger.error(
                                "failed_to_schedule_delayed_retry",
                                error=str(retry_error),
                                retry_count=retry_count + 1
                            )
                            # If we can't schedule a retry, treat as permanent failure
                            # to avoid infinite retry loops
                            if 'idempotency_key' in message_data:
                                await self.dedup_store.mark_processing_failed(
                                    idempotency_key=message_data["idempotency_key"],
                                    error_message=f"Failed to schedule retry: {str(retry_error)}",
                                    error_type="infrastructure_error"
                                )
                            await message.ack()
                            self.logger.warning(
                                "message_moved_to_dlq_after_retry_scheduling_failure",
                                retry_count=retry_count + 1
                            )

                else:
                    # Mark as failed and move to DLQ
                    if 'message_data' in locals() and 'idempotency_key' in message_data:
                        await self.dedup_store.mark_processing_failed(
                            idempotency_key=message_data["idempotency_key"],
                            error_message=str(e),
                            error_type=error_type.value
                        )

                    # ACK to remove from queue (will go to DLQ)
                    await message.ack()
                    self.logger.warning(
                        "message_moved_to_dlq",
                        error_type=error_type.value
                    )

    async def _handle_message_processing(self, message_data: dict[str, Any]) -> None:
        """
        Handle the main processing logic for a message.

        Args:
            message_data: Parsed message data

        Raises:
            Various exceptions that will be caught by _process_message
        """
        # 1. Download file from S3
        s3_key = message_data.get("key")
        self.logger.info("downloading_file_from_s3", key=s3_key)

        file_content = await self.s3_client.download_file(
            key=s3_key,
            max_size_mb=self.settings.max_file_size_mb
        )

        # 2. Parse Avro records
        record_type = message_data.get("record_type")
        self.logger.info("parsing_avro_records", record_type=record_type)

        records = self.avro_parser.parse_records(
            avro_data=file_content,
            expected_record_type=record_type
        )

        # 3. Get processor for record type
        # Note: get_processor() raises ValueError/RuntimeError if not found, never returns None
        processor = self.processor_factory.get_processor(record_type)

        # 4. Process records with clinical processor
        # Note: validation_result is None for Module 1, Module 2 will provide it
        self.logger.info("processing_with_clinical_processor", record_type=record_type)

        result = await processor.process_with_clinical_insights(
            records=records,
            message_data=message_data,
            validation_result=None  # Module 2 will provide validation
        )

        if not result.success:
            raise Exception(f"Processing failed: {result.error_message}")

        self.logger.info(
            "clinical_processing_completed",
            record_type=record_type,
            records_processed=result.records_processed,
            quality_score=result.quality_score
        )

        # Module 4 will handle training data output

    async def _publish_delayed_retry(
        self, message_data: dict[str, Any], delay_seconds: int
    ) -> None:
        """
        Publish message for delayed retry using RabbitMQ message TTL.

        Creates a temporary queue with TTL that routes back to main queue
        after the delay period.

        Args:
            message_data: Message data to retry
            delay_seconds: Delay in seconds before retry
        """
        try:
            # Delay queue name based on delay duration
            delay_queue_name = f"{self.settings.queue_name}_delay_{delay_seconds}s"

            # Use preserved routing key or construct default
            routing_key = message_data.get(
                'routing_key',
                f"health.processing.{message_data.get('record_type', 'unknown')}"
            )

            # Declare delay queue with message TTL and dead-letter back to main queue
            await self._channel.declare_queue(
                delay_queue_name,
                durable=True,
                arguments={
                    "x-message-ttl": delay_seconds * 1000,  # Convert to milliseconds
                    "x-dead-letter-exchange": self.settings.exchange_name,
                    "x-dead-letter-routing-key": routing_key
                }
            )

            # Publish message to delay queue
            message_body = json.dumps(message_data).encode('utf-8')
            await self._channel.default_exchange.publish(
                Message(body=message_body),
                routing_key=delay_queue_name
            )

            self.logger.info(
                "message_published_to_delay_queue",
                delay_queue=delay_queue_name,
                delay_seconds=delay_seconds,
                retry_count=message_data.get('retry_count', 0)
            )

        except Exception as e:
            self.logger.error(
                "failed_to_publish_delayed_retry",
                error=str(e),
                delay_seconds=delay_seconds
            )
            # Re-raise to let caller handle the failure
            # Caller will move message to DLQ to avoid infinite retry loops
            raise

    def _parse_message_body(self, message: IncomingMessage) -> dict[str, Any]:
        """
        Parse RabbitMQ message body into dictionary.

        Args:
            message: Incoming RabbitMQ message

        Returns:
            Parsed message data

        Raises:
            ValueError: If message body is invalid
        """
        try:
            body = message.body.decode('utf-8')
            data = json.loads(body)
            return data
        except Exception as e:
            self.logger.error("invalid_message_body", error=str(e))
            raise ValueError(f"Invalid message body: {str(e)}") from e

    async def stop(self) -> None:
        """Stop the consumer gracefully"""
        self.logger.info("stopping_consumer")
        self._should_stop = True

        # Close connections
        if self._channel:
            await self._channel.close()

        if self._connection:
            await self._connection.close()

        # Cleanup processors
        if self.processor_factory:
            await self.processor_factory.cleanup()

        # Close dedup store
        if self.dedup_store:
            await self.dedup_store.close()

        self.logger.info("consumer_stopped")
