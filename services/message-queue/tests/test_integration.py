import time
import pytest
import pytest_asyncio
import asyncio
import uuid
from datetime import datetime, timezone
import subprocess

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import aio_pika
from config.settings import settings
from core.message import HealthDataMessage
from publisher.health_data_publisher import HealthDataPublisher
from tests.helpers import MyConsumer

@pytest.fixture(scope="session")
def docker_services():
    """Starts and stops the redis and rabbitmq services for the integration tests."""
    docker_compose_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'deployment', 'docker-compose.yml'))
    try:
        subprocess.run(["docker-compose", "-f", docker_compose_path, "up", "-d", "rabbitmq", "redis"], check=True)
        time.sleep(10)
        yield
    finally:
        subprocess.run(["docker-compose", "-f", docker_compose_path, "down"])

@pytest_asyncio.fixture
async def test_env(docker_services):
    """Sets up a complete test environment for integration tests."""
    queue_name = f"test_queue_{uuid.uuid4()}"

    # Declare the exchange using a temporary connection
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    async with connection.channel() as channel:
        await channel.declare_exchange(
            name=settings.main_exchange,
            type=aio_pika.ExchangeType.TOPIC,
            durable=True
        )
    await connection.close()

    publisher = HealthDataPublisher()
    await publisher.initialize()

    consumer = MyConsumer(queue_name=queue_name)
    await consumer.initialize()

    consumer.processed_messages = []

    queue = await consumer.channel.declare_queue(queue_name, auto_delete=True)
    await queue.bind(
        exchange="health_data_exchange",
        routing_key="health.processing.testrecord.normal"
    )

    yield publisher, consumer, queue_name

    await publisher.close()
    await consumer.stop()

@pytest.mark.asyncio
async def test_deduplication_integration(test_env):
    """Tests that a message published twice is processed only once."""
    publisher, consumer, _ = test_env

    message = HealthDataMessage(
        bucket="test-bucket",
        key="test-key",
        user_id="user-int-test",
        upload_timestamp_utc=datetime.now(timezone.utc).isoformat(),
        record_type="TestRecord",
        correlation_id=f"corr-{uuid.uuid4()}",
        message_id=f"msg-{uuid.uuid4()}",
        content_hash="integration_test_hash",
        idempotency_key="integration_test_idem_key",
        file_size_bytes=123
    )

    await publisher.publish_health_data_message(message)
    await publisher.publish_health_data_message(message)

    consume_task = asyncio.create_task(consumer.start_consuming())
    await asyncio.sleep(2)

    await consumer.stop()
    consume_task.cancel()
    try:
        await consume_task
    except asyncio.CancelledError:
        pass

    assert len(consumer.processed_messages) == 1
    assert consumer.processed_messages[0].idempotency_key == "integration_test_idem_key"
