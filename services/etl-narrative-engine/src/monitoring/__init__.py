"""
Monitoring module for ETL Narrative Engine.

Provides metrics collection, health check endpoints, and distributed tracing.
"""

from .metrics import (
    decrement_messages_in_progress,
    increment_messages_in_progress,
    initialize_metrics,
    record_avro_parse_error,
    record_avro_records_parsed,
    record_dead_letter,
    record_duplicate_detected,
    record_message_processed,
    record_processing_error,
    record_processing_time,
    record_quality_score,
    record_quarantined,
    record_retry_attempt,
    record_training_data_generated,
    record_validation_check,
    set_consumer_status,
    set_deduplication_cache_size,
    set_rabbitmq_status,
    set_s3_status,
)
from .server import MetricsServer
from .tracing import (
    TracingContext,
    add_span_attributes,
    create_span,
    get_tracer,
    record_exception,
    setup_tracing,
    trace_async_function,
)

__all__ = [
    # Metrics
    'MetricsServer',
    'initialize_metrics',
    'record_message_processed',
    'record_processing_time',
    'record_avro_records_parsed',
    'record_avro_parse_error',
    'record_validation_check',
    'record_quality_score',
    'record_quarantined',
    'record_training_data_generated',
    'record_duplicate_detected',
    'record_processing_error',
    'record_retry_attempt',
    'record_dead_letter',
    'set_consumer_status',
    'set_rabbitmq_status',
    'set_s3_status',
    'increment_messages_in_progress',
    'decrement_messages_in_progress',
    'set_deduplication_cache_size',
    # Tracing
    'setup_tracing',
    'get_tracer',
    'trace_async_function',
    'add_span_attributes',
    'record_exception',
    'create_span',
    'TracingContext',
]
