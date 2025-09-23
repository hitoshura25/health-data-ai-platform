# CI/CD Workflows

This directory contains GitHub Actions workflows for the Health Data AI Platform.

## Current Workflows

### `schema-validation.yml`
- **Purpose**: Validates Avro schemas, Python types, and validation framework
- **Triggers**: Changes to `shared/schemas/`, `shared/types/`, or `shared/validation/`
- **What it tests**:
  - Avro schema validity
  - Schema evolution compatibility
  - Python type definitions import correctly
  - Clinical validation framework functionality

### `integration-tests.yml`
- **Purpose**: Tests infrastructure connectivity and basic integration
- **Triggers**: Push to main/develop, PRs, daily schedule
- **What it tests**:
  - Infrastructure services (PostgreSQL, RabbitMQ, Redis, MinIO)
  - Basic connectivity tests
  - Shared component tests
  - Creates placeholder integration tests if none exist

## Future Workflows

As services are implemented, additional workflows will be added:

- `health-api-service.yml` - When the Health API service is implemented
- `message-queue.yml` - When the Message Queue service is implemented
- `data-lake.yml` - When the Data Lake service is implemented
- `etl-narrative-engine.yml` - When the ETL Narrative Engine is implemented
- `ai-query-interface.yml` - When the AI Query Interface is implemented

Each service workflow will include:
- Unit and integration tests
- Security scanning
- Docker image building
- Deployment to staging/production

## Development Notes

- Only infrastructure and shared components are currently tested
- Service-specific workflows will be added incrementally as services are developed
- All workflows use Python 3.11 and the latest GitHub Actions
- Infrastructure services are tested via GitHub Actions services