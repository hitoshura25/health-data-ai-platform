# ETL Narrative Engine - Module Integration Guide

**Version:** 1.0
**Last Updated:** 2025-11-15
**Purpose:** Guide for integrating independently developed modules

---

## Overview

This guide explains how the 6 independently developed ETL modules integrate together to form the complete ETL Narrative Engine. Each module has been designed with clear interfaces to enable parallel development while ensuring seamless integration.

---

## Module Dependency Graph

```
┌─────────────────────────────────────────────────────────────────┐
│                        Integration Flow                          │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────┐     ┌──────────────────────┐
│ Module 6:            │     │ Module 5:            │
│ Deployment &         │     │ Observability        │
│ Infrastructure       │     │                      │
└──────────┬───────────┘     └──────────┬───────────┘
           │                            │
           │ (provides runtime)         │ (provides hooks)
           │                            │
           ▼                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ Module 1: Core Message Consumer & Infrastructure (Foundation)   │
│ - RabbitMQ consumption                                          │
│ - Deduplication (SQLite/Redis)                                  │
│ - Message routing                                               │
│ - Error recovery                                                │
└───────────┬─────────────────────────────────────────────────────┘
            │
            │ (calls interfaces)
            │
            ├────────────────┬────────────────┬───────────────────┐
            │                │                │                   │
            ▼                ▼                ▼                   ▼
┌───────────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ Module 2:         │ │ Module 3a:  │ │ Module 3b:  │ │ Module 3c/d:│
│ Validation        │ │ Blood       │ │ Heart Rate  │ │ Sleep/      │
│ Framework         │ │ Glucose     │ │ Processor   │ │ Others      │
│                   │ │ Processor   │ │             │ │             │
└───────┬───────────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
        │                    │               │               │
        │ (provides result)  │ (provides)    │ (provides)    │ (provides)
        │                    │               │               │
        ▼                    ▼               ▼               ▼
        └────────────────────┴───────────────┴───────────────┘
                             │
                             │ (all feed into)
                             ▼
                    ┌─────────────────┐
                    │ Module 4:       │
                    │ Training Data   │
                    │ Output          │
                    └─────────────────┘
```

---

## Phase 1: Foundation Modules (Week 1-2)

### Module 1 + Module 2 + Module 6 (Parallel Development)

**Goal:** Establish the foundation infrastructure that other modules will build upon.

### Integration Steps

1. **Module 1 (Core Consumer) provides stub interfaces:**
   ```python
   # src/processors/base_processor.py
   class BaseClinicalProcessor(ABC):
       """Stub interface for processors (real implementation in Module 3)"""
       @abstractmethod
       async def process_with_clinical_insights(...) -> ProcessingResult:
           pass
   ```

2. **Module 2 (Validation) provides validation interface:**
   ```python
   # src/validation/data_quality.py
   class DataQualityValidator:
       async def validate(...) -> ValidationResult:
           # Real implementation
           pass
   ```

3. **Module 1 calls Module 2:**
   ```python
   # In consumer (Module 1)
   from src.validation.data_quality import DataQualityValidator

   validator = DataQualityValidator(quality_threshold=0.7)
   validation_result = await validator.validate(records, record_type, file_size)

   if not validation_result.is_valid:
       await validator.quarantine_file(s3_key, validation_result, file_content)
       return  # Stop processing
   ```

4. **Module 6 (Deployment) provides:**
   - Docker configuration
   - docker-compose.yml
   - Local development scripts
   - Environment variable templates

**Integration Test:**
- Module 1 + Module 2: Process sample file, validate, quarantine low-quality data
- Module 6: Bring up stack with `docker compose up`

---

## Phase 2: Processor Modules (Week 2-4)

### Module 3a/3b/3c/3d (Highly Parallel Development)

**Goal:** Implement clinical processing logic for all 6 health data types.

### Integration Pattern (Same for all processor modules)

1. **Each processor implements `BaseClinicalProcessor`:**
   ```python
   # Module 3a: src/processors/blood_glucose_processor.py
   from src.processors.base_processor import BaseClinicalProcessor, ProcessingResult

   class BloodGlucoseProcessor(BaseClinicalProcessor):
       async def initialize(self):
           # Setup clinical ranges
           pass

       async def process_with_clinical_insights(
           self, records, message_data, validation_result
       ) -> ProcessingResult:
           # Implement glucose-specific logic
           return ProcessingResult(
               success=True,
               narrative="Generated narrative...",
               clinical_insights={...}
           )
   ```

