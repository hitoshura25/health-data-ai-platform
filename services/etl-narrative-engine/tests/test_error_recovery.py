"""
Tests for error recovery and classification.

Tests Module 1 error classification and retry logic.
"""

import pytest
from src.consumer.error_recovery import (
    ErrorRecoveryManager,
    ErrorType,
    NetworkError,
    S3TimeoutError,
    S3ConnectionError,
    S3RateLimitError,
    S3NotFoundError,
    S3AccessDeniedError,
    DataQualityError,
    SchemaError,
    ProcessingTimeoutError
)


@pytest.mark.unit
def test_error_classification_network_errors():
    """Verify network errors are classified correctly"""
    manager = ErrorRecoveryManager()

    # S3 timeout should be network error
    error = S3TimeoutError("Timeout")
    error_type = manager.classify_error(error)
    assert error_type == ErrorType.NETWORK_ERROR
    assert manager.should_retry(error_type, 0) is True

    # S3 connection error should be network error
    error = S3ConnectionError("Connection failed")
    error_type = manager.classify_error(error)
    assert error_type == ErrorType.NETWORK_ERROR
    assert manager.should_retry(error_type, 0) is True


@pytest.mark.unit
def test_error_classification_rate_limit():
    """Verify rate limit errors are retriable"""
    manager = ErrorRecoveryManager()

    error = S3RateLimitError("Rate limit")
    error_type = manager.classify_error(error)
    assert error_type == ErrorType.RATE_LIMIT
    assert manager.should_retry(error_type, 0) is True


@pytest.mark.unit
def test_error_classification_data_quality():
    """Verify data quality errors are not retriable"""
    manager = ErrorRecoveryManager()

    # Data quality error should not be retriable (quarantine instead)
    error = DataQualityError("Low quality")
    error_type = manager.classify_error(error)
    assert error_type == ErrorType.DATA_QUALITY_ERROR
    assert manager.should_retry(error_type, 0) is False
    assert manager.should_quarantine(error_type) is True


@pytest.mark.unit
def test_error_classification_schema_error():
    """Verify schema errors are not retriable"""
    manager = ErrorRecoveryManager()

    error = SchemaError("Invalid schema")
    error_type = manager.classify_error(error)
    assert error_type == ErrorType.SCHEMA_ERROR
    assert manager.should_retry(error_type, 0) is False
    assert manager.should_quarantine(error_type) is True


@pytest.mark.unit
def test_error_classification_not_found():
    """Verify not found errors are not retriable"""
    manager = ErrorRecoveryManager()

    error = S3NotFoundError("Object not found")
    error_type = manager.classify_error(error)
    assert error_type == ErrorType.NOT_FOUND_ERROR
    assert manager.should_retry(error_type, 0) is False


@pytest.mark.unit
def test_error_classification_access_denied():
    """Verify auth errors are not retriable"""
    manager = ErrorRecoveryManager()

    error = S3AccessDeniedError("Access denied")
    error_type = manager.classify_error(error)
    assert error_type == ErrorType.AUTH_ERROR
    assert manager.should_retry(error_type, 0) is False
    assert manager.get_error_action(error_type, 0) == "alert"


@pytest.mark.unit
def test_retry_delay_exponential_backoff():
    """Verify retry delays increase exponentially"""
    manager = ErrorRecoveryManager(
        max_retries=3,
        retry_delays=[30, 300, 900]
    )

    assert manager.get_retry_delay(0) == 30   # 30s
    assert manager.get_retry_delay(1) == 300  # 5m
    assert manager.get_retry_delay(2) == 900  # 15m

    # Should clamp to last delay
    assert manager.get_retry_delay(5) == 900


@pytest.mark.unit
def test_retry_max_attempts():
    """Verify max retry attempts are respected"""
    manager = ErrorRecoveryManager(max_retries=3)

    error_type = ErrorType.NETWORK_ERROR

    # Should retry for attempts 0, 1, 2
    assert manager.should_retry(error_type, 0) is True
    assert manager.should_retry(error_type, 1) is True
    assert manager.should_retry(error_type, 2) is True

    # Should not retry for attempt 3 (exceeded max)
    assert manager.should_retry(error_type, 3) is False


@pytest.mark.unit
def test_error_action_determination():
    """Verify correct action is determined for each error type"""
    manager = ErrorRecoveryManager(max_retries=3)

    # Retriable errors should retry
    assert manager.get_error_action(ErrorType.NETWORK_ERROR, 0) == "retry"
    assert manager.get_error_action(ErrorType.RATE_LIMIT, 0) == "retry"

    # Data quality/schema errors should quarantine
    assert manager.get_error_action(ErrorType.DATA_QUALITY_ERROR, 0) == "quarantine"
    assert manager.get_error_action(ErrorType.SCHEMA_ERROR, 0) == "quarantine"

    # Auth errors should alert
    assert manager.get_error_action(ErrorType.AUTH_ERROR, 0) == "alert"

    # Exceeded retries should go to DLQ
    assert manager.get_error_action(ErrorType.NETWORK_ERROR, 3) == "dead_letter_queue"

    # Processing errors should go to DLQ
    assert manager.get_error_action(ErrorType.PROCESSING_ERROR, 0) == "dead_letter_queue"


@pytest.mark.unit
def test_timeout_error_classification():
    """Verify timeout errors are classified as retriable"""
    manager = ErrorRecoveryManager()

    error = ProcessingTimeoutError("Processing timeout")
    error_type = manager.classify_error(error)
    assert error_type == ErrorType.TIMEOUT_ERROR
    assert manager.should_retry(error_type, 0) is True


@pytest.mark.unit
def test_unclassified_error_default():
    """Verify unknown errors default to processing error"""
    manager = ErrorRecoveryManager()

    # Generic exception should default to processing error
    error = RuntimeError("Unknown error")
    error_type = manager.classify_error(error)
    assert error_type == ErrorType.PROCESSING_ERROR
    assert manager.should_retry(error_type, 0) is False
