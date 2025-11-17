# Module 6: Deployment & Infrastructure

**Module ID:** ETL-M6
**Priority:** P2 (Infrastructure)
**Estimated Effort:** 1 week
**Dependencies:** All other modules (provides runtime environment)
**Team Assignment:** DevOps Engineer

---

## Module Overview

This module provides deployment infrastructure for the ETL Narrative Engine, including Docker containerization, docker-compose orchestration, environment configuration, and local development setup. It enables the entire ETL pipeline to run in a consistent, reproducible environment.

### Key Responsibilities
- Docker containerization for ETL service
- docker-compose configuration for full stack
- Environment variable management
- Local development scripts
- Integration with existing infrastructure (webauthn-stack, data-lake, message-queue)
- Sample data loading utilities

### What This Module Does NOT Include
- ❌ Business logic (Modules 1-5)
- ❌ Cloud deployment (separate DevOps task)
- ❌ Production Kubernetes manifests (future work)

---

## Docker Configuration

### Dockerfile for ETL Service

```dockerfile
# services/etl-narrative-engine/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY tests/ ./tests/

# Create data directory for SQLite deduplication
RUN mkdir -p /data

# Environment variables (defaults, override via docker-compose)
ENV ETL_RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672
ENV ETL_S3_ENDPOINT_URL=http://minio:9000
ENV ETL_S3_BUCKET_NAME=health-data
ENV ETL_DEDUPLICATION_STORE=sqlite
ENV ETL_DEDUPLICATION_DB_PATH=/data/etl_processed_messages.db
ENV ETL_LOG_LEVEL=INFO
ENV ETL_ENABLE_METRICS=true
ENV ETL_METRICS_PORT=8004

# Expose metrics port
EXPOSE 8004

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8004/health || exit 1

# Run ETL consumer
CMD ["python", "-m", "src.consumer.main"]
```

### Docker Compose Integration

```yaml
# docker-compose.yml (root level - add to existing file)
services:
  # ... existing services (minio, rabbitmq, postgres, redis) ...

  # ETL Narrative Engine
  etl-narrative-engine:
    build:
      context: ./services/etl-narrative-engine
      dockerfile: Dockerfile
    container_name: etl-narrative-engine
    hostname: etl-narrative-engine
    depends_on:
      - rabbitmq
      - minio
      - postgres
      - redis
    environment:
      # RabbitMQ
      ETL_RABBITMQ_URL: amqp://guest:guest@rabbitmq:5672
      ETL_QUEUE_NAME: health_data_processing
      ETL_EXCHANGE_NAME: health_data_exchange

      # MinIO / S3
      ETL_S3_ENDPOINT_URL: http://minio:9000
      ETL_S3_ACCESS_KEY: ${MINIO_ROOT_USER:-minioadmin}
      ETL_S3_SECRET_KEY: ${MINIO_ROOT_PASSWORD:-minioadmin}
      ETL_S3_BUCKET_NAME: health-data

      # Deduplication
      ETL_DEDUPLICATION_STORE: redis  # Use Redis for distributed setup
      ETL_REDIS_URL: redis://redis:6379/1  # Use DB 1 for ETL

      # Validation
      ETL_QUALITY_THRESHOLD: 0.7
      ETL_ENABLE_QUARANTINE: true

      # Training Data Output
      ETL_TRAINING_DATA_PREFIX: training/
      ETL_INCLUDE_METADATA: true

      # Observability
      ETL_ENABLE_METRICS: true
      ETL_METRICS_PORT: 8004
      ETL_ENABLE_JAEGER_TRACING: true
      ETL_JAEGER_OTLP_ENDPOINT: http://host.docker.internal:4319  # Jaeger from webauthn-stack
      ETL_LOG_LEVEL: INFO

      # Development
      ETL_DEVELOPMENT_MODE: true
      ETL_MAX_RETRIES: 3

    ports:
      - "8004:8004"  # Metrics endpoint

    volumes:
      # Mount sample Avro files for local development
      - ./docs/sample-avro-files:/sample-avro-files:ro
      # Persistent deduplication DB (if using SQLite)
      - etl-data:/data

    networks:
      - health-platform

    restart: unless-stopped

    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8004/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

volumes:
  # ... existing volumes ...
  etl-data:
    driver: local

networks:
  health-platform:
    driver: bridge
```

---

## Environment Configuration

### Environment Variable Template

