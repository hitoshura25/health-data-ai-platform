"""
Type definitions for processing message formats.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict
from enum import Enum


# Processing Enums
class HealthRecordType(Enum):
    """Type of health record for processor routing."""
    BLOOD_GLUCOSE = "BLOOD_GLUCOSE"
    HEART_RATE = "HEART_RATE"
    SLEEP_SESSION = "SLEEP_SESSION"
    STEPS = "STEPS"
    ACTIVE_CALORIES = "ACTIVE_CALORIES"
    HEART_RATE_VARIABILITY = "HEART_RATE_VARIABILITY"
    UNKNOWN = "UNKNOWN"


class ProcessingPriority(Enum):
    """Processing priority level."""
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class ProcessingStatus(Enum):
    """Status of the ETL processing operation."""
    SUCCESS = "SUCCESS"
    FAILED_VALIDATION = "FAILED_VALIDATION"
    FAILED_PROCESSING = "FAILED_PROCESSING"
    FAILED_STORAGE = "FAILED_STORAGE"
    QUARANTINED = "QUARANTINED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"


class ErrorType(Enum):
    """Category of error encountered."""
    VALIDATION_ERROR = "VALIDATION_ERROR"
    PARSING_ERROR = "PARSING_ERROR"
    STORAGE_ERROR = "STORAGE_ERROR"
    CLINICAL_VALIDATION_ERROR = "CLINICAL_VALIDATION_ERROR"
    SYSTEM_ERROR = "SYSTEM_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"


class ServiceComponent(Enum):
    """Component where the error occurred."""
    HEALTH_API_SERVICE = "HEALTH_API_SERVICE"
    MESSAGE_QUEUE = "MESSAGE_QUEUE"
    DATA_LAKE = "DATA_LAKE"
    ETL_NARRATIVE_ENGINE = "ETL_NARRATIVE_ENGINE"
    AI_QUERY_INTERFACE = "AI_QUERY_INTERFACE"


class ErrorSeverity(Enum):
    """Severity level of the error."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# Data Classes
@dataclass
class StorageLocation:
    """Location of stored health data file."""

    bucket: str
    """S3-compatible storage bucket name"""

    key: str
    """Object key/path within the bucket"""

    region: Optional[str] = None
    """Storage region (for S3 compatibility)"""


@dataclass
class UploadMetadata:
    """Metadata about the file upload process."""

    upload_timestamp: int
    """When the file was uploaded (epoch milliseconds)"""

    file_size: int
    """Size of the uploaded file in bytes"""

    content_hash: str
    """SHA256 hash of file content for integrity verification"""

    source_device: Optional[str] = None
    """Device that generated the health data"""

    sync_app_version: Optional[str] = None
    """Version of Android sync app that uploaded the data"""


@dataclass
class ProcessingMetadata:
    """Metadata for message processing and retry logic."""

    routing_key: str
    """RabbitMQ routing key for intelligent message routing"""

    priority: ProcessingPriority = ProcessingPriority.NORMAL
    """Processing priority level"""

    retry_count: int = 0
    """Number of processing retry attempts"""

    max_retries: int = 3
    """Maximum number of retry attempts"""

    ttl_seconds: Optional[int] = None
    """Message time-to-live in seconds"""


@dataclass
class TimeRange:
    """Time range covered by processed data."""

    start_time_epoch_millis: int
    """Earliest timestamp in processed data"""

    end_time_epoch_millis: int
    """Latest timestamp in processed data"""

    def get_duration_hours(self) -> float:
        """Get duration in hours."""
        duration_ms = self.end_time_epoch_millis - self.start_time_epoch_millis
        return duration_ms / (1000 * 60 * 60)


@dataclass
class ProcessedHealthData:
    """Successfully processed health data output."""

    clinical_narrative: str
    """Human-readable clinical narrative describing the health data"""

    structured_insights: Dict[str, str]
    """Key-value pairs of structured clinical insights"""

    training_data_location: StorageLocation
    """Location where training data is stored"""

    quality_score: float
    """Data quality score (0.0 - 1.0)"""

    record_count: int
    """Number of individual health records processed"""

    time_range: TimeRange
    """Time range covered by the processed data"""


