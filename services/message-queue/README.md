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

1.  **Generate Environment File**: The service uses a `.env` file for secure credential management. A script is provided to generate this for you. Navigate to this directory and run it once:

    ```bash
    bash setup-env.sh
    ```
    This will create a local `.env` file with a unique, secure username and password for RabbitMQ.

2.  **Start Services**: With the `.env` file created, start the RabbitMQ and Redis containers:

    ```bash
    docker-compose -f deployment/docker-compose.yml up -d
    ```

    You can now access the RabbitMQ Management UI at [http://localhost:15672](http://localhost:15672) using the credentials generated in your `.env` file.

## Testing

Tests are located in the `tests/` directory and are designed to be run with `pytest`.

### Test Setup

1.  **Create a Virtual Environment**: It is recommended to use a Python virtual environment.

    ```bash
    python -m venv .venv
    ```

2.  **Activate Environment and Install Dependencies**: Activate the environment and install the required packages.

    ```bash
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

### Running Tests

With the virtual environment activated, you can run the entire test suite:

```bash
pytest
```

This will execute both the unit tests (which use mocks) and the integration tests (which require Docker to be running for RabbitMQ and Redis).