```bash
# services/etl-narrative-engine/.env.template
# Copy this to .env and fill in values

# RabbitMQ Configuration
ETL_RABBITMQ_URL=amqp://guest:guest@localhost:5672
ETL_QUEUE_NAME=health_data_processing
ETL_EXCHANGE_NAME=health_data_exchange
ETL_ROUTING_KEY=health_data

# MinIO / S3 Configuration
ETL_S3_ENDPOINT_URL=http://localhost:9000
ETL_S3_ACCESS_KEY=minioadmin
ETL_S3_SECRET_KEY=minioadmin
ETL_S3_BUCKET_NAME=health-data
ETL_S3_REGION=us-east-1

# Deduplication Configuration
ETL_DEDUPLICATION_STORE=sqlite  # or 'redis'
ETL_DEDUPLICATION_DB_PATH=/data/etl_processed_messages.db
ETL_REDIS_URL=redis://localhost:6379/1

# Validation Configuration
ETL_QUALITY_THRESHOLD=0.7
ETL_ENABLE_QUARANTINE=true

# Training Data Output Configuration
ETL_TRAINING_DATA_PREFIX=training/
ETL_INCLUDE_METADATA=true

# Observability Configuration
ETL_ENABLE_METRICS=true
ETL_METRICS_PORT=8004
ETL_ENABLE_JAEGER_TRACING=true
ETL_JAEGER_OTLP_ENDPOINT=http://localhost:4319
ETL_LOG_LEVEL=INFO

# Development Configuration
ETL_DEVELOPMENT_MODE=true
ETL_MAX_RETRIES=3
ETL_RETRY_DELAY_SECONDS=5
```

### Settings Class

```python
# src/config/settings.py
from pydantic_settings import BaseSettings
from typing import Literal

class ETLSettings(BaseSettings):
    """ETL Narrative Engine settings"""

    # RabbitMQ
    rabbitmq_url: str
    queue_name: str = "health_data_processing"
    exchange_name: str = "health_data_exchange"
    routing_key: str = "health_data"

    # MinIO / S3
    s3_endpoint_url: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket_name: str
    s3_region: str = "us-east-1"

    # Deduplication
    deduplication_store: Literal["sqlite", "redis"] = "sqlite"
    deduplication_db_path: str = "/data/etl_processed_messages.db"
    redis_url: str = "redis://localhost:6379/1"

    # Validation
    quality_threshold: float = 0.7
    enable_quarantine: bool = True

    # Training Data Output
    training_data_prefix: str = "training/"
    include_metadata: bool = True

    # Observability
    enable_metrics: bool = True
    metrics_port: int = 8004
    enable_jaeger_tracing: bool = True
    jaeger_otlp_endpoint: str = "http://localhost:4319"
    log_level: str = "INFO"

    # Development
    development_mode: bool = False
    max_retries: int = 3
    retry_delay_seconds: int = 5

    class Config:
        env_prefix = "ETL_"
        env_file = ".env"

# Global settings instance
settings = ETLSettings()
```

---

## Local Development Scripts

### Development Setup Script

```bash
#!/bin/bash
# scripts/setup-dev.sh
# Setup local development environment for ETL Narrative Engine

set -e

echo "Setting up ETL Narrative Engine development environment..."

# 1. Create Python virtual environment
echo "Creating Python virtual environment..."
python3.11 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r services/etl-narrative-engine/requirements.txt
pip install -r services/etl-narrative-engine/requirements-dev.txt

# 3. Create environment file if not exists
if [ ! -f services/etl-narrative-engine/.env ]; then
    echo "Creating .env file from template..."
    cp services/etl-narrative-engine/.env.template services/etl-narrative-engine/.env
    echo "⚠️  Please review and update services/etl-narrative-engine/.env"
fi

# 4. Start infrastructure services (MinIO, RabbitMQ, Redis, PostgreSQL)
echo "Starting infrastructure services with docker-compose..."
docker-compose up -d minio rabbitmq redis postgres

# 5. Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 10

# 6. Initialize MinIO bucket
echo "Initializing MinIO bucket..."
docker-compose exec -T minio mc alias set myminio http://localhost:9000 minioadmin minioadmin
docker-compose exec -T minio mc mb myminio/health-data --ignore-existing

# 7. Create RabbitMQ queue
echo "Creating RabbitMQ queue..."
# Queue will be auto-created by consumer, but can pre-create if needed

# 8. Run tests to verify setup
echo "Running tests..."
pytest services/etl-narrative-engine/tests/

echo "✅ Development environment setup complete!"
echo ""
echo "To run the ETL service:"
echo "  source .venv/bin/activate"
echo "  python -m services.etl_narrative_engine.src.consumer.main"
echo ""
echo "To run tests:"
echo "  pytest services/etl-narrative-engine/tests/"
```

### Sample Data Loader Script

