# Module 1: Core Message Consumer & Infrastructure

**Module ID:** ETL-M1
**Priority:** P0 (Foundation - Must implement first)
**Estimated Effort:** 1.5 weeks
**Dependencies:** None
**Team Assignment:** Backend/Infrastructure Developer

---

## Module Overview

This module implements the foundational message consumption infrastructure for the ETL Narrative Engine. It provides the core plumbing that receives messages from RabbitMQ, manages deduplication, routes to clinical processors, and handles error recovery.

### Key Responsibilities
- RabbitMQ message consumption with reliable delivery
- Persistent deduplication (SQLite for single instance, Redis for distributed)
- Message routing to appropriate clinical processors
- Error classification and retry logic
- S3 file download from MinIO
- Configuration management (Pydantic settings)

### What This Module Does NOT Include
- ❌ Clinical processing logic (Module 3)
- ❌ Data validation (Module 2)
- ❌ Training data output (Module 4)
- ❌ Observability setup (Module 5)
- ❌ Deployment configuration (Module 6)

---

## Interfaces Provided

### **1. Processor Interface**
```python
# src/processors/base_processor.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class ProcessingResult:
    """Result returned by clinical processors"""
    success: bool
    narrative: str | None = None
    error_message: str | None = None
    processing_time_seconds: float = 0.0
    records_processed: int = 0
    quality_score: float = 1.0
    clinical_insights: Dict[str, Any] | None = None

class BaseClinicalProcessor(ABC):
    """Interface that all clinical processors must implement"""

    @abstractmethod
    async def process_with_clinical_insights(
        self,
        records: List[Dict[str, Any]],
        message_data: Dict[str, Any],
        validation_result: Any
    ) -> ProcessingResult:
        """Process records and return clinical narrative"""
        pass

    @abstractmethod
    async def initialize(self):
        """Initialize processor-specific configurations"""
        pass
```

**Contract:**
- Processors implementing this interface will be called by the consumer
- Consumer passes: `records`, `message_data`, `validation_result`
- Processor returns: `ProcessingResult` with narrative or error
- Consumer handles success/failure based on `result.success`

### **2. Deduplication Service**
```python
# src/consumer/deduplication.py
class DeduplicationStore:
    """Interface for deduplication storage"""

    async def is_already_processed(self, idempotency_key: str) -> bool:
        """Check if message already processed"""
        pass

    async def mark_processing_started(
        self, message_data: Dict, idempotency_key: str
    ) -> None:
        """Mark message as processing started"""
        pass

    async def mark_processing_completed(
        self, idempotency_key: str, processing_time: float,
        records_processed: int, narrative: str
    ) -> None:
        """Mark message as successfully processed"""
        pass

    async def mark_processing_failed(
        self, idempotency_key: str, error_message: str, error_type: str
    ) -> None:
        """Mark message as failed"""
        pass
```

**Contract:**
- Other modules can query deduplication status
- Deduplication store is injected into consumer
- Supports both SQLite (single instance) and Redis (distributed)

---

## Technical Specifications

### 1. Message Consumption

**Input Message Format** (from RabbitMQ):
```json
{
  "message_id": "uuid-v4",
  "correlation_id": "upload-correlation-id",
  "user_id": "user-identifier",
  "bucket": "health-data",
  "key": "raw/BloodGlucoseRecord/2025/11/15/user123_1731628800_abc123.avro",
  "record_type": "BloodGlucoseRecord",
  "upload_timestamp_utc": "2025-11-15T12:00:00Z",
  "content_hash": "sha256-hash",
  "file_size_bytes": 38664,
  "record_count": 287,
  "idempotency_key": "hash-based-key",
  "priority": "normal",
  "retry_count": 0
}
```

**Queue Configuration:**
- Queue: `health_data_processing`
- Exchange: `health_data_exchange` (topic)
- Routing Key: `health.processing.{record_type}.{priority}`
- Prefetch Count: 1 (fair distribution)
- Auto-ACK: **False** (manual ACK after successful processing)

