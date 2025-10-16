# Message Queue Service

This service manages the message queue for the Health Data AI Platform using RabbitMQ and Redis. It is responsible for reliable message delivery, persistent deduplication, and intelligent retry logic for processing health data.

## Overview

- **RabbitMQ**: Used as the message broker for asynchronous communication between services.
- **Redis**: Used for performant, persistent deduplication to prevent processing the same message twice.
- **Intelligent Retries**: Uses a Dead Letter Exchange (DLX) and Time-To-Live (TTL) pattern for exponential backoff on message processing failures.

## Getting Started

These instructions will get the message queue service running locally for development and testing.

### Prerequisites

- Docker and Docker Compose
- Python 3.11+

### Setup and Running

1.  **Generate Environment Files**: The platform uses coordinated `.env` files for secure credential management across all services. From the **project root directory**, run the setup script:

    ```bash
    ./setup-all-services.sh
    ```

    This will generate:
    - Coordinated credentials for all infrastructure (PostgreSQL, Redis, RabbitMQ, MinIO)
    - Service-specific `.env` files with shared credentials
    - `.env` file at project root for docker-compose

2.  **Start Services**: With the `.env` files created, start the RabbitMQ and Redis containers from the **project root**:

    ```bash
    docker compose up -d rabbitmq redis
    ```

    You can now access the RabbitMQ Management UI at [http://localhost:15672](http://localhost:15672) using the credentials from `infrastructure/.env` (MQ_RABBITMQ_USER and MQ_RABBITMQ_PASS).

## Testing

Tests are located in the `tests/` directory and are designed to be run with `pytest`. Integration tests automatically manage their own Docker containers.

### Test Setup

1.  **Generate Environment Files**: First ensure you've run the setup script from the project root (see Setup and Running above).

2.  **Create a Virtual Environment** (if not already done): From the **project root**, create a shared virtual environment:

    ```bash
    python -m venv .venv
    ```

3.  **Activate Environment and Install Dependencies**:

    ```bash
    source .venv/bin/activate
    pip install -r services/message-queue/requirements.txt
    ```

### Running Tests

**From project root**, with the virtual environment activated:

```bash
# Run all message-queue tests
./run-tests.sh message-queue

# Run with verbose output
./run-tests.sh message-queue -v

# Run only unit tests (no Docker needed)
cd services/message-queue
pytest tests/test_message_queue_message.py tests/test_message_queue_deduplication.py
```

**Test types:**
- **Unit tests**: Use mocks, no Docker required
- **Integration tests**: Automatically start/stop Docker containers (RabbitMQ, Redis) via fixtures