2. **Module 1 registers processors via factory:**
   ```python
   # src/processors/processor_factory.py (in Module 1 or Module 3)
   class ProcessorFactory:
       def __init__(self):
           self.processors = {
               'BloodGlucoseRecord': BloodGlucoseProcessor(),  # Module 3a
               'HeartRateRecord': HeartRateProcessor(),        # Module 3b
               'SleepSessionRecord': SleepProcessor(),         # Module 3c
               'StepsRecord': StepsProcessor(),                # Module 3d
               # ... others from Module 3d
           }

       def get_processor(self, record_type: str) -> BaseClinicalProcessor:
           return self.processors.get(record_type, GenericProcessor())
   ```

3. **Module 1 consumer calls processor:**
   ```python
   # In consumer (Module 1)
   factory = ProcessorFactory()
   processor = factory.get_processor(message_data['record_type'])

   result = await processor.process_with_clinical_insights(
       records, message_data, validation_result
   )

   if result.success:
       # Pass to Module 4 for output
       await output_formatter.generate_training_output(
           result.narrative, message_data, result.clinical_insights
       )
   ```

**Integration Test (per processor):**
- Load sample file for specific record type
- Validate (Module 2)
- Process (Module 3x)
- Verify narrative generated
- Verify clinical insights structure

---

## Phase 3: Output Module (Week 3-4)

### Module 4 (Training Data Output)

**Goal:** Generate JSONL training data from processor narratives.

### Integration Steps

1. **Module 4 provides output interface:**
   ```python
   # src/output/training_formatter.py
   class TrainingDataFormatter:
       async def generate_training_output(
           self,
           narrative: str,
           source_metadata: Dict[str, Any],
           processing_metadata: Dict[str, Any]
       ) -> bool:
           # Generate JSONL entry
           # Upload to S3
           pass
   ```

2. **Module 1 calls Module 4 after successful processing:**
   ```python
   # In consumer (Module 1)
   if processing_result.success:
       formatter = TrainingDataFormatter()
       success = await formatter.generate_training_output(
           narrative=processing_result.narrative,
           source_metadata={
               'bucket': message_data['bucket'],
               'key': message_data['key'],
               'record_type': message_data['record_type'],
               'user_id': message_data['user_id'],
               'correlation_id': message_data['correlation_id']
           },
           processing_metadata={
               'duration': processing_result.processing_time_seconds,
               'record_count': len(records),
               'quality_score': validation_result.quality_score,
               'clinical_insights': processing_result.clinical_insights
           }
       )
   ```

3. **Module 4 writes to S3:**
   ```
   training/
   ├── metabolic_diabetes/2025/11/health_journal_2025_11.jsonl
   ├── cardiovascular_fitness/2025/11/health_journal_2025_11.jsonl
   └── ...
   ```

**Integration Test:**
- Process sample file end-to-end
- Verify JSONL file created in S3
- Verify JSONL format is valid
- Verify metadata includes all required fields

---

## Phase 4: Observability Module (Week 3-5)

### Module 5 (Observability)

**Goal:** Add metrics, tracing, and health checks without modifying core logic.

### Integration Strategy

1. **Module 5 provides decorator/hook functions:**
   ```python
   # src/monitoring/metrics.py
   from prometheus_client import Counter, Histogram

   messages_processed = Counter('etl_messages_processed_total', ...)
   processing_duration = Histogram('etl_processing_duration_seconds', ...)

   def record_processing_metrics(record_type: str, duration: float, status: str):
       messages_processed.labels(record_type=record_type, status=status).inc()
       processing_duration.labels(record_type=record_type).observe(duration)
   ```

2. **Module 1 calls metrics hooks:**
   ```python
   # In consumer (Module 1)
   from src.monitoring.metrics import record_processing_metrics

   start_time = time.time()
   result = await processor.process_with_clinical_insights(...)
   duration = time.time() - start_time

   record_processing_metrics(
       record_type=message_data['record_type'],
       duration=duration,
       status='success' if result.success else 'failed'
   )
   ```

