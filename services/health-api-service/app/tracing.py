"""
OpenTelemetry distributed tracing configuration for Health API Service.

Sends traces to shared Jaeger instance in webauthn-stack for unified observability.
"""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
import structlog

from app.config import settings

logger = structlog.get_logger()


def setup_tracing(app):
    """
    Configure OpenTelemetry to send traces to shared Jaeger.

    This function:
    1. Creates a tracer provider with service identification
    2. Configures OTLP exporter to send traces to Jaeger
    3. Auto-instruments FastAPI for HTTP request tracing
    4. Auto-instruments SQLAlchemy for database query tracing

    Args:
        app: FastAPI application instance

    Returns:
        Tracer instance for creating custom spans
    """

    try:
        # Create resource with service identification
        resource = Resource.create({
            "service.name": settings.JAEGER_SERVICE_NAME,
            "service.version": "1.0.0",
        })

        # Set up tracer provider
        provider = TracerProvider(resource=resource)

        # Configure OTLP exporter to webauthn-stack Jaeger
        # Using gRPC endpoint (port 4319 in webauthn-stack)
        otlp_exporter = OTLPSpanExporter(
            endpoint=settings.JAEGER_OTLP_ENDPOINT,
            insecure=True  # For local development - use TLS in production
        )

        # Add batch span processor for efficient trace export
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

        # Set as global tracer provider
        trace.set_tracer_provider(provider)

        # Auto-instrument FastAPI
        # This automatically creates spans for all HTTP requests
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI auto-instrumentation enabled")

        # Auto-instrument SQLAlchemy
        # This automatically creates spans for database queries
        from app.db.session import engine
        SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
        logger.info("SQLAlchemy auto-instrumentation enabled")

        logger.info(
            "Distributed tracing initialized successfully",
            service_name=settings.JAEGER_SERVICE_NAME,
            jaeger_endpoint=settings.JAEGER_OTLP_ENDPOINT,
            jaeger_ui="http://localhost:16687"
        )

        # Return tracer for custom span creation
        return trace.get_tracer(__name__)

    except Exception as e:
        logger.error(
            "Failed to initialize distributed tracing",
            error=str(e),
            jaeger_endpoint=settings.JAEGER_OTLP_ENDPOINT
        )
        # Don't crash the application if tracing fails
        # Just log the error and continue without tracing
        return None