### 2. Processing Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Receive Message from RabbitMQ                               │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. Check Deduplication                                          │
│    - Query dedup store with idempotency_key                     │
│    - If processed: ACK message, return                          │
│    - Else: Mark as "processing_started"                         │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. Download File from S3                                        │
│    - Use bucket + key from message                              │
│    - Stream to memory (or temp file if large)                   │
│    - Handle S3 errors (retry on network issues)                 │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. Parse Avro File                                              │
│    - Extract records using fastavro                             │
│    - Return list of record dictionaries                         │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. Get Validator (Module 2 interface)                           │
│    - Call validation interface                                  │
│    - Pass records for quality check                             │
│    - Get ValidationResult                                       │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. Route to Processor (Module 3 interface)                      │
│    - Select processor based on record_type                      │
│    - Call process_with_clinical_insights()                      │
│    - Get ProcessingResult                                       │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. Handle Result                                                │
│    - If success: Call output formatter (Module 4)               │
│    - If failure: Classify error, retry or DLQ                   │
│    - Update deduplication store                                 │
│    - ACK or NACK message                                        │
└─────────────────────────────────────────────────────────────────┘
```

### 3. Deduplication Implementation

**SQLite Schema:**
```sql
CREATE TABLE processed_messages (
    idempotency_key TEXT PRIMARY KEY,
    message_id TEXT NOT NULL,
    correlation_id TEXT,
    user_id TEXT,
    record_type TEXT,
    s3_key TEXT,

    -- Processing status
    status TEXT NOT NULL,  -- 'processing_started', 'completed', 'failed'
    error_message TEXT,
    error_type TEXT,

    -- Timestamps
    started_at REAL NOT NULL,
    completed_at REAL,

    -- Processing results
    processing_time_seconds REAL,
    records_processed INTEGER,
    quality_score REAL,
    narrative_preview TEXT,  -- First 200 chars

    -- Retention
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL  -- Auto-cleanup after 7 days
);

CREATE INDEX idx_status ON processed_messages(status);
CREATE INDEX idx_expires_at ON processed_messages(expires_at);
CREATE INDEX idx_user_id ON processed_messages(user_id);
```

**Redis Keys (for distributed deployment):**
```
etl:processed:{idempotency_key} → JSON of processing record
etl:status:{idempotency_key} → processing_started|completed|failed
TTL: 7 days (168 hours)
```

### 4. Error Classification

```python
# src/consumer/error_recovery.py
from enum import Enum

class ErrorType(Enum):
    # Retriable errors
    NETWORK_ERROR = "network_error"          # S3 timeout, connection lost
    TEMPORARY_ERROR = "temporary_error"      # Transient issues
    RATE_LIMIT = "rate_limit"               # S3 rate limiting

    # Non-retriable errors
    DATA_QUALITY_ERROR = "data_quality"      # Low quality (quarantine)
    SCHEMA_ERROR = "schema_error"            # Invalid Avro schema
    PROCESSING_ERROR = "processing_error"    # Processor logic error
    NOT_FOUND_ERROR = "not_found"           # S3 object not found

class ErrorRecoveryManager:
    """Classify errors and determine retry strategy"""

    def classify_error(self, exception: Exception) -> ErrorType:
        """Classify exception into error type"""
        if isinstance(exception, S3TimeoutError):
            return ErrorType.NETWORK_ERROR
        elif isinstance(exception, S3RateLimitError):
            return ErrorType.RATE_LIMIT
        elif isinstance(exception, DataQualityError):
            return ErrorType.DATA_QUALITY_ERROR
        # ... more classifications
        return ErrorType.PROCESSING_ERROR

    def should_retry(self, error_type: ErrorType, retry_count: int) -> bool:
        """Determine if error should be retried"""
        retriable = error_type in [
            ErrorType.NETWORK_ERROR,
            ErrorType.TEMPORARY_ERROR,
            ErrorType.RATE_LIMIT
        ]
        return retriable and retry_count < MAX_RETRIES

    def get_retry_delay(self, retry_count: int) -> int:
        """Get delay in seconds for retry"""
        delays = [30, 300, 900]  # 30s, 5m, 15m
        return delays[min(retry_count, len(delays)-1)]
