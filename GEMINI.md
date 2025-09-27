## Gemini Added Memories
- The project is a health data AI platform with the following services:
- `health-api-service`: A FastAPI service for health data upload and management.
- `message-queue`: A RabbitMQ-based message queue for asynchronous communication.
- `etl-narrative-engine`: An ETL worker that processes health data and generates clinical narratives.
- `data-lake`: A MinIO-based data lake for storing health data.
- `ai-query-interface`: A FastAPI service that provides a natural language query interface over the processed health data.

Implementation Plan Summaries:
- **Health API Service:** Uses FastAPI, `fastapi-users` with JWT, SQLAlchemy (Postgres/SQLite), `tenacity` for retries, `aioboto3` for MinIO, and `aio-pika` for RabbitMQ. Features secure authentication, rate limiting, and file validation.
- **Message Queue:** Uses RabbitMQ with Redis for deduplication and DLX/TTL for retries. Ensures reliable message delivery with rich metadata.
- **ETL Narrative Engine:** Consumes messages with `aio-pika`, processes data with Pandas/NumPy and specialized clinical processors, validates data quality with automatic quarantine, and outputs clinical narratives and JSONL training data. Features idempotent processing and advanced error recovery.
- **Data Lake:** Uses MinIO for storage with intelligent object naming and built-in lifecycle management. Includes application-level data quality validation, encryption, access controls, and analytics.
- **AI Query Interface:** A FastAPI service using MLflow for model management, featuring natural language query processing with conversation context and a structured feedback system for model improvement.

## Best Practices
**Don't commit to git**