@dataclass
class ProcessingError:
    """Individual processing error details."""

    error_type: ErrorType
    """Category of error encountered"""

    error_message: str
    """Human-readable error description"""

    recoverable: bool
    """Whether this error is potentially recoverable with retry"""

    error_code: Optional[str] = None
    """Machine-readable error code"""


@dataclass
class HealthDataProcessingMessage:
    """Message format for health data processing queue with intelligent routing and deduplication."""

    message_id: str
    """Unique message identifier for deduplication"""

    correlation_id: str
    """Correlation ID for tracking requests across services"""

    user_id: str
    """User identifier for data ownership and routing"""

    record_type: HealthRecordType
    """Type of health record contained in this message"""

    storage_location: StorageLocation
    """Location where the raw health data file is stored"""

    upload_metadata: UploadMetadata
    """Metadata about the upload process and file characteristics"""

    processing_metadata: ProcessingMetadata
    """Processing control metadata for queue management"""

    idempotency_key: str
    """Unique key for idempotent processing (user_id + content_hash + timestamp)"""

    message_timestamp: int
    """When this message was created (epoch milliseconds)"""

    def get_routing_key(self) -> str:
        """Generate routing key for RabbitMQ."""
        return f"health.processing.{self.record_type.value.lower()}"

    def is_expired(self, current_timestamp: int) -> bool:
        """Check if message has expired based on TTL."""
        if self.processing_metadata.ttl_seconds is None:
            return False

        ttl_ms = self.processing_metadata.ttl_seconds * 1000
        return (current_timestamp - self.message_timestamp) > ttl_ms


@dataclass
class ETLProcessingResult:
    """Result message from ETL narrative engine processing."""

    message_id: str
    """Unique identifier for this result message"""

    correlation_id: str
    """Correlation ID linking to original processing message"""

    original_idempotency_key: str
    """Idempotency key from original processing message"""

    user_id: str
    """User identifier for data ownership"""

    record_type: HealthRecordType
    """Type of health record that was processed"""

    processing_status: ProcessingStatus
    """Overall status of the processing operation"""

    processing_duration_ms: int
    """Total processing time in milliseconds"""

    processing_timestamp: int
    """When processing completed (epoch milliseconds)"""

    processor_version: str
    """Version of ETL processor that handled this data"""

    processed_data: Optional[ProcessedHealthData] = None
    """Processed data output (null if processing failed)"""

    errors: List[ProcessingError] = None
    """List of errors encountered during processing"""

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    def is_successful(self) -> bool:
        """Check if processing was successful."""
        return self.processing_status == ProcessingStatus.SUCCESS

    def has_critical_errors(self) -> bool:
        """Check if there are any critical errors."""
        return any(not error.recoverable for error in self.errors)


@dataclass
class ErrorMessage:
    """Error message format for failed processing operations."""

    message_id: str
    """Unique identifier for this error message"""

    correlation_id: str
    """Correlation ID linking to original processing message"""

    original_idempotency_key: str
    """Idempotency key from original processing message"""

    user_id: str
    """User identifier for data ownership"""

    service_component: ServiceComponent
    """Service component that generated this error"""

    error_details: ProcessingError
    """Detailed error information"""

    retryable: bool
    """Whether this error condition is retryable"""

    severity: ErrorSeverity
    """Severity level of the error"""

    error_timestamp: int
    """When the error occurred (epoch milliseconds)"""

    original_message: Optional[str] = None
    """Original message content (if available and safe to log)"""

    stack_trace: Optional[str] = None
    """Stack trace information for debugging"""

    environment: Optional[str] = None
    """Environment where error occurred (dev, staging, prod)"""

    def is_critical(self) -> bool:
        """Check if this is a critical error requiring immediate attention."""
        return self.severity == ErrorSeverity.CRITICAL