```

**Retry Strategy:**
- Retriable errors: Network, temporary, rate limit
- Non-retriable: Data quality, schema errors, processor errors
- Max retries: 3
- Delays: 30s, 5m, 15m (exponential backoff)
- After max retries: Dead letter queue

### 5. Configuration

```python
# src/config/settings.py
from pydantic_settings import BaseSettings
from typing import List
from enum import Enum

class DeduplicationStore(str, Enum):
    SQLITE = "sqlite"
    REDIS = "redis"

class ConsumerSettings(BaseSettings):
    # Service
    service_name: str = "etl-narrative-engine"
    version: str = "v3.0"

    # Message Queue
    rabbitmq_url: str
    queue_name: str = "health_data_processing"
    exchange_name: str = "health_data_exchange"
    prefetch_count: int = 1
    max_retries: int = 3
    retry_delays: List[int] = [30, 300, 900]

    # Storage (S3/MinIO)
    s3_endpoint_url: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket_name: str
    s3_region: str = "us-east-1"

    # Deduplication
    deduplication_store: DeduplicationStore = DeduplicationStore.SQLITE
    deduplication_db_path: str = "/data/etl_processed_messages.db"
    deduplication_redis_url: str = "redis://redis:6379/2"
    deduplication_retention_hours: int = 168  # 7 days

    # Processing
    max_file_size_mb: int = 100
    processing_timeout_seconds: int = 300

    class Config:
        env_file = ".env"
        env_prefix = "ETL_"

settings = ConsumerSettings()
```

---

## Implementation Checklist

### Week 1: Core Infrastructure
- [ ] Set up project structure (`src/consumer/`, `src/config/`, `src/processors/`)
- [ ] Implement Pydantic settings with environment variables
- [ ] Create `BaseClinicalProcessor` abstract interface
- [ ] Implement SQLite deduplication store
  - [ ] Database schema
  - [ ] CRUD operations
  - [ ] Cleanup task (expired records)
- [ ] Implement Redis deduplication store (alternative)
- [ ] Write deduplication tests

### Week 1.5-2: Message Consumer
- [ ] Implement RabbitMQ consumer
  - [ ] Connection management (robust connection)
  - [ ] Message parsing
  - [ ] Prefetch configuration
- [ ] Implement S3 file download
  - [ ] aioboto3 client setup
  - [ ] Streaming download
  - [ ] Error handling
- [ ] Implement Avro parsing
  - [ ] fastavro integration
  - [ ] Record extraction
- [ ] Implement processor routing
  - [ ] Processor factory (stub for now)
  - [ ] Dynamic processor selection
- [ ] Implement error recovery
  - [ ] Error classification
  - [ ] Retry logic
  - [ ] Dead letter queue handling
- [ ] Write consumer tests
  - [ ] Deduplication flow
  - [ ] Retry mechanism
  - [ ] Error handling

---

## Testing Strategy

### Unit Tests
```python
# tests/test_deduplication.py
@pytest.mark.asyncio
async def test_deduplication_prevents_reprocessing():
    """Verify messages are not reprocessed"""
    store = DeduplicationStore(db_path=":memory:")
    await store.initialize()

    key = "test_key_123"

    # First check - should be new
    assert await store.is_already_processed(key) is False

    # Mark as started
    await store.mark_processing_started({}, key)

    # Second check - should be processing
    assert await store.is_already_processed(key) is True

    # Mark as completed
    await store.mark_processing_completed(key, 2.5, 100, "narrative")

    # Third check - should still be processed
    assert await store.is_already_processed(key) is True

@pytest.mark.asyncio
async def test_error_classification():
    """Verify errors are classified correctly"""
    manager = ErrorRecoveryManager()

    # Network error should be retriable
    error = S3TimeoutError()
    error_type = manager.classify_error(error)
    assert error_type == ErrorType.NETWORK_ERROR
    assert manager.should_retry(error_type, 0) is True

    # Schema error should not be retriable
    error = SchemaError()
    error_type = manager.classify_error(error)
    assert error_type == ErrorType.SCHEMA_ERROR
    assert manager.should_retry(error_type, 0) is False

