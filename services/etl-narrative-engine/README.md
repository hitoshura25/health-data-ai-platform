# ETL Narrative Engine - Module 1: Core Consumer & Infrastructure

**Status:** ✅ Module 1 Complete
**Version:** v3.0
**Last Updated:** 2025-11-17

---

## Overview

The ETL Narrative Engine transforms raw health data from Android Health Connect (Avro format) into clinically meaningful narratives and structured training data for AI model development.

**Module 1** provides the foundational infrastructure:
- RabbitMQ message consumption with reliable delivery
- Persistent deduplication (SQLite for single instance, Redis for distributed)
- Message routing to clinical processors
- Error classification and retry logic
- S3 file download from MinIO
- Avro record parsing

---

## Module 1 Implementation Status

### ✅ Completed Components

- [x] **Configuration** (`src/config/settings.py`)
  - Pydantic settings with environment variables
  - Support for both SQLite and Redis deduplication

- [x] **Base Processor Interface** (`src/processors/base_processor.py`)
  - Abstract `BaseClinicalProcessor` class
  - `ProcessingResult` dataclass
  - Error exception classes

- [x] **Processor Factory** (`src/processors/processor_factory.py`)
  - Mock processors for all 6 health data types
  - Dynamic processor selection
  - Lifecycle management

- [x] **Deduplication Stores** (`src/consumer/deduplication.py`)
  - SQLite implementation with schema and CRUD operations
  - Redis implementation with TTL-based expiration
  - Cleanup task for expired records

- [x] **Error Recovery** (`src/consumer/error_recovery.py`)
  - Error classification (retriable vs non-retriable)
  - Exponential backoff retry logic
  - Quarantine and DLQ routing

- [x] **S3 Client** (`src/storage/s3_client.py`)
  - Async file download with retry
  - Error handling for network, auth, and rate limit issues
  - Support for MinIO and S3

- [x] **Avro Parser** (`src/storage/avro_parser.py`)
  - Efficient parsing with fastavro
  - Schema validation
  - Record statistics

- [x] **Main Consumer** (`src/consumer/etl_consumer.py`)
  - RabbitMQ connection with automatic reconnection
  - Message processing pipeline
  - Deduplication checks
  - Processor routing
  - Error handling and retry

- [x] **Tests**
  - Unit tests for deduplication (`tests/test_deduplication.py`)
  - Unit tests for error recovery (`tests/test_error_recovery.py`)
  - Unit tests for processors (`tests/test_processor_factory.py`)

---

## Quick Start

### Prerequisites

- Python 3.11+
- Virtual environment activated
- Docker (for RabbitMQ, MinIO, Redis)

### Installation

```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies
cd services/etl-narrative-engine
pip install -r requirements.txt
```

### Configuration

Create `.env` file:

```bash
cp .env.example .env
# Edit .env with your configuration
```

### Running Tests

```bash
# Run linting (recommended before tests)
ruff check src/ tests/

# Run all unit tests
pytest

# Run linting and tests together
ruff check src/ tests/ && pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_deduplication.py -v

# Auto-fix linting issues
ruff check src/ tests/ --fix

# Use project-wide test runner (from repo root)
cd ../..
./run-tests.sh etl-narrative-engine -v
```

### Starting the Service (Development)

```bash
# Start infrastructure
docker compose up -d rabbitmq minio redis

# Run the consumer
python -m src.main
```

---

## Architecture

### Message Processing Flow

```
RabbitMQ Message
    ↓
Deduplication Check
    ↓ (if not processed)
Download Avro from S3
    ↓
Parse Avro Records
    ↓
Validation (Module 2 - stub for now)
    ↓
Clinical Processing (Module 3 - mock for now)
    ↓
Training Data Output (Module 4 - not yet implemented)
    ↓
Mark Complete & ACK
```

### Error Handling

