# ETL Narrative Engine - Deployment Guide

This directory contains deployment configuration for the ETL Narrative Engine service.

## Quick Start

### 1. Start the Full Stack

```bash
# From project root
./scripts/manage-etl-stack.sh start
```

This will:
- Start WebAuthn stack (for Jaeger tracing)
- Start all infrastructure services (RabbitMQ, MinIO, Redis, PostgreSQL)
- Start the ETL Narrative Engine

### 2. Verify Deployment

```bash
# Check health status
curl http://localhost:8004/health | jq

# Check metrics
curl http://localhost:8004/metrics | grep etl_

# View logs
./scripts/manage-etl-stack.sh logs
```

### 3. Load Sample Data

```bash
./scripts/load-sample-data.sh
```

## Available Endpoints

### ETL Service
- **Health Check**: `http://localhost:8004/health`
- **Metrics**: `http://localhost:8004/metrics`
- **Readiness**: `http://localhost:8004/ready` (Kubernetes)
- **Liveness**: `http://localhost:8004/live` (Kubernetes)

### Infrastructure Services
- **RabbitMQ Management**: `http://localhost:15672` (guest/guest)
- **MinIO Console**: `http://localhost:9001` (minioadmin/minioadmin)
- **Jaeger UI**: `http://localhost:16687` (from webauthn-stack)

## Docker Compose Configuration

The ETL service is configured in `etl-narrative-engine.compose.yml` and included in the main `docker-compose.yml`.

### Environment Variables

All configuration is done via environment variables with the `ETL_` prefix. See `.env.template` for all available options.

Key variables:
```bash
# RabbitMQ
ETL_RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
ETL_QUEUE_NAME=health_data_processing

# MinIO/S3
ETL_S3_ENDPOINT_URL=http://minio:9000
ETL_S3_BUCKET_NAME=health-data

# Deduplication
ETL_DEDUPLICATION_STORE=redis  # or 'sqlite'
ETL_DEDUPLICATION_REDIS_URL=redis://redis:6379/2

# Observability
ETL_ENABLE_METRICS=true
ETL_METRICS_PORT=8004
ETL_ENABLE_JAEGER_TRACING=false
```

### Volumes

- `etl-data`: Persistent storage for SQLite deduplication DB (if using SQLite)

### Network

The ETL service uses the `health-platform-net` network shared with other services.

## Development Setup

### Local Development (without Docker)

```bash
# Run setup script
./scripts/setup-etl-dev.sh

# Activate virtual environment
source .venv/bin/activate

# Start infrastructure services only
docker compose up -d minio rabbitmq redis

# Run ETL service locally
python -m services.etl_narrative_engine.src.main
```

### Running Tests

```bash
# Run all tests
pytest services/etl-narrative-engine/tests/

# Run deployment integration tests (requires Docker services)
pytest services/etl-narrative-engine/tests/test_deployment_integration.py -v

# Run tests inside Docker container
./scripts/manage-etl-stack.sh test
```

## Management Scripts

### Stack Management

```bash
# Start stack
./scripts/manage-etl-stack.sh start

# Stop stack
./scripts/manage-etl-stack.sh stop

# Restart ETL service
./scripts/manage-etl-stack.sh restart

# Rebuild and restart
./scripts/manage-etl-stack.sh rebuild
```

### Monitoring

```bash
# View logs
./scripts/manage-etl-stack.sh logs

# Check metrics
./scripts/manage-etl-stack.sh metrics

# Check health
./scripts/manage-etl-stack.sh health

# Check status
./scripts/manage-etl-stack.sh status
```

### Development

```bash
# Open shell in container
./scripts/manage-etl-stack.sh shell

# Run tests
./scripts/manage-etl-stack.sh test

# Load sample data
./scripts/manage-etl-stack.sh load-sample
```

## Health Checks

The service includes Docker health checks that monitor the `/health` endpoint:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8004/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

## Metrics

The service exposes Prometheus metrics at `/metrics`:

- `etl_messages_processed_total` - Total messages processed
- `etl_processing_duration_seconds` - Processing time histogram
- `etl_validation_quality_score` - Validation quality scores
- `etl_records_quarantined_total` - Quarantined records
- `etl_consumer_status` - Consumer running status
- `etl_rabbitmq_connection_status` - RabbitMQ connection status
- `etl_s3_connection_status` - S3 connection status

## Observability

### Jaeger Tracing (Optional)

To enable distributed tracing:

1. Ensure webauthn-stack is running (provides Jaeger)
2. Set environment variables:
   ```bash
   ETL_ENABLE_JAEGER_TRACING=true
   ETL_JAEGER_OTLP_ENDPOINT=http://host.docker.internal:4319
   ```

3. Access Jaeger UI at `http://localhost:16687`

## Troubleshooting

### ETL Service Not Starting

1. Check if dependencies are running:
   ```bash
   docker compose ps
   ```

2. Check logs:
   ```bash
   docker compose logs etl-narrative-engine
   ```

3. Verify health status:
   ```bash
   curl http://localhost:8004/health
   ```

### Messages Not Processing

1. Check RabbitMQ connection:
   - Access RabbitMQ UI: `http://localhost:15672`
   - Verify queue exists: `health_data_processing`
   - Check messages in queue

2. Check S3 connectivity:
   - Access MinIO UI: `http://localhost:9001`
   - Verify bucket exists: `health-data`

3. Check metrics:
   ```bash
   curl http://localhost:8004/metrics | grep etl_processing_errors_total
   ```

### Performance Issues

1. Check resource usage:
   ```bash
   docker stats etl-narrative-engine
   ```

2. Review processing metrics:
   ```bash
   ./scripts/manage-etl-stack.sh metrics
   ```

3. Adjust resource limits in `etl-narrative-engine.compose.yml`:
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '2'
         memory: 2G
   ```

## Production Deployment

For production deployment:

1. **Environment Variables**:
   - Use proper secret management (AWS Secrets Manager, Vault, etc.)
   - Never commit `.env` files with real credentials

2. **Resource Limits**:
   - Uncomment and adjust resource limits in compose file
   - Configure based on expected load

3. **Logging**:
   - Set `ETL_LOG_JSON=true` for structured logging
   - Configure log aggregation (ELK, Loki, etc.)

4. **Monitoring**:
   - Setup Prometheus to scrape `/metrics` endpoint
   - Configure alerting rules
   - Monitor queue depth and processing times

5. **High Availability**:
   - Run multiple ETL consumer instances
   - Use Redis for deduplication (not SQLite)
   - Configure RabbitMQ clustering

## Next Steps

- [Development Guide](../README.md)
- [Testing Guide](../TESTING.md)
- [Implementation Plan](../implementation_plan.md)
- [Architecture Overview](../../../docs/architecture/implementation_plan_optimal_hybrid.md)
