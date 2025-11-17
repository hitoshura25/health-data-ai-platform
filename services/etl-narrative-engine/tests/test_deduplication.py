"""
Tests for deduplication stores (SQLite and Redis).

Tests Module 1 deduplication functionality to ensure idempotent processing.
"""

import pytest
import asyncio
import time
from src.consumer.deduplication import (
    SQLiteDeduplicationStore,
    ProcessingRecord
)


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


# Note: Redis tests would require a Redis instance
# For Module 1, we can use fakeredis or mark as integration tests
# Integration tests will be added later when Docker setup is complete
