# Multi-stage Dockerfile for ETL Narrative Engine
# Supports both arm64 (Oracle Ampere A1) and amd64
# Build: docker buildx build --platform linux/arm64,linux/amd64 -t etl-engine:latest .

# Build stage
FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies system-wide
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python packages from builder (system-wide installation)
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copy application code (tests excluded from production image)
COPY src/ ./src/

# Create data directory for SQLite deduplication
RUN mkdir -p /data && chmod 755 /data

# Create non-root user
RUN groupadd -r etl && useradd -r -g etl etl \
    && chown -R etl:etl /app /data

# Environment variables (defaults, override via Kubernetes ConfigMap/Secrets)
ENV ETL_RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
ENV ETL_S3_ENDPOINT_URL=http://minio:9000
ENV ETL_S3_BUCKET_NAME=health-data
ENV ETL_DEDUPLICATION_STORE=sqlite
ENV ETL_DEDUPLICATION_DB_PATH=/data/etl_processed_messages.db
ENV ETL_LOG_LEVEL=INFO
ENV ETL_ENABLE_METRICS=true
ENV ETL_METRICS_PORT=8004

USER etl

# Expose metrics port
EXPOSE 8004

# Health check using metrics endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8004/health || exit 1

# Run ETL consumer
CMD ["python", "-m", "src.main"]