@pytest.mark.asyncio
async def test_retry_delay_exponential_backoff():
    """Verify retry delays increase exponentially"""
    manager = ErrorRecoveryManager()

    assert manager.get_retry_delay(0) == 30   # 30s
    assert manager.get_retry_delay(1) == 300  # 5m
    assert manager.get_retry_delay(2) == 900  # 15m
```

### Integration Tests
```python
# tests/test_consumer_integration.py
@pytest.mark.integration
@pytest.mark.asyncio
async def test_consumer_processes_message_end_to_end(
    rabbitmq_container,
    minio_container,
    dedup_store
):
    """Test complete message processing flow"""

    # 1. Upload test file to MinIO
    test_file = "docs/sample-avro-files/BloodGlucoseRecord_1758407139312.avro"
    await upload_to_minio(minio_container, test_file)

    # 2. Publish message to RabbitMQ
    message = create_test_message(record_type="BloodGlucoseRecord")
    await publish_message(rabbitmq_container, message)

    # 3. Start consumer (mock processor returns success)
    consumer = ETLConsumer()
    consumer.processor_factory = MockProcessorFactory()

    # 4. Process message
    await consumer.start_consuming()
    await asyncio.sleep(2)  # Allow processing

    # 5. Verify deduplication store updated
    assert await dedup_store.is_already_processed(message['idempotency_key'])

    # 6. Verify message acknowledged
    queue_depth = await get_queue_depth(rabbitmq_container)
    assert queue_depth == 0
```

---

## Dependencies

### Python Packages
```txt
aio-pika==9.4.0              # RabbitMQ
aioboto3==12.3.0             # S3
aiosqlite==0.19.0            # SQLite
redis==5.0.3                 # Redis (optional)
fastavro==1.9.3              # Avro parsing
pydantic-settings==2.1.0     # Configuration
structlog==24.1.0            # Logging
tenacity==8.2.3              # Retry logic
```

### External Services
- RabbitMQ (localhost:5672)
- MinIO (localhost:9000)
- Redis (localhost:6379) - optional, for distributed deployment

---

## Success Criteria

**Module Complete When:**
- ✅ Consumer connects to RabbitMQ and receives messages
- ✅ Deduplication prevents duplicate processing (SQLite + Redis implementations)
- ✅ S3 files downloaded successfully
- ✅ Avro records extracted correctly
- ✅ Messages routed to processor interface
- ✅ Errors classified and retried appropriately
- ✅ Unit tests: >80% coverage
- ✅ Integration tests: End-to-end flow verified
- ✅ Documentation: Interfaces clearly documented

**Ready for Integration When:**
- ✅ `BaseClinicalProcessor` interface stable and documented
- ✅ Deduplication service interface defined
- ✅ Error types and retry logic working
- ✅ Other modules can implement against interfaces

---

## Integration Points

### **Depends On:**
- None (foundation module)

### **Depended On By:**
- **Module 2** (Validation Framework) - Consumer calls validation interface
- **Module 3** (Clinical Processors) - Consumer routes to processors
- **Module 4** (Training Data Output) - Consumer calls output formatter
- **Module 5** (Observability) - Consumer emits metrics/traces

### **Interface Contracts:**
See "Interfaces Provided" section for complete contracts.

---

## Notes & Considerations

1. **Processor Factory**: Initially create stub factory that returns mock processors. Real processors come from Module 3.

2. **Validation Integration**: Stub validation for now. Module 2 will provide real validation.

3. **Output Integration**: Don't implement output writing yet. Module 4 handles that.

4. **Metrics**: Add hooks for metrics, but actual Prometheus setup is in Module 5.

5. **Testing**: Use mock processors in tests until Module 3 is ready.

6. **Configuration**: Make all settings configurable via environment variables for easy integration testing.

---

**End of Module 1 Specification**
