# Testing Guide - Health Data AI Platform

## Overview

This platform uses a microservices architecture where each service is an independent Python package. Due to this architecture, tests must be run per-service to avoid namespace conflicts.

## Quick Start

### Run All Tests
```bash
source .venv/bin/activate
./run-tests.sh all
```

### Run Specific Service Tests
```bash
source .venv/bin/activate
./run-tests.sh {service-name}
```

Available services:
- `health-api` - Health API service (27 tests)
- `data-lake` - Data Lake service (1 test)
- `message-queue` - Message Queue service (14 tests)

### Examples
```bash
# Run all tests
./run-tests.sh all

# Run only health-api tests
./run-tests.sh health-api

# Run message-queue tests with verbose output
./run-tests.sh message-queue -v

# Run health-api tests matching "upload"
./run-tests.sh health-api -k upload

# Run with coverage
./run-tests.sh health-api --cov
```

## Running Tests from Service Directory

You can also run tests by changing into the service directory:

```bash
cd services/health-api-service
source ../../.venv/bin/activate
pytest tests/
```

This works because each service manages its own Python path via `sys.path` modifications in test files.

## Test Structure

```
services/
├── health-api-service/
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py
│       └── test_health_api_integration.py  (27 tests)
├── data-lake/
│   └── tests/
│       ├── __init__.py
│       └── test_data_lake_integration.py   (1 test)
└── message-queue/
    └── tests/
        ├── __init__.py
        ├── test_message_queue_message.py        (7 unit tests)
        ├── test_message_queue_deduplication.py  (6 unit tests)
        └── test_message_queue_integration.py    (1 integration test)
```

## Test Types

### Unit Tests
- Fast, no external dependencies
- Use mocks (e.g., fakeredis for Redis tests)
- Examples: `test_message_queue_message.py`, `test_message_queue_deduplication.py`

### Integration Tests
- Require Docker services
- Tests automatically start/stop required services
- Use real databases, queues, storage
- Examples: All `*_integration.py` files

## Why Per-Service Testing?

Each service is an independent Python package with its own:
- Configuration (`config/settings.py`)
- Dependencies (`requirements.txt`)
- Module namespace

Running all tests from the root causes namespace conflicts because multiple services have modules with the same names (e.g., `config.settings`).

## CI/CD

GitHub Actions workflows run tests per-service:
- `.github/workflows/test-health-api.yml`
- `.github/workflows/test-data-lake.yml`
- `.github/workflows/test-message-queue.yml`

## Troubleshooting

### "ModuleNotFoundError"
- Make sure you've activated the virtual environment
- Use `./run-tests.sh` instead of running `pytest` directly from root
- Check that you're in the correct directory if running tests manually

### "ValidationError" from Pydantic
- Ensure `.env` file exists at project root
- Run `./setup-all-services.sh` to regenerate environment variables
- Check that required environment variables are set

### Docker Services Not Starting
- Ensure Docker is running
- Check service logs: `docker compose logs <service-name>`
- Try stopping all services: `docker compose down -v`

## Test Coverage

Current test coverage:
- **Health API**: 27 integration tests covering auth, uploads, health checks, rate limiting
- **Data Lake**: 1 integration test for upload/download
- **Message Queue**: 14 tests (7 unit + 6 unit + 1 integration)

**Total: 42 tests**