```
Error Detected
    ↓
Classify Error Type
    ↓
├─ Retriable? (network, timeout, rate limit)
│  ├─ Yes → Retry with exponential backoff
│  └─ No → Dead Letter Queue
│
├─ Data Quality/Schema Error?
│  └─ Yes → Quarantine with metadata
│
└─ Auth Error?
   └─ Yes → Critical Alert
```

---

## Environment Variables

All settings use `ETL_` prefix. See `.env.example` for complete list.

**Key Settings:**

- `ETL_RABBITMQ_URL`: RabbitMQ connection string
- `ETL_S3_ENDPOINT_URL`: MinIO endpoint (default: `http://localhost:9000`)
- `ETL_DEDUPLICATION_STORE`: `sqlite` or `redis`
- `ETL_DEDUPLICATION_DB_PATH`: SQLite database path
- `ETL_MAX_RETRIES`: Maximum retry attempts (default: 3)

---

## Testing Strategy

### Unit Tests
- Mock external dependencies
- Test business logic in isolation
- Fast execution (<1s per test)

### Integration Tests (Future)
- Require Docker services (RabbitMQ, MinIO, Redis)
- Test end-to-end message processing
- Verify deduplication works across restarts

---

## Module Integration Points

### Provided Interfaces

**For Module 2 (Validation):**
- Consumer calls validation interface (currently stubbed)

**For Module 3 (Clinical Processors):**
- `BaseClinicalProcessor` interface to implement
- `ProcessorFactory` routes to real processors

**For Module 4 (Training Data Output):**
- Consumer provides processed results for output formatting

**For Module 5 (Observability):**
- Logging hooks for metrics and tracing

---

## Next Steps (Module 2+)

- [ ] **Module 2**: Implement data validation framework
- [ ] **Module 3**: Implement clinical processors (BloodGlucose, HeartRate, etc.)
- [ ] **Module 4**: Implement training data output (JSONL formatting)
- [ ] **Module 5**: Add observability (Prometheus metrics, Jaeger tracing)
- [ ] **Module 6**: Create deployment configuration (Docker, docker-compose)

---

## Success Criteria

Module 1 is complete when:

- ✅ Consumer connects to RabbitMQ and receives messages
- ✅ Deduplication prevents duplicate processing (SQLite + Redis)
- ✅ S3 files downloaded successfully
- ✅ Avro records extracted correctly
- ✅ Messages routed to processor interface
- ✅ Errors classified and retried appropriately
- ✅ Unit tests: >80% coverage
- ✅ Interfaces documented for other modules

---

## Development Guidelines

### Adding New Processor

1. Create processor class inheriting from `BaseClinicalProcessor`
2. Implement `initialize()` and `process_with_clinical_insights()`
3. Add to `ProcessorFactory.SUPPORTED_TYPES`
4. Register in `ProcessorFactory.initialize()`
5. Write unit tests

### Error Handling

- Use specific exception classes from `error_recovery.py`
- Let consumer handle retry logic
- Log with structured logging (structlog)
- Include correlation_id in all logs

### Testing

- Mark tests with `@pytest.mark.unit` or `@pytest.mark.integration`
- Use fixtures from `conftest.py`
- Mock external services for unit tests
- Use Docker for integration tests

---

## Troubleshooting

### Consumer Not Starting

```bash
# Check RabbitMQ is running
docker ps | grep rabbitmq

# Check logs
docker compose logs rabbitmq
```

### Deduplication Errors

```bash
# Check SQLite database
ls -lh /data/etl_processed_messages.db

# Check Redis connection
redis-cli -h localhost -p 6379 ping
```

### S3 Download Failures

```bash
# Check MinIO is running
docker ps | grep minio

# Test S3 access
aws s3 --endpoint-url http://localhost:9000 ls s3://health-data/
```

---

## References

- **Module 1 Spec**: `specs/etl-modules/module-1-core-consumer.md`
- **Main Spec**: `specs/etl-narrative-engine-spec-v3.md`
- **Project Guidelines**: `CLAUDE.md`

---

**Module 1 Status:** ✅ Complete and ready for Module 2 integration
