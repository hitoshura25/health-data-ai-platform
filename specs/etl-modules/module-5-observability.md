# Module 5: Observability & Monitoring

**Module ID:** ETL-M5
**Priority:** P2 (Production Readiness)
**Estimated Effort:** 1 week
**Dependencies:** Module 1 (Integrates with core consumer)
**Team Assignment:** DevOps Engineer or Backend Developer with Observability Experience

---

## Module Overview

This module implements comprehensive observability for the ETL Narrative Engine, including metrics, distributed tracing, health checks, and structured logging. It provides visibility into system performance, errors, and data quality without modifying core business logic.

### Key Responsibilities
- Prometheus metrics export (`/metrics` endpoint)
- Distributed tracing with Jaeger (reuses webauthn-stack Jaeger)
- Health check endpoint (`/health`)
- Structured logging with correlation IDs
- Performance monitoring
- Error tracking and alerting hooks

### What This Module Does NOT Include
- ❌ Core business logic (Module 1, 3)
- ❌ Data processing (Modules 2, 3, 4)
- ❌ Deployment infrastructure (Module 6)

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Module 1: Core Consumer                                │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Message Processing                             │   │
│  │  ↓                                               │   │
│  │  Module 5 Metrics Hook ────→ Prometheus         │   │
│  │  Module 5 Tracing ──────────→ Jaeger (existing) │   │
│  │  Module 5 Logging ──────────→ stdout/file       │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘

External Access:
- GET /metrics  → Prometheus scraping
- GET /health   → Kubernetes/Docker health checks
- Jaeger UI     → http://localhost:16687 (from webauthn-stack)
```

---

## Component 1: Prometheus Metrics

### Metrics Specification

```python
# src/monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge, generate_latest

# Message processing metrics
messages_consumed_total = Counter(
    'etl_messages_consumed_total',
    'Total messages consumed from RabbitMQ',
    ['queue_name']
)

messages_processed_total = Counter(
    'etl_messages_processed_total',
    'Total messages successfully processed',
    ['record_type', 'status']  # status: success, failed, quarantined
)

processing_duration_seconds = Histogram(
    'etl_processing_duration_seconds',
    'Time spent processing messages',
    ['record_type'],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0)
)

# Validation metrics
validation_failures_total = Counter(
    'etl_validation_failures_total',
    'Total validation failures',
    ['record_type', 'failure_reason']
)

quality_score_histogram = Histogram(
    'etl_quality_score',
    'Data quality scores',
    ['record_type'],
    buckets=(0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
)

# Clinical processing metrics
clinical_events_detected = Counter(
    'etl_clinical_events_detected',
    'Clinical events detected',
    ['record_type', 'event_type']  # event_type: hypoglycemia, tachycardia, etc.
)

# Training data output metrics
training_examples_generated = Counter(
    'etl_training_examples_generated',
    'Training examples written to JSONL',
    ['health_domain']
)

# Error metrics
errors_total = Counter(
    'etl_errors_total',
    'Total errors encountered',
    ['error_type', 'component']  # component: consumer, processor, output
)

# Deduplication metrics
duplicate_messages_skipped = Counter(
    'etl_duplicate_messages_skipped',
    'Messages skipped due to deduplication',
    ['record_type']
)

# System metrics
active_consumers = Gauge(
    'etl_active_consumers',
    'Number of active message consumers'
)

rabbitmq_queue_depth = Gauge(
    'etl_rabbitmq_queue_depth',
    'Current depth of RabbitMQ queue',
    ['queue_name']
)
```

### Metrics Collection Hooks

```python
# src/monitoring/metrics.py
from typing import Dict, Any

class MetricsCollector:
    """Collect and export metrics"""

    @staticmethod
    def record_message_consumed(queue_name: str):
        """Record message consumption"""
        messages_consumed_total.labels(queue_name=queue_name).inc()

    @staticmethod
    def record_processing_complete(
        record_type: str,
        duration: float,
        status: str,  # 'success', 'failed', 'quarantined'
        quality_score: float = None
    ):
        """Record completed processing"""

        messages_processed_total.labels(
            record_type=record_type,
            status=status
        ).inc()

        processing_duration_seconds.labels(
            record_type=record_type
        ).observe(duration)

        if quality_score is not None:
            quality_score_histogram.labels(
                record_type=record_type
            ).observe(quality_score)

    @staticmethod
    def record_validation_failure(record_type: str, failure_reason: str):
        """Record validation failure"""
        validation_failures_total.labels(
            record_type=record_type,
            failure_reason=failure_reason
        ).inc()

    @staticmethod
    def record_clinical_event(record_type: str, event_type: str):
        """Record clinical event detection"""
        clinical_events_detected.labels(
            record_type=record_type,
            event_type=event_type
        ).inc()

    @staticmethod
    def record_training_example(health_domain: str):
        """Record training example generation"""
        training_examples_generated.labels(
            health_domain=health_domain
        ).inc()

    @staticmethod
    def record_error(error_type: str, component: str):
        """Record error"""
        errors_total.labels(
            error_type=error_type,
            component=component
        ).inc()

    @staticmethod
    def record_duplicate_skipped(record_type: str):
        """Record duplicate message skipped"""
        duplicate_messages_skipped.labels(
            record_type=record_type
        ).inc()

    @staticmethod
    def set_active_consumers(count: int):
        """Set active consumer count"""
        active_consumers.set(count)

    @staticmethod
    async def update_queue_depth(rabbitmq_client, queue_name: str):
        """Update RabbitMQ queue depth"""
        try:
            queue_info = await rabbitmq_client.queue_declare(
                queue=queue_name,
                passive=True
            )
            depth = queue_info.method.message_count
            rabbitmq_queue_depth.labels(queue_name=queue_name).set(depth)
        except Exception:
            pass
```

### Metrics Endpoint

```python
# src/monitoring/metrics_server.py
from fastapi import FastAPI
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

app = FastAPI()

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "etl-narrative-engine",
        "version": "1.0.0"
    }