3. **Module 5 provides tracing setup:**
   ```python
   # src/monitoring/tracing.py
   from opentelemetry import trace

   tracer = trace.get_tracer(__name__)

   def setup_tracing():
       # Configure Jaeger
       pass
   ```

4. **Module 1 uses tracing:**
   ```python
   # In consumer (Module 1)
   from src.monitoring.tracing import tracer

   with tracer.start_as_current_span("process_message") as span:
       span.set_attribute("record_type", record_type)
       result = await process_health_data(...)
   ```

5. **Module 5 provides health check:**
   ```python
   # src/monitoring/health.py
   @app.get("/health")
   async def health_check():
       return {
           "status": "healthy",
           "rabbitmq_connected": True,
           "s3_accessible": True
       }
   ```

**Integration Test:**
- Process sample file
- Verify metrics exported on `/metrics`
- Verify traces appear in Jaeger UI
- Verify `/health` endpoint returns 200

---

## Integration Checklist

### Phase 1 Complete When:
- [ ] Module 1 can consume messages from RabbitMQ
- [ ] Module 2 can validate sample Avro files
- [ ] Module 1 calls Module 2 validation
- [ ] Low-quality files are quarantined
- [ ] Module 6 Docker stack brings up all services
- [ ] Integration test: Message → Validation → Quarantine works

### Phase 2 Complete When:
- [ ] All processor modules (3a, 3b, 3c, 3d) implement `BaseClinicalProcessor`
- [ ] Processor factory routes to correct processor
- [ ] Module 1 can call any processor
- [ ] Integration test: Each processor generates valid narratives
- [ ] Integration test: Unknown record types handled gracefully

### Phase 3 Complete When:
- [ ] Module 4 generates JSONL training data
- [ ] Module 1 calls Module 4 after successful processing
- [ ] Training files appear in S3 `training/` prefix
- [ ] Integration test: End-to-end pipeline produces JSONL
- [ ] JSONL format validated (instruction + output + metadata)

### Phase 4 Complete When:
- [ ] Module 5 metrics are collected during processing
- [ ] Prometheus metrics endpoint working (`/metrics`)
- [ ] Jaeger traces visible in UI
- [ ] Health check endpoint working (`/health`)
- [ ] Integration test: Metrics update during processing
- [ ] Integration test: Traces captured for sample processing

### Phase 5 Complete When (Full Integration):
- [ ] All 26 sample files process successfully
- [ ] Deduplication prevents reprocessing
- [ ] All 6 record types produce training data
- [ ] Metrics captured for all processing
- [ ] Quarantine works for invalid files
- [ ] Health checks pass
- [ ] Performance: 500 records in <5 seconds
- [ ] No data loss (all messages accounted for)

---

## Integration Testing Strategy

### 1. Module-Level Integration (during development)

Each module should have integration tests that verify its contract:

**Module 1:**
```bash
pytest tests/test_consumer_integration.py
# Tests: RabbitMQ → Consumer → Deduplication → (Mock) Processor
```

**Module 2:**
```bash
pytest tests/test_validation_integration.py
# Tests: Sample Avro files → Validation → Quality score
```

**Module 3a:**
```bash
pytest tests/test_blood_glucose_integration.py
# Tests: Sample glucose file → Processor → Narrative
```

### 2. Cross-Module Integration (Phase 3)

**Consumer + Validation:**
```bash
pytest tests/integration/test_consumer_validation.py
# Tests: Message → Download → Validate → Quarantine
```

**Consumer + Processor:**
```bash
pytest tests/integration/test_consumer_processor.py
# Tests: Message → Download → Validate → Process → Narrative
```

**Consumer + Output:**
```bash
pytest tests/integration/test_consumer_output.py
# Tests: Message → Process → Output JSONL
```

### 3. End-to-End Integration (Phase 5)

**Full Pipeline:**
```bash
pytest tests/integration/test_full_pipeline.py
# Tests: All 26 sample files through complete pipeline
```

**Load Testing:**
```bash
pytest tests/integration/test_load.py
# Tests: Process 100 messages concurrently
```

---

## Common Integration Issues & Solutions

