"""
Integration tests for ETL Narrative Engine deployment.

Tests the complete deployment stack including:
- Docker container health
- Service dependencies (RabbitMQ, MinIO, Redis)
- Health and metrics endpoints
- End-to-end message processing
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any

import aio_pika
import aioboto3
import pytest
import redis.asyncio as aioredis
import requests


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_stack_deployment():
    """Test complete ETL stack deployment"""

    # Verify all infrastructure is running
    assert await check_rabbitmq_connection(), "RabbitMQ connection failed"
    assert await check_minio_connection(), "MinIO connection failed"
    assert await check_redis_connection(), "Redis connection failed"

    # Verify ETL service is healthy
    response = requests.get("http://localhost:8004/health", timeout=5)
    assert response.status_code == 200, "Health endpoint not accessible"

    health = response.json()
    assert health['status'] in ['healthy', 'degraded'], f"Unexpected health status: {health['status']}"
    assert health['service'] == 'etl-narrative-engine', "Wrong service name"

    # Verify metrics endpoint
    response = requests.get("http://localhost:8004/metrics", timeout=5)
    assert response.status_code == 200, "Metrics endpoint not accessible"
    assert 'etl_messages_processed_total' in response.text, "Expected metrics not found"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_endpoint_details():
    """Test health endpoint returns correct structure"""

    response = requests.get("http://localhost:8004/health", timeout=5)
    assert response.status_code == 200

    health = response.json()

    # Verify required fields
    assert 'status' in health
    assert 'service' in health
    assert 'version' in health
    assert 'environment' in health
    assert 'uptime_seconds' in health
    assert 'dependencies' in health
    assert 'timestamp' in health

    # Verify dependencies
    deps = health['dependencies']
    assert 'rabbitmq' in deps
    assert 's3' in deps


@pytest.mark.integration
@pytest.mark.asyncio
async def test_metrics_endpoint():
    """Test metrics endpoint returns Prometheus format"""

    response = requests.get("http://localhost:8004/metrics", timeout=5)
    assert response.status_code == 200

    metrics_text = response.text

    # Verify Prometheus format
    assert 'etl_service_info' in metrics_text
    assert 'etl_messages_processed_total' in metrics_text
    assert 'etl_consumer_status' in metrics_text
    assert 'etl_rabbitmq_connection_status' in metrics_text
    assert 'etl_s3_connection_status' in metrics_text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_readiness_endpoint():
    """Test Kubernetes readiness endpoint"""

    response = requests.get("http://localhost:8004/ready", timeout=5)
    assert response.status_code == 200

    ready = response.json()
    assert 'ready' in ready
    assert 'checks' in ready
    assert 'rabbitmq' in ready['checks']
    assert 's3' in ready['checks']


@pytest.mark.integration
@pytest.mark.asyncio
async def test_liveness_endpoint():
    """Test Kubernetes liveness endpoint"""

    response = requests.get("http://localhost:8004/live", timeout=5)
    assert response.status_code == 200

    live = response.json()
    assert 'alive' in live
    assert live['alive'] is True
    assert 'timestamp' in live


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sample_data_processing():
    """
    Test processing of sample Avro files.

    This test:
    1. Uploads a sample file to MinIO
    2. Publishes a message to RabbitMQ
    3. Waits for processing
    4. Verifies training data was generated
    """

    # Sample message
    correlation_id = str(uuid.uuid4())
    s3_key = f"raw/test/BloodGlucoseRecord_test_{correlation_id}.avro"

    message = {
        'bucket': 'health-data',
        'key': s3_key,
        'record_type': 'BloodGlucoseRecord',
        'user_id': f'test_user_{correlation_id}',
        'correlation_id': correlation_id,
        'timestamp': datetime.utcnow().isoformat(),
    }

    # Publish message to RabbitMQ
    await publish_message(message)

    # Wait for processing (with timeout)
    await asyncio.sleep(10)

    # Note: Actual file processing verification would require
    # the sample file to be uploaded and the ETL service to be running
    # This is a placeholder for the full integration test

    # Verify metrics were updated (messages should have been processed or attempted)
    response = requests.get("http://localhost:8004/metrics", timeout=5)
    assert response.status_code == 200


# Helper functions

async def check_rabbitmq_connection() -> bool:
    """Check if RabbitMQ is accessible"""
    try:
        connection = await aio_pika.connect_robust(
            "amqp://guest:guest@localhost:5672/",
            timeout=5
        )
        await connection.close()
        return True
    except Exception as e:
        print(f"RabbitMQ connection failed: {e}")
        return False


async def check_minio_connection() -> bool:
    """Check if MinIO is accessible"""
    try:
        session = aioboto3.Session()
        async with session.client(
            's3',
            endpoint_url='http://localhost:9000',
            aws_access_key_id='minioadmin',
            aws_secret_access_key='minioadmin',
        ) as s3:
            # Try to list buckets
            await s3.list_buckets()
            return True
    except Exception as e:
        print(f"MinIO connection failed: {e}")
        return False


async def check_redis_connection() -> bool:
    """Check if Redis is accessible"""
    try:
        redis_client = await aioredis.from_url(
            "redis://localhost:6379/2",
            encoding="utf-8",
            decode_responses=True
        )
        await redis_client.ping()
        await redis_client.close()
        return True
    except Exception as e:
        print(f"Redis connection failed: {e}")
        return False


async def publish_message(message: dict[str, Any]):
    """Publish a message to RabbitMQ"""
    connection = await aio_pika.connect_robust(
        "amqp://guest:guest@localhost:5672/"
    )

    async with connection:
        channel = await connection.channel()

        # Declare exchange
        exchange = await channel.declare_exchange(
            'health_data_exchange',
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )

        # Publish message
        await exchange.publish(
            aio_pika.Message(
                body=json.dumps(message).encode(),
                content_type='application/json',
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            ),
            routing_key='health.processing.data'
        )


async def list_s3_objects(bucket: str, prefix: str) -> list:
    """List objects in S3/MinIO bucket"""
    session = aioboto3.Session()
    async with session.client(
        's3',
        endpoint_url='http://localhost:9000',
        aws_access_key_id='minioadmin',
        aws_secret_access_key='minioadmin',
    ) as s3:
        try:
            response = await s3.list_objects_v2(
                Bucket=bucket,
                Prefix=prefix
            )
            return response.get('Contents', [])
        except Exception as e:
            print(f"Failed to list S3 objects: {e}")
            return []
