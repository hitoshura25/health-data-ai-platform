import pytest
import pytest_asyncio
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

@pytest_asyncio.fixture(scope="session")
async def docker_services():
    """Ensures Redis and RabbitMQ services are running for integration tests."""
    # Use root docker-compose.yml which includes all services via include directive
    compose_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'docker-compose.yml'))
    # Use root .env file which has all infrastructure variables
    env_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env'))

    # Ensure the .env file exists before starting
    if not os.path.exists(env_file):
        pytest.fail(".env file not found. Please run setup-all-services.sh from project root first.")

    # Check if services are already running
    result = subprocess.run(
        ["docker", "compose", "-f", compose_file, "--env-file", env_file, "ps", "--services", "--filter", "status=running"],
        capture_output=True,
        text=True
    )
    running_services = set(result.stdout.strip().split('\n')) if result.stdout.strip() else set()
    services_were_running = 'rabbitmq' in running_services and 'redis' in running_services

    try:
        # Start services if not already running (or ensure they're up and healthy)
        subprocess.run(
            ["docker", "compose", "-f", compose_file, "--env-file", env_file, "up", "-d", "--wait", "rabbitmq", "redis"],
            check=True
        )
        yield
    finally:
        # Only stop services if we started them (don't interfere with user's running services)
        if not services_were_running:
            subprocess.run(
                ["docker", "compose", "-f", compose_file, "--env-file", env_file, "stop", "rabbitmq", "redis"],
                check=True,
                capture_output=True
            )

@pytest_asyncio.fixture()
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

    consumer = MyConsumer(queue_name=queue_name, stop_after_n_messages=1)
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

@pytest.mark.timeout(60)
@pytest.mark.asyncio
async def test_deduplication_integration(test_env):
    """Tests that a message published twice is processed only once."""

    publisher, consumer, queue_name = test_env

    message = HealthDataMessage(
        bucket="test-bucket",
        key="test-key",
        user_id="user-int-test",
        upload_timestamp_utc=datetime.now(timezone.utc).isoformat(),
        record_type="TestRecord",
        correlation_id=f"corr-{uuid.uuid4()}",
        message_id=f"msg-{uuid.uuid4()}",
        content_hash="integration_test_hash",
        idempotency_key=f"test_idem_key_{uuid.uuid4()}",
        file_size_bytes=123
    )

    await publisher.publish_health_data_message(message)
    await publisher.publish_health_data_message(message)

    await consumer.start_consuming()

    assert len(consumer.processed_messages) == 1
    assert consumer.processed_messages[0].idempotency_key == message.idempotency_key
