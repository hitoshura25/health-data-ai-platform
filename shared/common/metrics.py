"""
Metrics collection utilities for Health Data AI Platform.
"""

from prometheus_client import Counter, Histogram, Gauge, Info, start_http_server
import time
from typing import Dict, Any, Optional, List
from functools import wraps
import structlog
from datetime import datetime
from contextlib import contextmanager


class MetricsCollector:
    """Centralized metrics collection for health data platform."""

    def __init__(self, service_name: str):
        """
        Initialize metrics collector for a service.

        Args:
            service_name: Name of the service for metric labeling
        """
        self.service_name = service_name
        self.logger = structlog.get_logger(__name__)

        # Initialize metrics
        self._init_common_metrics()
        self._init_health_data_metrics()
        self._init_api_metrics()
        self._init_processing_metrics()

    def _init_common_metrics(self):
        """Initialize common service metrics."""
        self.service_info = Info(
            'service_info',
            'Service information',
            ['service_name', 'version']
        )

        self.requests_total = Counter(
            'requests_total',
            'Total number of requests',
            ['service', 'method', 'endpoint', 'status_code']
        )

        self.request_duration = Histogram(
            'request_duration_seconds',
            'Request duration in seconds',
            ['service', 'method', 'endpoint'],
            buckets=[0.001, 0.01, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0]
        )

        self.active_connections = Gauge(
            'active_connections',
            'Number of active connections',
            ['service']
        )

        self.errors_total = Counter(
            'errors_total',
            'Total number of errors',
            ['service', 'error_type', 'component']
        )

    def _init_health_data_metrics(self):
        """Initialize health data specific metrics."""
        self.health_records_processed = Counter(
            'health_records_processed_total',
            'Total number of health records processed',
            ['service', 'record_type', 'status']
        )

        self.health_data_quality_score = Histogram(
            'health_data_quality_score',
            'Data quality scores for health records',
            ['service', 'record_type'],
            buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        )

        self.file_upload_size = Histogram(
            'file_upload_size_bytes',
            'Size of uploaded health data files',
            ['service', 'record_type'],
            buckets=[1024, 10240, 102400, 1048576, 10485760, 104857600]  # 1KB to 100MB
        )

        self.clinical_alerts = Counter(
            'clinical_alerts_total',
            'Number of clinical alerts generated',
            ['service', 'alert_type', 'severity']
        )

    def _init_api_metrics(self):
        """Initialize API specific metrics."""
        self.api_rate_limit_hits = Counter(
            'api_rate_limit_hits_total',
            'Number of rate limit hits',
            ['service', 'endpoint', 'user_type']
        )

        self.authentication_attempts = Counter(
            'authentication_attempts_total',
            'Number of authentication attempts',
            ['service', 'status', 'method']
        )

        self.concurrent_users = Gauge(
            'concurrent_users',
            'Number of concurrent users',
            ['service']
        )

    def _init_processing_metrics(self):
        """Initialize processing specific metrics."""
        self.queue_size = Gauge(
            'queue_size',
            'Number of messages in queue',
            ['service', 'queue_name']
        )

        self.processing_duration = Histogram(
            'processing_duration_seconds',
            'Time spent processing messages',
            ['service', 'operation', 'record_type'],
            buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0]
        )

        self.message_retries = Counter(
            'message_retries_total',
            'Number of message processing retries',
            ['service', 'record_type', 'retry_reason']
        )

        self.etl_narratives_generated = Counter(
            'etl_narratives_generated_total',
            'Number of clinical narratives generated',
            ['service', 'record_type', 'narrative_type']
        )

    def set_service_info(self, version: str = "unknown", **kwargs):
        """Set service information."""
        info_dict = {
            'service_name': self.service_name,
            'version': version,
            **kwargs
        }
        self.service_info.info(info_dict)

    def start_metrics_server(self, port: int = 9090):
        """Start Prometheus metrics server."""
        try:
            start_http_server(port)
            self.logger.info("Metrics server started", port=port)
        except Exception as e:
            self.logger.error("Failed to start metrics server", error=str(e))

    # Request tracking decorators and context managers
    def track_request(self, method: str, endpoint: str):
        """Decorator to track API requests."""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                start_time = time.time()
                status_code = 500  # Default to error

                try:
                    result = await func(*args, **kwargs)
                    status_code = getattr(result, 'status_code', 200)
                    return result
                except Exception as e:
                    self.errors_total.labels(
                        service=self.service_name,
                        error_type=type(e).__name__,
                        component='api'
                    ).inc()
                    raise
                finally:
                    duration = time.time() - start_time
                    self.requests_total.labels(
                        service=self.service_name,
                        method=method,
                        endpoint=endpoint,
                        status_code=str(status_code)
                    ).inc()
                    self.request_duration.labels(
                        service=self.service_name,
                        method=method,
                        endpoint=endpoint
                    ).observe(duration)

            return wrapper
        return decorator

    @contextmanager
    def track_processing_time(self, operation: str, record_type: str = "unknown"):
        """Context manager to track processing time."""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.processing_duration.labels(
                service=self.service_name,
                operation=operation,
                record_type=record_type
            ).observe(duration)

    # Health data specific tracking
    def record_health_data_processed(
        self,
        record_type: str,
        status: str,
        quality_score: Optional[float] = None,
        file_size: Optional[int] = None
    ):
        """Record health data processing metrics."""
        self.health_records_processed.labels(
            service=self.service_name,
            record_type=record_type,
            status=status
        ).inc()

        if quality_score is not None:
            self.health_data_quality_score.labels(
                service=self.service_name,
                record_type=record_type
            ).observe(quality_score)

        if file_size is not None:
            self.file_upload_size.labels(
                service=self.service_name,
                record_type=record_type
            ).observe(file_size)

    def record_clinical_alert(self, alert_type: str, severity: str):
        """Record clinical alert generation."""
        self.clinical_alerts.labels(
            service=self.service_name,
            alert_type=alert_type,
            severity=severity
        ).inc()

    def record_authentication(self, status: str, method: str = "jwt"):
        """Record authentication attempt."""
        self.authentication_attempts.labels(
            service=self.service_name,
            status=status,
            method=method
        ).inc()

    def record_rate_limit_hit(self, endpoint: str, user_type: str = "user"):
        """Record rate limit hit."""
        self.api_rate_limit_hits.labels(
            service=self.service_name,
            endpoint=endpoint,
            user_type=user_type
        ).inc()

    def set_queue_size(self, queue_name: str, size: int):
        """Set current queue size."""
        self.queue_size.labels(
            service=self.service_name,
            queue_name=queue_name
        ).set(size)

    def record_message_retry(self, record_type: str, retry_reason: str):
        """Record message processing retry."""
        self.message_retries.labels(
            service=self.service_name,
            record_type=record_type,
            retry_reason=retry_reason
        ).inc()

    def record_narrative_generated(self, record_type: str, narrative_type: str = "clinical"):
        """Record ETL narrative generation."""
        self.etl_narratives_generated.labels(
            service=self.service_name,
            record_type=record_type,
            narrative_type=narrative_type
        ).inc()

    def set_concurrent_users(self, count: int):
        """Set concurrent user count."""
        self.concurrent_users.labels(service=self.service_name).set(count)

    def set_active_connections(self, count: int):
        """Set active connection count."""
        self.active_connections.labels(service=self.service_name).set(count)

    def record_error(self, error_type: str, component: str = "general"):
        """Record error occurrence."""
        self.errors_total.labels(
            service=self.service_name,
            error_type=error_type,
            component=component
        ).inc()

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of current metrics (for debugging/monitoring)."""
        return {
            "service": self.service_name,
            "timestamp": datetime.utcnow().isoformat(),
            "metrics_available": [
                "requests_total",
                "request_duration",
                "health_records_processed",
                "health_data_quality_score",
                "clinical_alerts",
                "processing_duration",
                "queue_size",
                "errors_total"
            ]
        }


# Global metrics instance (can be used across modules)
_metrics_instance: Optional[MetricsCollector] = None


def initialize_metrics(service_name: str, version: str = "unknown") -> MetricsCollector:
    """Initialize global metrics instance."""
    global _metrics_instance
    _metrics_instance = MetricsCollector(service_name)
    _metrics_instance.set_service_info(version=version)
    return _metrics_instance


def get_metrics() -> Optional[MetricsCollector]:
    """Get global metrics instance."""
    return _metrics_instance


# Convenience decorators using global instance
def track_api_request(method: str, endpoint: str):
    """Decorator using global metrics instance."""
    def decorator(func):
        if _metrics_instance:
            return _metrics_instance.track_request(method, endpoint)(func)
        return func
    return decorator


def track_processing(operation: str, record_type: str = "unknown"):
    """Context manager using global metrics instance."""
    if _metrics_instance:
        return _metrics_instance.track_processing_time(operation, record_type)
    else:
        @contextmanager
        def dummy_context():
            yield
        return dummy_context()