# Run metrics server on separate port (e.g., 8004)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
```

---

## Component 2: Distributed Tracing (Jaeger)

### Jaeger Integration

**IMPORTANT**: Reuse existing Jaeger instance from `webauthn-stack/`.

```python
# src/monitoring/tracing.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

def setup_tracing(service_name: str = "etl-narrative-engine"):
    """Setup distributed tracing with Jaeger"""

    # Create resource
    resource = Resource(attributes={
        "service.name": service_name,
        "service.version": "1.0.0",
    })

    # Create tracer provider
    tracer_provider = TracerProvider(resource=resource)

    # Configure OTLP exporter (connects to Jaeger from webauthn-stack)
    otlp_exporter = OTLPSpanExporter(
        endpoint="http://localhost:4319",  # Jaeger OTLP gRPC endpoint
        insecure=True
    )

    # Add span processor
    tracer_provider.add_span_processor(
        BatchSpanProcessor(otlp_exporter)
    )

    # Set global tracer provider
    trace.set_tracer_provider(tracer_provider)

    return trace.get_tracer(__name__)

# Global tracer
tracer = setup_tracing()
```

### Tracing Instrumentation

```python
# src/monitoring/tracing.py
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

tracer = trace.get_tracer(__name__)

def trace_message_processing(func):
    """Decorator for tracing message processing"""

    async def wrapper(*args, **kwargs):
        with tracer.start_as_current_span("process_message") as span:
            # Extract message data if available
            if args and isinstance(args[0], dict):
                message_data = args[0]
                span.set_attribute("record_type", message_data.get('record_type', 'unknown'))
                span.set_attribute("correlation_id", message_data.get('correlation_id', 'none'))
                span.set_attribute("user_id", message_data.get('user_id', 'none'))

            try:
                result = await func(*args, **kwargs)
                span.set_status(Status(StatusCode.OK))
                return result
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    return wrapper

# Usage in consumer
@trace_message_processing
async def process_health_data(message_data: dict):
    """Process health data message"""

    with tracer.start_as_current_span("download_from_s3") as span:
        span.set_attribute("bucket", message_data['bucket'])
        span.set_attribute("key", message_data['key'])
        file_content = await download_file(...)

    with tracer.start_as_current_span("validate_data") as span:
        validation_result = await validator.validate(...)
        span.set_attribute("quality_score", validation_result.quality_score)

    with tracer.start_as_current_span("process_clinical_data") as span:
        processing_result = await processor.process_with_clinical_insights(...)
        span.set_attribute("records_processed", processing_result.records_processed)

    with tracer.start_as_current_span("generate_training_output") as span:
        await training_formatter.generate_training_output(...)
```

---

## Component 3: Health Checks

### Health Check Implementation

```python
# src/monitoring/health.py
from typing import Dict, Any
from datetime import datetime