```bash
#!/bin/bash
# scripts/load-sample-data.sh
# Load sample Avro files and trigger ETL processing

set -e

SAMPLE_DIR="docs/sample-avro-files"
BUCKET="health-data"
S3_ENDPOINT="http://localhost:9000"

echo "Loading sample health data files..."

# Upload all sample files to MinIO
for file in "$SAMPLE_DIR"/*.avro; do
    filename=$(basename "$file")
    record_type=$(echo "$filename" | sed 's/_[0-9]*.avro//')

    echo "Uploading $filename as $record_type..."

    # Generate S3 key with date partitioning
    s3_key="raw/$record_type/$(date +%Y/%m/%d)/$filename"

    # Upload to MinIO
    docker-compose exec -T minio mc cp "/sample-avro-files/$filename" "myminio/$BUCKET/$s3_key"

    # Publish message to RabbitMQ to trigger processing
    python3 <<EOF
import pika
import json
import uuid
from datetime import datetime

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost', 5672))
channel = connection.channel()

message = {
    'bucket': '$BUCKET',
    'key': '$s3_key',
    'record_type': '$record_type',
    'user_id': 'sample_user_123',
    'correlation_id': str(uuid.uuid4()),
    'timestamp': datetime.utcnow().isoformat(),
}

channel.basic_publish(
    exchange='health_data_exchange',
    routing_key='health_data',
    body=json.dumps(message)
)

connection.close()
print(f"Published message for {s3_key}")
EOF

done

echo "✅ All sample files loaded and processing triggered!"
```

### Stack Management Script

```bash
#!/bin/bash
# scripts/manage-etl-stack.sh
# Manage ETL Narrative Engine stack

COMMAND=${1:-help}

case $COMMAND in
  start)
    echo "Starting ETL Narrative Engine stack..."
    # Start WebAuthn stack first (for Jaeger)
    cd webauthn-stack/docker && docker-compose up -d && cd ../..
    # Start health services stack
    docker-compose up -d
    echo "✅ ETL stack started"
    echo "  - Metrics: http://localhost:8004/metrics"
    echo "  - Health: http://localhost:8004/health"
    echo "  - Jaeger UI: http://localhost:16687"
    ;;

  stop)
    echo "Stopping ETL Narrative Engine stack..."
    docker-compose down
    cd webauthn-stack/docker && docker-compose down && cd ../..
    echo "✅ ETL stack stopped"
    ;;

  logs)
    echo "Showing ETL logs (Ctrl+C to exit)..."
    docker-compose logs -f etl-narrative-engine
    ;;

  restart)
    echo "Restarting ETL Narrative Engine..."
    docker-compose restart etl-narrative-engine
    ;;

  rebuild)
    echo "Rebuilding ETL Narrative Engine..."
    docker-compose build etl-narrative-engine
    docker-compose up -d etl-narrative-engine
    ;;

  test)
    echo "Running ETL tests..."
    docker-compose exec etl-narrative-engine pytest /app/tests/
    ;;

  shell)
    echo "Opening shell in ETL container..."
    docker-compose exec etl-narrative-engine /bin/bash
    ;;

  metrics)
    echo "Fetching current metrics..."
    curl -s http://localhost:8004/metrics | grep etl_
    ;;

  health)
    echo "Checking health status..."
    curl -s http://localhost:8004/health | jq
    ;;

  *)
    echo "ETL Narrative Engine Stack Management"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  start     - Start the full ETL stack"
    echo "  stop      - Stop the ETL stack"
    echo "  logs      - View ETL logs"
    echo "  restart   - Restart ETL service"
    echo "  rebuild   - Rebuild and restart ETL service"
    echo "  test      - Run tests inside container"
    echo "  shell     - Open shell in ETL container"
    echo "  metrics   - Show current Prometheus metrics"
    echo "  health    - Check health status"
    ;;
esac
```

---

## Dependencies

### Python Requirements

```txt
# services/etl-narrative-engine/requirements.txt
# Core dependencies
pydantic==2.5.0
pydantic-settings==2.1.0
fastavro==1.9.3
aio-pika==9.3.1
aioboto3==12.3.0
structlog==24.1.0

# Observability
prometheus-client==0.19.0
opentelemetry-api==1.21.0
opentelemetry-sdk==1.21.0
opentelemetry-exporter-otlp-proto-grpc==1.21.0

# API server for metrics
fastapi==0.109.0
uvicorn==0.27.0

# Database
aiosqlite==0.19.0  # For SQLite deduplication
redis==5.0.1       # For Redis deduplication
```

```txt
# services/etl-narrative-engine/requirements-dev.txt
# Testing
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
pytest-mock==3.12.0

# Linting and formatting
black==23.12.1
ruff==0.1.9
mypy==1.7.1

# Development tools
ipython==8.18.1
```

