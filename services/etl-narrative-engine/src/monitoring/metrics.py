"""
Prometheus metrics for ETL Narrative Engine.

Provides metrics for monitoring message processing, errors, and performance.
"""


from prometheus_client import Counter, Gauge, Histogram, Info

# Message processing metrics
messages_processed_total = Counter(
    'etl_messages_processed_total',
    'Total number of messages processed',
    ['record_type', 'status']
)

messages_in_progress = Gauge(
    'etl_messages_in_progress',
    'Number of messages currently being processed'
)

# Processing time metrics
processing_duration_seconds = Histogram(
    'etl_processing_duration_seconds',
    'Time spent processing messages',
    ['record_type'],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0]
)

# Avro parsing metrics
avro_records_parsed_total = Counter(
    'etl_avro_records_parsed_total',
    'Total number of Avro records parsed',
    ['record_type']
)

avro_parse_errors_total = Counter(
    'etl_avro_parse_errors_total',
    'Total number of Avro parsing errors',
    ['record_type', 'error_type']
)

# Validation metrics
validation_checks_total = Counter(
    'etl_validation_checks_total',
    'Total number of validation checks performed',
    ['record_type', 'validation_type', 'result']
)

validation_quality_score = Histogram(
    'etl_validation_quality_score',
    'Quality scores from validation',
    ['record_type'],
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

# Quarantine metrics
records_quarantined_total = Counter(
    'etl_records_quarantined_total',
    'Total number of records sent to quarantine',
    ['record_type', 'reason']
)

# Training data output metrics
training_data_generated_total = Counter(
    'etl_training_data_generated_total',
    'Total number of training data files generated',
    ['record_type']
)

training_data_size_bytes = Histogram(
    'etl_training_data_size_bytes',
    'Size of generated training data files',
    ['record_type'],
    buckets=[100, 1000, 10000, 100000, 1000000, 10000000]
)

# Deduplication metrics
duplicate_messages_total = Counter(
    'etl_duplicate_messages_total',
    'Total number of duplicate messages detected',
    ['record_type']
)

deduplication_cache_size = Gauge(
    'etl_deduplication_cache_size',
    'Number of entries in deduplication cache'
)

# Error and retry metrics
processing_errors_total = Counter(
    'etl_processing_errors_total',
    'Total number of processing errors',
    ['error_type', 'record_type']
)

retry_attempts_total = Counter(
    'etl_retry_attempts_total',
    'Total number of retry attempts',
    ['record_type', 'retry_number']
)

dead_letter_messages_total = Counter(
    'etl_dead_letter_messages_total',
    'Total number of messages sent to dead letter queue',
    ['record_type', 'reason']
)

# System health metrics
consumer_status = Gauge(
    'etl_consumer_status',
    'Consumer status (1=running, 0=stopped)'
)

rabbitmq_connection_status = Gauge(
    'etl_rabbitmq_connection_status',
    'RabbitMQ connection status (1=connected, 0=disconnected)'
)

s3_connection_status = Gauge(
    'etl_s3_connection_status',
    'S3/MinIO connection status (1=connected, 0=disconnected)'
)

# Service info
service_info = Info(
    'etl_service',
    'ETL Narrative Engine service information'
)


def initialize_metrics(service_name: str, version: str, environment: str):
    """Initialize service info metrics"""
    service_info.info({
        'service': service_name,
        'version': version,
        'environment': environment
    })

    # Set initial status values
    consumer_status.set(0)
    rabbitmq_connection_status.set(0)
    s3_connection_status.set(0)
    messages_in_progress.set(0)
    deduplication_cache_size.set(0)


def record_message_processed(record_type: str, status: str):
    """Record a processed message"""
    messages_processed_total.labels(
        record_type=record_type,
        status=status
    ).inc()


def record_processing_time(record_type: str, duration_seconds: float):
    """Record processing duration"""
    processing_duration_seconds.labels(
        record_type=record_type
    ).observe(duration_seconds)


def record_avro_records_parsed(record_type: str, count: int = 1):
    """Record Avro records parsed"""
    avro_records_parsed_total.labels(
        record_type=record_type
    ).inc(count)


def record_avro_parse_error(record_type: str, error_type: str):
    """Record Avro parsing error"""
    avro_parse_errors_total.labels(
        record_type=record_type,
        error_type=error_type
    ).inc()


def record_validation_check(record_type: str, validation_type: str, result: str):
    """Record a validation check"""
    validation_checks_total.labels(
        record_type=record_type,
        validation_type=validation_type,
        result=result
    ).inc()


def record_quality_score(record_type: str, score: float):
    """Record validation quality score"""
    validation_quality_score.labels(
        record_type=record_type
    ).observe(score)


def record_quarantined(record_type: str, reason: str):
    """Record a quarantined record"""
    records_quarantined_total.labels(
        record_type=record_type,
        reason=reason
    ).inc()


def record_training_data_generated(record_type: str, size_bytes: int):
    """Record training data generation"""
    training_data_generated_total.labels(
        record_type=record_type
    ).inc()

    training_data_size_bytes.labels(
        record_type=record_type
    ).observe(size_bytes)


def record_duplicate_detected(record_type: str):
    """Record duplicate message detection"""
    duplicate_messages_total.labels(
        record_type=record_type
    ).inc()


def record_processing_error(error_type: str, record_type: str = "unknown"):
    """Record a processing error"""
    processing_errors_total.labels(
        error_type=error_type,
        record_type=record_type
    ).inc()


def record_retry_attempt(record_type: str, retry_number: int):
    """Record a retry attempt"""
    retry_attempts_total.labels(
        record_type=record_type,
        retry_number=str(retry_number)
    ).inc()


def record_dead_letter(record_type: str, reason: str):
    """Record message sent to dead letter queue"""
    dead_letter_messages_total.labels(
        record_type=record_type,
        reason=reason
    ).inc()


def set_consumer_status(running: bool):
    """Set consumer running status"""
    consumer_status.set(1 if running else 0)


def set_rabbitmq_status(connected: bool):
    """Set RabbitMQ connection status"""
    rabbitmq_connection_status.set(1 if connected else 0)


def set_s3_status(connected: bool):
    """Set S3 connection status"""
    s3_connection_status.set(1 if connected else 0)


def increment_messages_in_progress():
    """Increment messages in progress"""
    messages_in_progress.inc()


def decrement_messages_in_progress():
    """Decrement messages in progress"""
    messages_in_progress.dec()


def set_deduplication_cache_size(size: int):
    """Set deduplication cache size"""
    deduplication_cache_size.set(size)