class HealthChecker:
    """Health check for ETL service"""

    def __init__(self, rabbitmq_client, s3_client, dedup_store):
        self.rabbitmq_client = rabbitmq_client
        self.s3_client = s3_client
        self.dedup_store = dedup_store

    async def check_health(self) -> Dict[str, Any]:
        """Comprehensive health check"""

        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {}
        }

        # Check RabbitMQ connection
        try:
            # Simple connection check
            health_status["checks"]["rabbitmq"] = {
                "status": "healthy",
                "connected": True
            }
        except Exception as e:
            health_status["checks"]["rabbitmq"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["status"] = "unhealthy"

        # Check S3/MinIO connection
        try:
            await self.s3_client.list_buckets()
            health_status["checks"]["s3"] = {
                "status": "healthy",
                "accessible": True
            }
        except Exception as e:
            health_status["checks"]["s3"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["status"] = "unhealthy"

        # Check deduplication store
        try:
            await self.dedup_store.ping()
            health_status["checks"]["deduplication_store"] = {
                "status": "healthy",
                "accessible": True
            }
        except Exception as e:
            health_status["checks"]["deduplication_store"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["status"] = "degraded"  # Non-critical

        return health_status
```

### Health Endpoint

```python
# In metrics_server.py
from src.monitoring.health import HealthChecker

health_checker = None  # Initialized at startup

@app.get("/health")
async def health():
    """Health check endpoint"""

    if health_checker is None:
        return {"status": "starting"}

    health_status = await health_checker.check_health()

    # Return 200 for healthy/degraded, 503 for unhealthy
    status_code = 200 if health_status["status"] in ["healthy", "degraded"] else 503

    return Response(
        content=json.dumps(health_status),
        media_type="application/json",
        status_code=status_code
    )
```

---

## Component 4: Structured Logging

### Logging Setup

```python
# src/monitoring/logging_config.py
import structlog
import logging
import sys

def setup_logging(log_level: str = "INFO", enable_json: bool = True):
    """Setup structured logging with structlog"""

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper())
    )

    # Configure structlog
    processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if enable_json:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    return structlog.get_logger()

# Global logger
logger = setup_logging()
```

### Logging with Correlation IDs

```python
# src/monitoring/logging.py
import structlog

logger = structlog.get_logger()

async def process_health_data(message_data: dict):
    """Process health data with structured logging"""

    # Bind correlation ID to logger context
    log = logger.bind(
        correlation_id=message_data['correlation_id'],
        record_type=message_data['record_type'],
        user_id=message_data['user_id']
    )

    log.info("processing_started", bucket=message_data['bucket'], key=message_data['key'])

    try:
        # Processing steps...

        log.info(
            "processing_completed",
            duration_seconds=duration,
            records_processed=records_processed,
            quality_score=quality_score
        )

    except Exception as e:
        log.error(
            "processing_failed",
            error=str(e),
            error_type=type(e).__name__
        )
        raise
```

---

## Implementation Checklist

### Week 1: Observability
- [ ] Create monitoring module structure
- [ ] Implement Prometheus metrics
  - [ ] Define all metrics (counters, histograms, gauges)
  - [ ] Create `MetricsCollector` class
  - [ ] Implement metrics endpoint (`/metrics`)
- [ ] Implement distributed tracing
  - [ ] Setup Jaeger OTLP integration
  - [ ] Create tracing decorators
  - [ ] Add spans to critical paths
- [ ] Implement health checks
  - [ ] RabbitMQ health check
  - [ ] S3 health check
  - [ ] Dedup store health check
  - [ ] Implement `/health` endpoint
- [ ] Implement structured logging
  - [ ] Setup structlog
  - [ ] Add correlation ID binding
  - [ ] Add log statements to critical paths
- [ ] Integrate metrics hooks into Module 1
- [ ] Write unit tests (>80% coverage)
- [ ] Write integration tests
  - [ ] Verify metrics are collected
  - [ ] Verify traces appear in Jaeger
  - [ ] Verify health checks work
- [ ] Document observability setup

---

## Testing Strategy

### Unit Tests

```python
# tests/test_metrics.py
import pytest
from src.monitoring.metrics import MetricsCollector
from prometheus_client import REGISTRY

@pytest.mark.asyncio
async def test_metrics_collection():
    """Test metrics are collected correctly"""

    # Record processing
    MetricsCollector.record_processing_complete(
        record_type='BloodGlucoseRecord',
        duration=2.5,
        status='success',
        quality_score=0.95
    )

    # Verify metrics
    metrics = {
        sample.name: sample
        for family in REGISTRY.collect()
        for sample in family.samples
    }

    assert 'etl_messages_processed_total' in str(metrics)
    assert 'etl_processing_duration_seconds' in str(metrics)
```

### Integration Tests

```python
# tests/test_observability_integration.py
@pytest.mark.integration
@pytest.mark.asyncio
async def test_metrics_endpoint():
    """Test metrics endpoint returns Prometheus format"""

    from src.monitoring.metrics_server import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    response = client.get("/metrics")

    assert response.status_code == 200
    assert 'etl_messages_processed_total' in response.text
    assert 'etl_processing_duration_seconds' in response.text

@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_endpoint():
    """Test health check endpoint"""

    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code in [200, 503]
    data = response.json()
    assert 'status' in data
    assert 'checks' in data
```

---

## Configuration

```python
# src/monitoring/config.py
from pydantic import BaseModel

class ObservabilityConfig(BaseModel):
    """Configuration for observability"""

    # Metrics
    enable_metrics: bool = True
    metrics_port: int = 8004

    # Tracing
    enable_jaeger_tracing: bool = True
    jaeger_otlp_endpoint: str = "http://localhost:4319"

    # Logging
    log_level: str = "INFO"
    enable_json_logs: bool = True

    # Health checks
    enable_health_checks: bool = True
```

---

## Dependencies

### Python Packages
```txt
prometheus-client==0.19.0    # Prometheus metrics
opentelemetry-api==1.21.0    # OpenTelemetry API
opentelemetry-sdk==1.21.0    # OpenTelemetry SDK
opentelemetry-exporter-otlp-proto-grpc==1.21.0  # Jaeger export
structlog==24.1.0            # Structured logging
fastapi==0.109.0             # Metrics server
uvicorn==0.27.0              # ASGI server
```

### External Services
- **Jaeger** (from webauthn-stack) - Distributed tracing UI
- **Prometheus** (optional) - Metrics scraping and visualization

---

## Success Criteria

**Module Complete When:**
- ✅ Prometheus metrics endpoint working (`/metrics`)
- ✅ All critical metrics defined and collected
- ✅ Jaeger tracing integrated (traces visible in UI)
- ✅ Health check endpoint working (`/health`)
- ✅ Structured logging with correlation IDs
- ✅ Integration with Module 1 complete
- ✅ Unit tests: >80% coverage
- ✅ Integration tests passing
- ✅ Documentation complete

**Ready for Integration When:**
- ✅ Metrics hooks can be called from Module 1
- ✅ Tracing decorators work with async functions
- ✅ Health checks don't block message processing
- ✅ Logging doesn't impact performance

---

## Integration Points

### **Depends On:**
- **Module 1** (Core Consumer) - Integrates metrics/tracing hooks

### **Depended On By:**
- External monitoring systems (Prometheus, Grafana, Jaeger UI)

### **Interface Contract:**
```python
# Module 1 integration pattern:

# 1. Import metrics and tracing
from src.monitoring.metrics import MetricsCollector
from src.monitoring.tracing import tracer
from src.monitoring.logging import logger

# 2. Record metrics
MetricsCollector.record_message_consumed(queue_name)
MetricsCollector.record_processing_complete(
    record_type, duration, status, quality_score
)

# 3. Add tracing
with tracer.start_as_current_span("process_message") as span:
    span.set_attribute("record_type", record_type)
    # ... processing ...

# 4. Structured logging
log = logger.bind(correlation_id=correlation_id)
log.info("processing_started")
```

---

## Notes & Considerations

1. **Jaeger Reuse**: Using existing Jaeger from webauthn-stack avoids duplicate infrastructure. Ensure webauthn-stack is running.

2. **Metrics Cardinality**: Be careful with high-cardinality labels (e.g., user_id). Use only for low-cardinality dimensions.

3. **Performance**: Metrics and tracing add minimal overhead (<5ms per operation). Use sampling for tracing if needed.

4. **Alerting**: Metrics endpoint enables alerting via Prometheus AlertManager (not implemented in this module).

5. **Log Retention**: Structured logs can grow large. Configure log rotation and retention policies.

---

**End of Module 5 Specification**
