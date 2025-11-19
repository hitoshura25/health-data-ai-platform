"""
Distributed tracing for ETL Narrative Engine using OpenTelemetry and Jaeger.

Provides tracing decorators and helpers for tracking message processing across
the ETL pipeline. Integrates with Jaeger from webauthn-stack for unified observability.
"""

import functools
from collections.abc import Callable
from typing import Any

import structlog
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode

from ..config.settings import settings

logger = structlog.get_logger()

# Global tracer instance
_tracer: trace.Tracer | None = None


def setup_tracing() -> trace.Tracer:
    """
    Setup distributed tracing with Jaeger.

    Configures OpenTelemetry to export traces to Jaeger OTLP endpoint.
    Uses the shared Jaeger instance from webauthn-stack.

    Returns:
        Configured tracer instance
    """
    global _tracer

    if not settings.enable_jaeger_tracing:
        logger.info("jaeger_tracing_disabled")
        # Return a no-op tracer
        return trace.get_tracer(__name__)

    if _tracer is not None:
        return _tracer

    logger.info(
        "initializing_jaeger_tracing",
        service_name=settings.jaeger_service_name,
        otlp_endpoint=settings.jaeger_otlp_endpoint
    )

    try:
        # Create resource with service metadata
        resource = Resource(attributes={
            "service.name": settings.jaeger_service_name,
            "service.version": settings.version,
            "deployment.environment": settings.environment,
        })

        # Create tracer provider
        tracer_provider = TracerProvider(resource=resource)

        # Configure OTLP exporter (connects to Jaeger from webauthn-stack)
        otlp_exporter = OTLPSpanExporter(
            endpoint=settings.jaeger_otlp_endpoint,
            insecure=True  # Use insecure for local development
        )

        # Add span processor with batching for efficiency
        tracer_provider.add_span_processor(
            BatchSpanProcessor(otlp_exporter)
        )

        # Set global tracer provider
        trace.set_tracer_provider(tracer_provider)

        _tracer = trace.get_tracer(__name__)

        logger.info(
            "jaeger_tracing_initialized",
            service_name=settings.jaeger_service_name,
            otlp_endpoint=settings.jaeger_otlp_endpoint
        )

        return _tracer

    except Exception as e:
        logger.error(
            "jaeger_tracing_initialization_failed",
            error=str(e),
            error_type=type(e).__name__
        )
        # Return no-op tracer on failure (fail-safe)
        return trace.get_tracer(__name__)


def get_tracer() -> trace.Tracer:
    """
    Get the global tracer instance.

    Returns:
        Global tracer (or no-op tracer if tracing is disabled)
    """
    global _tracer

    if _tracer is None:
        _tracer = setup_tracing()

    return _tracer


def trace_async_function(
    span_name: str | None = None,
    attributes: dict[str, Any] | None = None
):
    """
    Decorator for tracing async functions.

    Automatically creates a span for the decorated function and records
    exceptions if they occur.

    Args:
        span_name: Optional custom span name (defaults to function name)
        attributes: Optional span attributes to set

    Usage:
        @trace_async_function("process_message")
        async def process_health_data(message_data: dict):
            # Function implementation
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if not settings.enable_jaeger_tracing:
                # Skip tracing if disabled
                return await func(*args, **kwargs)

            tracer = get_tracer()
            effective_span_name = span_name or func.__name__

            with tracer.start_as_current_span(effective_span_name) as span:
                # Set custom attributes if provided
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)

                # Set function metadata
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)

                try:
                    result = await func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result

                except Exception as e:
                    # Record exception in span
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)

                    # Set error attributes
                    span.set_attribute("error", True)
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))

                    raise

        return wrapper
    return decorator


def add_span_attributes(attributes: dict[str, Any]):
    """
    Add attributes to the current active span.

    Args:
        attributes: Dictionary of attributes to add

    Usage:
        with tracer.start_as_current_span("process") as span:
            add_span_attributes({
                "record_type": "BloodGlucoseRecord",
                "user_id": "user123"
            })
    """
    if not settings.enable_jaeger_tracing:
        return

    span = trace.get_current_span()
    if span.is_recording():
        for key, value in attributes.items():
            # Convert value to string if it's not a primitive type
            if isinstance(value, (str, int, float, bool)):
                span.set_attribute(key, value)
            else:
                span.set_attribute(key, str(value))


def record_exception(exception: Exception, attributes: dict[str, Any] | None = None):
    """
    Record an exception in the current active span.

    Args:
        exception: The exception to record
        attributes: Optional additional attributes

    Usage:
        try:
            # Some operation
            pass
        except Exception as e:
            record_exception(e, {"operation": "s3_download"})
            raise
    """
    if not settings.enable_jaeger_tracing:
        return

    span = trace.get_current_span()
    if span.is_recording():
        span.record_exception(exception)
        span.set_status(Status(StatusCode.ERROR, str(exception)))

        if attributes:
            add_span_attributes(attributes)


class TracingContext:
    """
    Context manager for creating spans with automatic error handling.

    Usage:
        async with TracingContext("download_from_s3", {"bucket": "health-data"}):
            # Operations to trace
            data = await download_file()
    """

    def __init__(self, span_name: str, attributes: dict[str, Any] | None = None):
        self.span_name = span_name
        self.attributes = attributes or {}
        self.span = None
        self.token = None

    def __enter__(self):
        if not settings.enable_jaeger_tracing:
            return self

        tracer = get_tracer()
        self.span = tracer.start_span(self.span_name)
        self.token = trace.set_span_in_context(self.span).__enter__()

        # Set attributes
        if self.attributes:
            add_span_attributes(self.attributes)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.span is None:
            return False

        if exc_type is not None:
            # Record exception
            self.span.set_status(Status(StatusCode.ERROR, str(exc_val)))
            self.span.record_exception(exc_val)
            self.span.set_attribute("error", True)
            self.span.set_attribute("error.type", exc_type.__name__)
        else:
            self.span.set_status(Status(StatusCode.OK))

        if self.token:
            self.token.__exit__(exc_type, exc_val, exc_tb)

        self.span.end()
        return False  # Don't suppress exceptions


# Convenience function for creating traced spans
def create_span(name: str, attributes: dict[str, Any] | None = None):
    """
    Create a new span with the given name and attributes.

    Args:
        name: Span name
        attributes: Optional span attributes

    Returns:
        Span context manager

    Usage:
        with create_span("validate_data", {"record_type": "BloodGlucoseRecord"}):
            # Validation logic
            pass
    """
    return TracingContext(name, attributes)
