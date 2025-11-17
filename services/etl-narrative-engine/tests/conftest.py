"""
Pytest fixtures for ETL Narrative Engine tests.

Provides common test fixtures for unit and integration tests.
"""

import pytest
import tempfile
from pathlib import Path


@pytest.fixture
def temp_db_path():
    """Provide temporary SQLite database path for testing"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    yield db_path

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def sample_message_data():
    """Sample message data for testing"""
    return {
        "message_id": "test-message-123",
        "correlation_id": "test-correlation-456",
        "user_id": "test-user-789",
        "bucket": "health-data",
        "key": "raw/BloodGlucoseRecord/2025/11/15/user123_1731628800_abc123.avro",
        "record_type": "BloodGlucoseRecord",
        "upload_timestamp_utc": "2025-11-15T12:00:00Z",
        "content_hash": "sha256-test-hash",
        "file_size_bytes": 38664,
        "record_count": 287,
        "idempotency_key": "test-idempotency-key-123",
        "priority": "normal",
        "retry_count": 0
    }


@pytest.fixture
def sample_avro_records():
    """Sample Avro records for testing"""
    return [
        {
            "level": {
                "inMilligramsPerDeciliter": 120.5
            },
            "time": {
                "epochMillis": 1700000000000
            },
            "specimenSource": "INTERSTITIAL_FLUID",
            "metadata": {
                "id": "record-1",
                "dataOrigin": {
                    "packageName": "com.example.app"
                }
            }
        },
        {
            "level": {
                "inMilligramsPerDeciliter": 135.2
            },
            "time": {
                "epochMillis": 1700003600000
            },
            "specimenSource": "INTERSTITIAL_FLUID",
            "metadata": {
                "id": "record-2",
                "dataOrigin": {
                    "packageName": "com.example.app"
                }
            }
        }
    ]
