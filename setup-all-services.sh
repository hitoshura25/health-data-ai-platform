#!/bin/bash

# Health Data AI Platform - Unified Setup Script
# This script generates secure .env files for all services with coordinated secrets

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 Health Data AI Platform - Secure Environment Setup"
echo "=================================================="
echo ""

# Step 1: Generate shared infrastructure secrets
echo "📦 Step 1/5: Setting up shared infrastructure (PostgreSQL, Redis, Jaeger, WebAuthn, MinIO, RabbitMQ)..."
cd "$SCRIPT_DIR/infrastructure"
./setup-secure-env.sh
cd "$SCRIPT_DIR"
echo ""

# Load shared credentials for use by service-specific scripts
source "$SCRIPT_DIR/infrastructure/.env"

# Step 2: Setup data-lake service
echo "📦 Step 2/5: Setting up data-lake service..."
cd "$SCRIPT_DIR/services/data-lake"

# Override the data-lake setup script to use shared MinIO credentials
cat > .env << EOL
# MinIO Configuration (using shared infrastructure credentials)
DATALAKE_MINIO_ENDPOINT=localhost:9000
DATALAKE_MINIO_ACCESS_KEY=${DATALAKE_MINIO_ACCESS_KEY}
DATALAKE_MINIO_SECRET_KEY=${DATALAKE_MINIO_SECRET_KEY}
DATALAKE_MINIO_KMS_SECRET_KEY=${DATALAKE_MINIO_KMS_SECRET_KEY}
DATALAKE_MINIO_SECURE=false
DATALAKE_MINIO_REGION=us-east-1

# Bucket Configuration
DATALAKE_BUCKET_NAME=${DATALAKE_BUCKET_NAME}
DATALAKE_CREATE_BUCKET_ON_STARTUP=true

# Object Naming
DATALAKE_MAX_OBJECT_KEY_LENGTH=1024
DATALAKE_HASH_LENGTH=8

# Data Quality
DATALAKE_ENABLE_QUALITY_VALIDATION=true
DATALAKE_QUALITY_THRESHOLD=0.7
DATALAKE_QUARANTINE_RETENTION_DAYS=30

# Lifecycle Management
DATALAKE_RAW_DATA_EXPIRATION_DAYS=2555
DATALAKE_PROCESSED_DATA_EXPIRATION_DAYS=3650

# Security
DATALAKE_ENABLE_ENCRYPTION=true
DATALAKE_ENABLE_VERSIONING=true
DATALAKE_ENABLE_AUDIT_LOGGING=true

# Monitoring
DATALAKE_ENABLE_METRICS=true
DATALAKE_METRICS_PORT=${DATALAKE_METRICS_PORT}
DATALAKE_ANALYTICS_UPDATE_INTERVAL_HOURS=6
EOL

echo "   ✅ Data-lake .env created with shared MinIO credentials"
cd "$SCRIPT_DIR"
echo ""

# Step 3: Setup health-api-service
echo "📦 Step 3/5: Setting up health-api-service..."
cd "$SCRIPT_DIR/services/health-api-service"

# Create .env using shared infrastructure credentials
cat > .env << EOL
# FastAPI Users Secret
SECRET_KEY=${SECRET_KEY}

# Application Connection URLs (for running tests locally)
DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5432/${HEALTH_API_DB}
REDIS_URL=redis://:${HEALTH_REDIS_PASSWORD}@localhost:6379
S3_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY=${DATALAKE_MINIO_ACCESS_KEY}
S3_SECRET_KEY=${DATALAKE_MINIO_SECRET_KEY}
S3_BUCKET_NAME=${DATALAKE_BUCKET_NAME}
RABBITMQ_URL=amqp://${MQ_RABBITMQ_USER}:${MQ_RABBITMQ_PASS}@localhost:5672/

# Rate Limiting and File Size
UPLOAD_RATE_LIMIT=${UPLOAD_RATE_LIMIT}
UPLOAD_RATE_LIMIT_STORAGE_URI=redis://:${HEALTH_REDIS_PASSWORD}@localhost:6379
MAX_FILE_SIZE_MB=${MAX_FILE_SIZE_MB}

# --- Docker Compose Variables ---
# These are used by the docker-compose.yml file

# PostgreSQL
POSTGRES_DB=${HEALTH_API_DB}
POSTGRES_USER=${POSTGRES_USER}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}

# MinIO
MINIO_ROOT_USER=${DATALAKE_MINIO_ACCESS_KEY}
MINIO_ROOT_PASSWORD=${DATALAKE_MINIO_SECRET_KEY}

# RabbitMQ
RABBITMQ_DEFAULT_USER=${MQ_RABBITMQ_USER}
RABBITMQ_DEFAULT_PASS=${MQ_RABBITMQ_PASS}
RABBITMQ_MAIN_EXCHANGE=${RABBITMQ_MAIN_EXCHANGE}
EOL

echo "   ✅ Health-api .env created with shared credentials"
cd "$SCRIPT_DIR"
echo ""

# Step 4: Setup message-queue service
echo "📦 Step 4/5: Setting up message-queue service..."
cd "$SCRIPT_DIR/services/message-queue"

# Create .env using shared infrastructure credentials
cat > .env << EOL
# RabbitMQ Configuration
MQ_RABBITMQ_URL=${MQ_RABBITMQ_URL}
MQ_RABBITMQ_MANAGEMENT_URL=${MQ_RABBITMQ_MANAGEMENT_URL}
MQ_RABBITMQ_USER=${MQ_RABBITMQ_USER}
MQ_RABBITMQ_PASS=${MQ_RABBITMQ_PASS}

# Redis Configuration
MQ_REDIS_URL=${MQ_REDIS_URL}

# Exchange Configuration
MQ_MAIN_EXCHANGE=health_data_exchange
MQ_DLX_EXCHANGE=health_data_dlx

# Queue Configuration
MQ_PROCESSING_QUEUE=health_data_processing
MQ_FAILED_QUEUE=health_data_failed

# Monitoring
MQ_ENABLE_METRICS=true
MQ_METRICS_PORT=8001
EOL

echo "   ✅ Message-queue .env created with shared credentials"
cd "$SCRIPT_DIR"
echo ""

# Step 5: Create root .env symlink for docker compose
echo "📦 Step 5/5: Creating root .env for docker-compose..."
cp "$SCRIPT_DIR/infrastructure/.env" "$SCRIPT_DIR/.env"
echo "   ✅ Root .env created (copy of infrastructure/.env)"
echo ""

# Summary
echo "=================================================="
echo "✅ All services configured successfully!"
echo ""
echo "📋 Summary:"
echo "   - Infrastructure:      infrastructure/.env"
echo "   - Data Lake:           services/data-lake/.env"
echo "   - Message Queue:       services/message-queue/.env"
echo "   - Health API:          services/health-api-service/.env"
echo "   - Root (Docker):       .env"
echo ""
echo "🔐 All services are now using coordinated, secure credentials"
echo ""
echo "🚀 Next steps:"
echo "   1. Start all services:    docker compose up -d"
echo "   2. View logs:             docker compose logs -f"
echo "   3. Run tests:             cd services/health-api-service && source .venv/bin/activate && pytest"
echo ""
