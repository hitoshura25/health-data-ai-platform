"""
Error classification and retry logic for ETL Narrative Engine.

Classifies errors into retriable and non-retriable categories and determines
appropriate retry strategies with exponential backoff.
"""

from enum import Enum

import structlog

logger = structlog.get_logger()


class ErrorType(Enum):
    """Classification of error types"""

    # Retriable errors (transient issues)
    NETWORK_ERROR = "network_error"              # S3 timeout, connection lost
    TEMPORARY_ERROR = "temporary_error"          # Transient issues
    RATE_LIMIT = "rate_limit"                   # S3 rate limiting
    RESOURCE_ERROR = "resource_error"            # Memory, CPU exhaustion

    # Non-retriable errors (permanent failures)
    DATA_QUALITY_ERROR = "data_quality"          # Low quality (quarantine)
    SCHEMA_ERROR = "schema_error"                # Invalid Avro schema
    PROCESSING_ERROR = "processing_error"        # Processor logic error
    NOT_FOUND_ERROR = "not_found"               # S3 object not found
    AUTH_ERROR = "auth_error"                   # S3 access denied
    TIMEOUT_ERROR = "timeout_error"             # Processing timeout
    VALIDATION_ERROR = "validation_error"        # Data validation failed


# Custom exception classes for error classification
class NetworkError(Exception):
    """Network-related errors (S3 connection, timeout)"""
    pass


class S3TimeoutError(NetworkError):
    """S3 operation timeout"""
    pass


class S3ConnectionError(NetworkError):
    """S3 connection failed"""
    pass


class S3RateLimitError(Exception):
    """S3 rate limit exceeded"""
    pass


class S3NotFoundError(Exception):
    """S3 object not found"""
    pass


class S3AccessDeniedError(Exception):
    """S3 access denied"""
    pass


class DataQualityError(Exception):
    """Data quality below threshold"""
    pass


class SchemaError(Exception):
    """Invalid Avro schema"""
    pass


class ProcessingTimeoutError(Exception):
    """Processing exceeded timeout"""
    pass


class ValidationError(Exception):
    """Data validation failed"""
    pass


class ErrorRecoveryManager:
    """
    Manages error classification and retry strategies.

    This class determines if errors should be retried and calculates
    appropriate delay intervals using exponential backoff.
    """

    def __init__(self, max_retries: int = 3, retry_delays: list[int] | None = None):
        """
        Initialize error recovery manager.

        Args:
            max_retries: Maximum number of retry attempts (default: 3)
            retry_delays: List of delays in seconds [30s, 5m, 15m]
        """
        self.max_retries = max_retries
        self.retry_delays = retry_delays or [30, 300, 900]  # 30s, 5m, 15m
        self.logger = structlog.get_logger()

    def classify_error(self, exception: Exception) -> ErrorType:
        """
        Classify exception into error type.

        Args:
            exception: The exception to classify

        Returns:
            ErrorType enum value
        """
        # Network errors (retriable)
        if isinstance(exception, (S3TimeoutError, S3ConnectionError, NetworkError)):
            return ErrorType.NETWORK_ERROR

        # Rate limiting (retriable)
        elif isinstance(exception, S3RateLimitError):
            return ErrorType.RATE_LIMIT

        # Resource errors (retriable)
        elif isinstance(exception, MemoryError):
            return ErrorType.RESOURCE_ERROR
        elif isinstance(exception, ProcessingTimeoutError):
            return ErrorType.TIMEOUT_ERROR

        # Data quality/validation errors (non-retriable - quarantine)
        elif isinstance(exception, DataQualityError):
            return ErrorType.DATA_QUALITY_ERROR
        elif isinstance(exception, ValidationError):
            return ErrorType.VALIDATION_ERROR

        # Schema errors (non-retriable - quarantine)
        elif isinstance(exception, SchemaError):
            return ErrorType.SCHEMA_ERROR

        # Not found errors (non-retriable - likely upstream issue)
        elif isinstance(exception, S3NotFoundError):
            return ErrorType.NOT_FOUND_ERROR

        # Auth errors (non-retriable - critical alert)
        elif isinstance(exception, S3AccessDeniedError):
            return ErrorType.AUTH_ERROR

        # Check exception message for hints
        elif "timeout" in str(exception).lower() or "connection" in str(exception).lower():
            return ErrorType.NETWORK_ERROR
        elif "rate limit" in str(exception).lower():
            return ErrorType.RATE_LIMIT

        # Default to processing error (non-retriable)
        else:
            self.logger.warning(
                "unclassified_error_defaulting_to_processing_error",
                exception_type=type(exception).__name__,
                exception_message=str(exception)
            )
            return ErrorType.PROCESSING_ERROR

    def should_retry(self, error_type: ErrorType, retry_count: int) -> bool:
        """
        Determine if error should be retried.

        Args:
            error_type: The classified error type
            retry_count: Current retry attempt count

        Returns:
            True if should retry, False otherwise
        """
        # Check if error type is retriable
        retriable_errors = {
            ErrorType.NETWORK_ERROR,
            ErrorType.TEMPORARY_ERROR,
            ErrorType.RATE_LIMIT,
            ErrorType.RESOURCE_ERROR,
            ErrorType.TIMEOUT_ERROR
        }

        is_retriable = error_type in retriable_errors
        within_retry_limit = retry_count < self.max_retries

        should_retry = is_retriable and within_retry_limit

        self.logger.info(
            "retry_decision",
            error_type=error_type.value,
            retry_count=retry_count,
            max_retries=self.max_retries,
            should_retry=should_retry
        )

        return should_retry

    def get_retry_delay(self, retry_count: int) -> int:
        """
        Get delay in seconds for retry with exponential backoff.

        Args:
            retry_count: Current retry attempt (0-indexed)

        Returns:
            Delay in seconds
        """
        # Use configured delays with clamping
        index = min(retry_count, len(self.retry_delays) - 1)
        delay = self.retry_delays[index]

        self.logger.info(
            "retry_delay_calculated",
            retry_count=retry_count,
            delay_seconds=delay
        )

        return delay

    def should_quarantine(self, error_type: ErrorType) -> bool:
        """
        Determine if data should be moved to quarantine.

        Args:
            error_type: The classified error type

        Returns:
            True if should quarantine, False otherwise
        """
        quarantine_errors = {
            ErrorType.DATA_QUALITY_ERROR,
            ErrorType.SCHEMA_ERROR,
            ErrorType.VALIDATION_ERROR
        }

        return error_type in quarantine_errors

    def get_error_action(self, error_type: ErrorType, retry_count: int) -> str:
        """
        Get recommended action for error.

        Args:
            error_type: The classified error type
            retry_count: Current retry attempt count

        Returns:
            Action string: 'retry', 'quarantine', 'dead_letter_queue', 'alert'
        """
        if self.should_quarantine(error_type):
            return "quarantine"

        elif self.should_retry(error_type, retry_count):
            return "retry"

        elif error_type == ErrorType.AUTH_ERROR:
            return "alert"  # Critical: auth issues need immediate attention

        else:
            return "dead_letter_queue"