---

## Implementation Checklist

### Week 1: Deployment & Infrastructure
- [ ] Create Docker infrastructure
  - [ ] Write Dockerfile for ETL service
  - [ ] Update docker-compose.yml
  - [ ] Configure environment variables
- [ ] Create development scripts
  - [ ] setup-dev.sh
  - [ ] load-sample-data.sh
  - [ ] manage-etl-stack.sh
- [ ] Create settings management
  - [ ] .env.template
  - [ ] settings.py with Pydantic
- [ ] Test local deployment
  - [ ] docker-compose up works
  - [ ] ETL service starts successfully
  - [ ] Metrics endpoint accessible
  - [ ] Health check passes
- [ ] Documentation
  - [ ] Local development guide
  - [ ] Environment variable reference
  - [ ] Deployment troubleshooting guide
- [ ] Integration testing
  - [ ] Full stack integration test
  - [ ] Sample data processing test

---

## Testing Strategy

### Integration Tests

```python
# tests/test_deployment_integration.py
@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_stack_deployment():
    """Test complete ETL stack deployment"""

    # Verify all infrastructure is running
    assert await check_rabbitmq_connection()
    assert await check_minio_connection()
    assert await check_redis_connection()

    # Verify ETL service is healthy
    response = requests.get("http://localhost:8004/health")
    assert response.status_code == 200
    health = response.json()
    assert health['status'] in ['healthy', 'degraded']

    # Verify metrics endpoint
    response = requests.get("http://localhost:8004/metrics")
    assert response.status_code == 200
    assert 'etl_messages_processed_total' in response.text

@pytest.mark.integration
async def test_sample_data_processing():
    """Test processing of sample Avro files"""

    # Upload sample file and publish message
    await upload_sample_file('docs/sample-avro-files/BloodGlucoseRecord_1758407139312.avro')

    # Wait for processing (with timeout)
    await asyncio.sleep(10)

    # Verify training data was generated
    training_files = await list_s3_objects('health-data', 'training/')
    assert len(training_files) > 0
```

---

## Configuration

### Docker Compose Profiles (Optional)

```yaml
# Add profiles for different deployment scenarios
services:
  etl-narrative-engine:
    profiles:
      - etl
      - full-stack

  # Development profile: ETL only (assumes infrastructure already running)
  # docker-compose --profile etl up

  # Full stack profile: Everything
  # docker-compose --profile full-stack up
```

---

## Success Criteria

**Module Complete When:**
- ✅ Dockerfile builds successfully
- ✅ docker-compose starts full stack
- ✅ ETL service connects to all dependencies
- ✅ Metrics endpoint accessible
- ✅ Health checks pass
- ✅ Sample data can be processed end-to-end
- ✅ Development scripts work
- ✅ Environment configuration documented
- ✅ Integration tests passing

**Ready for Integration When:**
- ✅ All modules can run in Docker
- ✅ Local development workflow documented
- ✅ Sample data processing verified
- ✅ Observability working (metrics, traces, logs)

---

## Integration Points

### **Depends On:**
- **All Modules (1-5)** - Provides runtime environment

### **Depended On By:**
- Development team (local testing)
- CI/CD pipelines (automated testing)

---

## Notes & Considerations

1. **Docker Networking**: Use `host.docker.internal` to access Jaeger from webauthn-stack running on host.

2. **Volume Mounts**: Sample files mounted read-only for local development. Production should use S3 directly.

3. **Health Checks**: Docker health check uses `/health` endpoint to enable automatic container restart.

4. **Resource Limits**: Consider adding resource limits in docker-compose for production deployment:
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '2'
         memory: 2G
   ```

5. **Secrets Management**: Use Docker secrets or external secret management (Vault, AWS Secrets Manager) for production.

6. **Multi-Stage Builds**: Consider multi-stage Docker build for smaller production images.

---

## Production Deployment Checklist (Future)

- [ ] Create Kubernetes manifests (Deployment, Service, ConfigMap, Secret)
- [ ] Setup Horizontal Pod Autoscaler (HPA) based on queue depth
- [ ] Configure PersistentVolumeClaim for deduplication DB
- [ ] Setup Helm chart for easy deployment
- [ ] Configure ingress for metrics endpoint
- [ ] Setup Prometheus ServiceMonitor for metrics scraping
- [ ] Configure log aggregation (ELK, Loki)
- [ ] Setup alerting rules (Prometheus AlertManager)
- [ ] Create deployment pipeline (GitHub Actions, GitLab CI, ArgoCD)
- [ ] Load testing and capacity planning

---

**End of Module 6 Specification**
