import pytest
from datetime import datetime, timezone
import os
import sys
from unittest.mock import patch

# Add the service directory to the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Use fakeredis for mocking
import fakeredis.aioredis

from core.deduplication import RedisDeduplicationStore
from core.message import HealthDataMessage

import pytest_asyncio

@pytest_asyncio.fixture
async def store(mocker):
    """Fixture to create a Redis-based deduplication store with a mock Redis pool."""
    # Configure the fake redis to decode responses to avoid `b'...'` issues
    fake_redis_instance = fakeredis.aioredis.FakeRedis(decode_responses=True)
    
    # Patch the redis connection pool to use the fake one
    mocker.patch('redis.asyncio.ConnectionPool.from_url', return_value=fake_redis_instance.connection_pool)
    
    store = RedisDeduplicationStore(retention_hours=1)
    await store.initialize()
    yield store
    await store.close()

@pytest.fixture
def sample_message():
    """Provides a sample HealthDataMessage for tests."""
    return HealthDataMessage(
        bucket="test-bucket",
        key="test-key",
        user_id="user1",
        upload_timestamp_utc=datetime.now(timezone.utc).isoformat(),
        record_type="TestRecord",
        correlation_id="corr1",
        message_id="msg1",
        content_hash="hash1",
        idempotency_key="idem1",
        file_size_bytes=100
    )

@pytest.mark.asyncio
async def test_initialization(store):
    """Tests that the store initializes correctly with a Redis pool."""
    assert store.redis_pool is not None

@pytest.mark.asyncio
async def test_mark_started_and_is_processed(store, sample_message):
    """Tests marking a message as started and then checking it."""
    assert not await store.is_already_processed(sample_message.idempotency_key)
    
    await store.mark_processing_started(sample_message)
    
    assert await store.is_already_processed(sample_message.idempotency_key)
    status = await store._get_status_for_testing(sample_message.idempotency_key)
    assert status == 'processing'

@pytest.mark.asyncio
async def test_mark_completed(store, sample_message):
    """Tests marking a message as completed and checking its status."""
    await store.mark_processing_started(sample_message)
    await store.mark_processing_completed(sample_message.idempotency_key, 0.5)
    
    status = await store._get_status_for_testing(sample_message.idempotency_key)
    assert status == 'completed'

@pytest.mark.asyncio
async def test_mark_failed(store, sample_message):
    """Tests marking a message as failed."""
    await store.mark_processing_started(sample_message)
    await store.mark_processing_failed(sample_message.idempotency_key, "test error")

    status = await store._get_status_for_testing(sample_message.idempotency_key)
    assert status == 'failed'

@pytest.mark.asyncio
async def test_retention_ttl(store, sample_message):
    """Tests that keys are set with the correct TTL."""
    expected_ttl = 3600  # 1 hour in seconds

    await store.mark_processing_completed(sample_message.idempotency_key, 0.1)
    
    # Get a client from the pool to check the TTL
    client = fakeredis.aioredis.FakeRedis(connection_pool=store.redis_pool)
    ttl = await client.ttl(sample_message.idempotency_key)
    
    # fakeredis might not be exact, so check if it's close
    assert expected_ttl - 5 <= ttl <= expected_ttl

@pytest.mark.asyncio
async def test_cleanup_is_noop(store, mocker):
    """Tests that the cleanup function does nothing for Redis."""
    # Patch the logger instance directly in the module where it is used
    log_mock = mocker.patch('core.deduplication.logger')
    
    await store.cleanup_old_records()
    
    # Check that the specific debug message is logged
    log_mock.debug.assert_called_once_with("Cleanup is handled automatically by Redis TTL.")
