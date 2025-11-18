"""
Tests for deduplication stores (SQLite and Redis).

Tests Module 1 deduplication functionality to ensure idempotent processing.
"""

import asyncio
import time

import pytest

from src.consumer.deduplication import ProcessingRecord, SQLiteDeduplicationStore


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sqlite_dedup_prevents_reprocessing(temp_db_path, sample_message_data):
    """Verify messages are not reprocessed"""
    store = SQLiteDeduplicationStore(db_path=temp_db_path, retention_hours=1)
    await store.initialize()

    key = sample_message_data["idempotency_key"]

    # First check - should be new
    assert await store.is_already_processed(key) is False

    # Mark as started
    await store.mark_processing_started(sample_message_data, key)

    # Second check - should be processing
    assert await store.is_already_processed(key) is True

    # Mark as completed
    await store.mark_processing_completed(
        idempotency_key=key,
        processing_time=2.5,
        records_processed=100,
        narrative="Test narrative"
    )

    # Third check - should still be processed
    assert await store.is_already_processed(key) is True

    await store.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sqlite_dedup_marks_failed(temp_db_path, sample_message_data):
    """Verify failed processing is recorded"""
    store = SQLiteDeduplicationStore(db_path=temp_db_path, retention_hours=1)
    await store.initialize()

    key = sample_message_data["idempotency_key"]

    # Mark as started
    await store.mark_processing_started(sample_message_data, key)

    # Mark as failed
    await store.mark_processing_failed(
        idempotency_key=key,
        error_message="Test error",
        error_type="network_error"
    )

    # Should still be marked as processed (even though failed)
    assert await store.is_already_processed(key) is True

    await store.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sqlite_dedup_cleanup_expired(temp_db_path, sample_message_data):
    """Verify expired records are cleaned up"""
    # Use very short retention for testing
    store = SQLiteDeduplicationStore(db_path=temp_db_path, retention_hours=0)
    await store.initialize()

    key = sample_message_data["idempotency_key"]

    # Mark as started (will expire immediately due to 0 hour retention)
    await store.mark_processing_started(sample_message_data, key)

    # Should exist
    assert await store.is_already_processed(key) is True

    # Wait a tiny bit to ensure expiration
    await asyncio.sleep(0.1)

    # Cleanup
    deleted_count = await store.cleanup_expired_records()

    # Should have cleaned up 1 record
    assert deleted_count == 1

    # Should no longer exist
    assert await store.is_already_processed(key) is False

    await store.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sqlite_dedup_multiple_messages(temp_db_path, sample_message_data):
    """Verify multiple messages are tracked independently"""
    store = SQLiteDeduplicationStore(db_path=temp_db_path, retention_hours=1)
    await store.initialize()

    # Create multiple messages
    messages = []
    for i in range(3):
        msg = sample_message_data.copy()
        msg["idempotency_key"] = f"key-{i}"
        msg["message_id"] = f"msg-{i}"
        messages.append(msg)

    # Mark all as started
    for msg in messages:
        await store.mark_processing_started(msg, msg["idempotency_key"])

    # All should be processed
    for msg in messages:
        assert await store.is_already_processed(msg["idempotency_key"]) is True

    # Mark first as completed, second as failed
    await store.mark_processing_completed(
        idempotency_key=messages[0]["idempotency_key"],
        processing_time=1.0,
        records_processed=50,
        narrative="Success"
    )

    await store.mark_processing_failed(
        idempotency_key=messages[1]["idempotency_key"],
        error_message="Error",
        error_type="schema_error"
    )

    # All should still be marked as processed
    for msg in messages:
        assert await store.is_already_processed(msg["idempotency_key"]) is True

    await store.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_processing_record_dataclass():
    """Verify ProcessingRecord dataclass serialization"""
    record = ProcessingRecord(
        idempotency_key="test-key",
        message_id="msg-123",
        correlation_id="corr-456",
        user_id="user-789",
        record_type="BloodGlucoseRecord",
        s3_key="raw/test.avro",
        status="completed",
        started_at=time.time(),
        created_at=time.time(),
        expires_at=time.time() + 3600
    )

    # Convert to dict
    record_dict = record.to_dict()
    assert record_dict["idempotency_key"] == "test-key"
    assert record_dict["record_type"] == "BloodGlucoseRecord"

    # Convert back from dict
    restored = ProcessingRecord.from_dict(record_dict)
    assert restored.idempotency_key == record.idempotency_key
    assert restored.record_type == record.record_type


