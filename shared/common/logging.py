"""
Structured logging configuration for Health Data AI Platform.
"""

import logging
import structlog
import sys
from typing import Any, Dict, Optional
from datetime import datetime


def setup_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    service_name: Optional[str] = None
) -> None:
    """
    Set up structured logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Format type ('json' or 'console')
        service_name: Name of the service for log context
    """
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )

    # Configure structlog
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        add_timestamp,
        add_service_context(service_name) if service_name else add_default_context,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def add_timestamp(logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Add timestamp to log events."""
    event_dict["timestamp"] = datetime.utcnow().isoformat() + "Z"
    return event_dict


def add_service_context(service_name: str):
    """Create processor to add service context."""
    def processor(logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        event_dict["service"] = service_name
        event_dict["platform"] = "health-data-ai"
        return event_dict
    return processor


def add_default_context(logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Add default context to log events."""
    event_dict["platform"] = "health-data-ai"
    return event_dict


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


def add_correlation_id(correlation_id: str):
    """
    Add correlation ID to logger context.

    Args:
        correlation_id: Unique identifier for request correlation

    Returns:
        Logger with correlation ID bound
    """
    return structlog.get_logger().bind(correlation_id=correlation_id)


def log_health_data_event(
    logger: structlog.stdlib.BoundLogger,
    event_type: str,
    user_id: str,
    record_type: str,
    **kwargs
) -> None:
    """
    Log health data processing events with consistent structure.

    Args:
        logger: Structured logger instance
        event_type: Type of event (upload, processing, error, etc.)
        user_id: User identifier
        record_type: Type of health record
        **kwargs: Additional event data
    """
    logger.info(
        "Health data event",
        event_type=event_type,
        user_id=user_id,
        record_type=record_type,
        **kwargs
    )


def log_api_request(
    logger: structlog.stdlib.BoundLogger,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    user_id: Optional[str] = None,
    **kwargs
) -> None:
    """
    Log API requests with consistent structure.

    Args:
        logger: Structured logger instance
        method: HTTP method
        path: Request path
        status_code: HTTP status code
        duration_ms: Request duration in milliseconds
        user_id: Optional user identifier
        **kwargs: Additional request data
    """
    logger.info(
        "API request",
        method=method,
        path=path,
        status_code=status_code,
        duration_ms=duration_ms,
        user_id=user_id,
        **kwargs
    )


def log_processing_result(
    logger: structlog.stdlib.BoundLogger,
    operation: str,
    success: bool,
    duration_ms: float,
    record_count: Optional[int] = None,
    error_message: Optional[str] = None,
    **kwargs
) -> None:
    """
    Log processing results with consistent structure.

    Args:
        logger: Structured logger instance
        operation: Processing operation name
        success: Whether operation succeeded
        duration_ms: Processing duration in milliseconds
        record_count: Number of records processed
        error_message: Error message if operation failed
        **kwargs: Additional processing data
    """
    logger.info(
        "Processing result",
        operation=operation,
        success=success,
        duration_ms=duration_ms,
        record_count=record_count,
        error_message=error_message,
        **kwargs
    )