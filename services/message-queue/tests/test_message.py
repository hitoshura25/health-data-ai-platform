import pytest
import json
from datetime import datetime
import sys
import os

# Add the service directory to the python path to allow imports from core
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.message import HealthDataMessage

@pytest.fixture
def sample_message_data():
    """Provides a sample dictionary to create a HealthDataMessage."""
    return {
        "bucket": "health-data",
        "key": "raw/BloodGlucose/2025/09/23/user123.avro",
        "user_id": "user123",
        "upload_timestamp_utc": "2025-09-23T10:00:00Z",
        "record_type": "BloodGlucose",
        "correlation_id": "corr-id-123",
        "message_id": "msg-id-456",
        "content_hash": "a1b2c3d4e5f6...",
        "file_size_bytes": 1024,
    }

def test_message_creation_with_idempotency_key(sample_message_data):
    """Tests creating a message when an idempotency key is provided."""
    data = {**sample_message_data, "idempotency_key": "manual-key-123"}
    msg = HealthDataMessage(**data)
    assert msg.idempotency_key == "manual-key-123"
    assert msg.record_type == "BloodGlucose"

def test_message_creation_auto_idempotency_key(sample_message_data):
    """Tests that an idempotency key is auto-generated if not provided."""
    data = {**sample_message_data, "idempotency_key": ""}
    msg = HealthDataMessage(**data)
    assert msg.idempotency_key is not None
    assert len(msg.idempotency_key) == 16 # As per implementation

def test_serialization_deserialization(sample_message_data):
    """Tests that a message can be serialized to JSON and back."""
    data = {**sample_message_data, "idempotency_key": "key-1"}
    msg = HealthDataMessage(**data)
    
    json_str = msg.to_json()
    deserialized_msg = HealthDataMessage.from_json(json_str)
    
    assert isinstance(json_str, str)
    assert deserialized_msg == msg

def test_get_routing_key(sample_message_data):
    """Tests the generation of the main routing key."""
    data = {**sample_message_data, "idempotency_key": "key-1"}
    msg = HealthDataMessage(**data)
    assert msg.get_routing_key() == "health.processing.bloodglucose.normal"
    
    msg.processing_priority = "high"
    assert msg.get_routing_key() == "health.processing.bloodglucose.high"

def test_get_retry_routing_key(sample_message_data):
    """Tests the generation of the retry routing key."""
    data = {**sample_message_data, "idempotency_key": "key-1"}
    msg = HealthDataMessage(**data)
    msg.retry_count = 1
    assert msg.get_retry_routing_key() == "health.retry.bloodglucose.attempt_1"

def test_increment_retry(sample_message_data):
    """Tests that the retry count is incremented correctly."""
    data = {**sample_message_data, "idempotency_key": "key-1"}
    msg = HealthDataMessage(**data)
    assert msg.retry_count == 0
    
    msg.increment_retry()
    assert msg.retry_count == 1
    
    msg.increment_retry()
    assert msg.retry_count == 2

def test_calculate_retry_delay(sample_message_data):
    """Tests the calculation of the retry delay based on retry count."""
    data = {**sample_message_data, "idempotency_key": "key-1"}
    msg = HealthDataMessage(**data)
    
    # Note: This test depends on the hardcoded delays in the current implementation
    delays = [30, 300, 900]
    
    msg.retry_count = 1
    assert msg.calculate_retry_delay() == delays[0]
    
    msg.retry_count = 2
    assert msg.calculate_retry_delay() == delays[1]
    
    msg.retry_count = 3
    assert msg.calculate_retry_delay() == delays[2]
    
    # Test that it doesn't go out of bounds
    msg.retry_count = 4
    assert msg.calculate_retry_delay() == delays[-1]