### Issue 1: Import Path Conflicts
**Problem:** Modules can't import each other's code
**Solution:** Use absolute imports from project root:
```python
# ❌ Wrong
from ..validation.data_quality import DataQualityValidator

# ✅ Correct
from src.validation.data_quality import DataQualityValidator
```

### Issue 2: Interface Mismatches
**Problem:** Module 1 expects different signature than Module 3 provides
**Solution:**
1. Freeze interface contracts early (Week 1)
2. Use type hints and mypy for validation
3. Create integration tests that verify contracts

### Issue 3: Circular Dependencies
**Problem:** Module A imports Module B which imports Module A
**Solution:**
1. Keep dependencies one-directional (see dependency graph)
2. Use dependency injection instead of direct imports
3. Define interfaces in neutral location (e.g., `src/interfaces/`)

### Issue 4: Configuration Conflicts
**Problem:** Different modules need different environment variables
**Solution:**
1. Use single `settings.py` with all configurations
2. Use prefixes to avoid conflicts (e.g., `ETL_`, `METRICS_`)
3. Make Module 1's settings include all module configs

### Issue 5: Testing Isolation
**Problem:** Integration tests interfere with each other
**Solution:**
1. Use pytest fixtures with proper scope
2. Clean up resources (S3 files, DB records) after each test
3. Use separate test queues/buckets per test

---

## Environment Configuration

**Complete `.env` file for all modules:**
```bash
# Module 1: Core Consumer
ETL_RABBITMQ_URL=amqp://guest:guest@localhost:5672
ETL_QUEUE_NAME=health_data_processing
ETL_S3_ENDPOINT_URL=http://localhost:9000
ETL_S3_ACCESS_KEY=minioadmin
ETL_S3_SECRET_KEY=minioadmin
ETL_S3_BUCKET_NAME=health-data
ETL_DEDUPLICATION_STORE=sqlite
ETL_DEDUPLICATION_DB_PATH=/data/etl_processed_messages.db
ETL_MAX_RETRIES=3

# Module 2: Validation
ETL_QUALITY_THRESHOLD=0.7
ETL_ENABLE_QUARANTINE=true

# Module 4: Training Data Output
ETL_TRAINING_DATA_PREFIX=training/
ETL_INCLUDE_METADATA=true

# Module 5: Observability
ETL_ENABLE_METRICS=true
ETL_METRICS_PORT=8004
ETL_ENABLE_JAEGER_TRACING=true
ETL_JAEGER_OTLP_ENDPOINT=http://localhost:4319
ETL_LOG_LEVEL=INFO

# Module 6: Deployment
ETL_DEVELOPMENT_MODE=true
```

---

## Release Strategy

### Week 5: Integration Testing
- Day 1-2: Module-pair integration (1+2, 1+3, 1+4, 1+5)
- Day 3: Full pipeline integration
- Day 4-5: Bug fixes and refinement

### Week 6: Production Readiness
- Day 1-2: Performance testing and optimization
- Day 3: Security review
- Day 4: Documentation review
- Day 5: Staging deployment and final testing

---

## Success Metrics

**Integration Successful When:**
- ✅ All 26 sample files process end-to-end
- ✅ Training JSONL files generated correctly
- ✅ No duplicate processing (deduplication works)
- ✅ Quarantine works for invalid data
- ✅ Metrics collected for all operations
- ✅ Health checks pass
- ✅ Performance targets met (<5s for 500 records)
- ✅ Zero data loss (all messages accounted for)
- ✅ Integration tests: >95% pass rate
- ✅ Documentation complete

---

## Contact Points (Example for Team)

For integration issues, contact module owners:

- **Module 1 (Core Consumer):** Developer A
- **Module 2 (Validation):** Developer B
- **Module 3a (Blood Glucose):** Developer C
- **Module 3b (Heart Rate):** Developer D
- **Module 3c (Sleep):** Developer E
- **Module 3d (Others):** Developer F
- **Module 4 (Training Data):** Developer G
- **Module 5 (Observability):** Developer H (DevOps)
- **Module 6 (Deployment):** Developer H (DevOps)

**Integration Lead:** [Assign someone to coordinate integration]

---

**End of Integration Guide**
