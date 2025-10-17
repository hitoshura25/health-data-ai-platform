# Data Lake Service

This service provides an intelligent object storage system for health data using MinIO.

## Features

- **Intelligent Object Naming:** Smart naming conventions for efficient querying.
- **Automated Lifecycle Management:** Built-in policies for data tiering and retention.
- **Data Quality Validation:** Application-level validation with quality scoring and automatic quarantine.
- **Security:** Encryption at rest, access controls, and audit logging.

## Getting Started

These instructions will get the data lake service running locally for development and testing.

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

2.  **Start Services**: With the `.env` files created, start the MinIO container from the **project root**:

    ```bash
    docker compose up -d minio
    ```

    You can now access the MinIO Console at [http://localhost:9001](http://localhost:9001) using the credentials from `infrastructure/.env` (DATALAKE_MINIO_ACCESS_KEY and DATALAKE_MINIO_SECRET_KEY).

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
    pip install -r services/data-lake/requirements.txt
    ```

### Running Tests

**From project root**, with the virtual environment activated:

```bash
# Run all data-lake tests
./run-tests.sh data-lake

# Run with verbose output
./run-tests.sh data-lake -v

# Run only unit tests (no Docker needed)
cd services/data-lake
pytest tests/test_data_lake_unit.py
```

**Test types:**
- **Unit tests**: Use mocks, no Docker required
- **Integration tests**: Automatically start/stop Docker containers (MinIO) via fixtures

## Server-Side Encryption (SSE)

The server-side encryption for the local MinIO setup is configured using a secret key. The implementation is based on the following resource:

- [MinIO Server-Side Encryption with Docker Compose](https://medium.com/@murisuu/self-host-s3-minio-docker-compose-setup-48588b2f9bcd)