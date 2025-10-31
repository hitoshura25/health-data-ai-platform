#!/bin/bash

# This script generates secure .env file for shared infrastructure services
# (PostgreSQL, Redis, Jaeger, WebAuthn)

set -e

# Function to generate a secure random string
generate_short_secret() {
  openssl rand -hex 16
}

generate_long_secret() {
  openssl rand -hex 32
}

# Set the path for the .env file
ENV_FILE="$(dirname "$0")/.env"

echo "🔐 Generating secure credentials for shared infrastructure..."

# --- Credentials Generation ---
POSTGRES_USER=$(generate_short_secret)
POSTGRES_PASSWORD=$(generate_long_secret)
MQ_RABBITMQ_USER=$(generate_short_secret)
MQ_RABBITMQ_PASS=$(generate_long_secret)
DATALAKE_MINIO_ACCESS_KEY=$(generate_short_secret)
DATALAKE_MINIO_SECRET_KEY=$(generate_long_secret)
DATALAKE_MINIO_KMS_KEY=$(openssl rand -base64 32)
SECRET_KEY=$(generate_long_secret)
WEBAUTHN_REDIS_PASSWORD=$(generate_long_secret)

# --- Static Configuration ---
POSTGRES_DB="postgres"

# --- Create the .env file ---
cat > "$ENV_FILE" << EOL
# =============================================================================
# SHARED INFRASTRUCTURE - Auto-generated secrets
# WARNING: Do not edit manually - regenerate with setup-all-services.sh
# =============================================================================

# --- PostgreSQL Database ---
POSTGRES_USER=${POSTGRES_USER}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_DB=${POSTGRES_DB}
POSTGRES_PORT=5432

# Multiple databases (comma-separated, auto-created on startup)
POSTGRES_MULTIPLE_DATABASES=healthapi,webauthn

# Individual service database names
HEALTH_API_DB=healthapi
WEBAUTHN_DB=webauthn

# --- Redis Cache & Sessions ---
REDIS_PORT=6379

# --- WebAuthn Stack Integration ---
# WebAuthn authentication and Jaeger tracing are provided by webauthn-stack/
# Start webauthn-stack first: cd webauthn-stack/docker && docker compose up -d
#
# Jaeger endpoints (from webauthn-stack):
#   UI: http://localhost:16687
#   OTLP gRPC: http://localhost:4319
#   OTLP HTTP: http://localhost:4320
#
# WebAuthn server endpoint (from webauthn-stack):
#   Gateway: http://localhost:8000
#
# When adding Jaeger tracing to health services, use:
# JAEGER_OTLP_ENDPOINT=http://localhost:4319  # or 4320 for HTTP

# --- Data Lake (MinIO) ---
MINIO_API_PORT=9000
MINIO_CONSOLE_PORT=9001

DATALAKE_MINIO_ACCESS_KEY=${DATALAKE_MINIO_ACCESS_KEY}
DATALAKE_MINIO_SECRET_KEY=${DATALAKE_MINIO_SECRET_KEY}
DATALAKE_MINIO_KMS_SECRET_KEY=my-minio-key:${DATALAKE_MINIO_KMS_KEY}
DATALAKE_BUCKET_NAME=health-data
DATALAKE_METRICS_PORT=8002

# --- Message Queue (RabbitMQ) ---
RABBITMQ_AMQP_PORT=5672
RABBITMQ_MGMT_PORT=15672

MQ_RABBITMQ_USER=${MQ_RABBITMQ_USER}
MQ_RABBITMQ_PASS=${MQ_RABBITMQ_PASS}
RABBITMQ_MAIN_EXCHANGE=health-data

# Message Queue URLs
MQ_RABBITMQ_URL=amqp://${MQ_RABBITMQ_USER}:${MQ_RABBITMQ_PASS}@localhost:5672/
MQ_RABBITMQ_MANAGEMENT_URL=http://localhost:15672
MQ_REDIS_URL=redis://:${WEBAUTHN_REDIS_PASSWORD}@localhost:6379

# --- Health API Service ---
HEALTH_API_PORT=8000
SECRET_KEY=${SECRET_KEY}
UPLOAD_RATE_LIMIT=10/minute
MAX_FILE_SIZE_MB=50

# --- Development Flags ---
ENVIRONMENT=development
DEBUG=true
EOL

echo "✅ Secure infrastructure .env file created at ${ENV_FILE}"
echo "📝 Credentials generated for:"
echo "   - PostgreSQL (user, password, databases: healthapi, webauthn)"
echo "   - Redis (no auth required for dev)"
echo "   - MinIO (access key, secret key, KMS key)"
echo "   - RabbitMQ (user, password)"
echo "   - Health API (secret key)"
echo "   - WebAuthn (uses postgres & redis credentials)"