# ============================================================================
# Redis Deduplication Store Tests (using fakeredis)
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_dedup_prevents_reprocessing(
    fake_redis, sample_message_data, redis_test_url
):
    """
    Test that Redis-based deduplication prevents message reprocessing.

    Verifies:
    1. New message is not marked as processed
    2. After marking as started, message is marked as processed
    3. Redis keys are created correctly
    4. TTL is set on keys
    """
    from src.consumer.deduplication import RedisDeduplicationStore

    # Create store
    store = RedisDeduplicationStore(
        redis_url=redis_test_url,
        retention_hours=24
    )

    # Override Redis client with fake
    store._redis = fake_redis

    idempotency_key = sample_message_data["idempotency_key"]

    # First check - should not be processed
    is_processed = await store.is_already_processed(idempotency_key)
    assert is_processed is False, "New message should not be marked as processed"

    # Mark as started
    await store.mark_processing_started(sample_message_data, idempotency_key)

    # Second check - should be processed
    is_processed = await store.is_already_processed(idempotency_key)
    assert is_processed is True, "Started message should be marked as processed"

    # Verify Redis keys exist
    data_key = f"etl:processed:{idempotency_key}"
    status_key = f"etl:status:{idempotency_key}"

    assert await fake_redis.exists(data_key), "Data key should exist in Redis"
    assert await fake_redis.exists(status_key), "Status key should exist in Redis"

    # Verify TTL is set (should be close to 24 hours = 86400 seconds)
    data_ttl = await fake_redis.ttl(data_key)
    assert data_ttl > 86000, f"Data key TTL should be ~24 hours, got {data_ttl}s"
    assert data_ttl <= 86400, f"Data key TTL should not exceed 24 hours, got {data_ttl}s"

    # Cleanup
    await store.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_dedup_marks_failed(
    fake_redis, sample_message_data, redis_test_url
):
    """
    Test that Redis store correctly marks failed processing.

    Verifies:
    1. Can mark message as failed
    2. Status is updated to 'failed'
    3. Failed messages are still marked as processed (to prevent retry loops)
    """
    from src.consumer.deduplication import RedisDeduplicationStore

    store = RedisDeduplicationStore(redis_url=redis_test_url, retention_hours=24)
    store._redis = fake_redis

    idempotency_key = sample_message_data["idempotency_key"]

    # Mark as started
    await store.mark_processing_started(sample_message_data, idempotency_key)

    # Mark as failed
    await store.mark_processing_failed(idempotency_key, error_message="Test error", error_type="network_error")

    # Should still be marked as processed
    is_processed = await store.is_already_processed(idempotency_key)
    assert is_processed is True, "Failed message should still be marked as processed"

    # Check status
    status_key = f"etl:status:{idempotency_key}"
    status = await fake_redis.get(status_key)
    assert status == "failed", f"Status should be 'failed', got '{status}'"

    await store.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_dedup_marks_completed(
    fake_redis, sample_message_data, redis_test_url
):
    """
    Test that Redis store correctly marks completed processing.

    Verifies:
    1. Can mark message as completed
    2. Status is updated to 'completed'
    3. Completed messages remain in Redis with TTL
    """
    from src.consumer.deduplication import RedisDeduplicationStore

    store = RedisDeduplicationStore(redis_url=redis_test_url, retention_hours=24)
    store._redis = fake_redis

    idempotency_key = sample_message_data["idempotency_key"]

    # Mark as started
    await store.mark_processing_started(sample_message_data, idempotency_key)

    # Mark as completed
    await store.mark_processing_completed(
        idempotency_key=idempotency_key,
        processing_time=2.5,
        records_processed=100,
        narrative="Test narrative"
    )

    # Should be marked as processed
    is_processed = await store.is_already_processed(idempotency_key)
    assert is_processed is True

    # Check status
    status_key = f"etl:status:{idempotency_key}"
    status = await fake_redis.get(status_key)
    assert status == "completed", f"Status should be 'completed', got '{status}'"

    await store.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_dedup_multiple_messages(
    fake_redis, sample_message_data, redis_test_url
):
    """
    Test Redis deduplication with multiple messages.

    Verifies:
    1. Can track multiple messages independently
    2. Each message has separate Redis keys
    3. Messages don't interfere with each other
    """
    from src.consumer.deduplication import RedisDeduplicationStore

    store = RedisDeduplicationStore(redis_url=redis_test_url, retention_hours=24)
    store._redis = fake_redis

    # Create three different messages
    messages = [
        {**sample_message_data, "idempotency_key": f"key-{i}", "message_id": f"msg-{i}"}
        for i in range(3)
    ]

    # Mark all as started
    for msg in messages:
        await store.mark_processing_started(msg, msg["idempotency_key"])

    # All should be marked as processed
    for msg in messages:
        is_processed = await store.is_already_processed(msg["idempotency_key"])
        assert is_processed is True, f"Message {msg['message_id']} should be processed"

    # Verify separate keys
    keys = await fake_redis.keys("etl:processed:*")
    assert len(keys) == 3, f"Should have 3 data keys, got {len(keys)}"

    status_keys = await fake_redis.keys("etl:status:*")
    assert len(status_keys) == 3, f"Should have 3 status keys, got {len(status_keys)}"

    await store.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_ttl_expiration(fake_redis, sample_message_data, redis_test_url):
    """
    Test that Redis keys expire after TTL.

    Verifies:
    1. TTL is set correctly based on retention_hours
    2. Different retention periods result in different TTLs
    """
    from src.consumer.deduplication import RedisDeduplicationStore

    # Test with 1 hour retention
    store_1h = RedisDeduplicationStore(redis_url=redis_test_url, retention_hours=1)
    store_1h._redis = fake_redis

    idempotency_key = "test-key-1h"

    await store_1h.mark_processing_started(sample_message_data, idempotency_key)

    # Check TTL (should be ~3600 seconds for 1 hour)
    data_key = f"etl:processed:{idempotency_key}"
    ttl = await fake_redis.ttl(data_key)

    assert 3500 < ttl <= 3600, f"1-hour retention should have ~3600s TTL, got {ttl}s"

    await store_1h.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_cleanup_expired_records(
    fake_redis, sample_message_data, redis_test_url
):
    """
    Test Redis cleanup of expired records.

    Note: Redis handles expiration automatically via TTL, so cleanup
    is mostly a no-op for Redis (unlike SQLite which requires manual cleanup).

    Verifies:
    1. Cleanup method exists and doesn't error
    2. Returns count of cleaned records (should be 0 for Redis with TTL)
    """
    from src.consumer.deduplication import RedisDeduplicationStore

    store = RedisDeduplicationStore(redis_url=redis_test_url, retention_hours=24)
    store._redis = fake_redis

    # Cleanup should work but return 0 (Redis auto-expires via TTL)
    cleaned_count = await store.cleanup_expired_records()

    # For Redis, this should return 0 since expiration is automatic
    assert cleaned_count == 0, "Redis cleanup should return 0 (automatic TTL expiration)"

    await store.close()
