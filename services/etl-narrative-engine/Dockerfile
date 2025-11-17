# ETL Narrative Engine - Dockerfile
# Python-based ETL service for processing health data

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY tests/ ./tests/
COPY pytest.ini ./

# Create data directory for SQLite deduplication
RUN mkdir -p /data

# Environment variables (defaults, override via docker-compose)
ENV ETL_RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
ENV ETL_S3_ENDPOINT_URL=http://minio:9000
ENV ETL_S3_BUCKET_NAME=health-data
ENV ETL_DEDUPLICATION_STORE=sqlite
ENV ETL_DEDUPLICATION_DB_PATH=/data/etl_processed_messages.db
ENV ETL_LOG_LEVEL=INFO
ENV ETL_ENABLE_METRICS=true
ENV ETL_METRICS_PORT=8004

# Expose metrics port
EXPOSE 8004

# Health check using metrics endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8004/health || exit 1

# Run ETL consumer
CMD ["python", "-m", "src.main"]
