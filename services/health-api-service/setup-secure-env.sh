#!/bin/bash

# This script generates a secure .env file for the health-api service.

# Function to generate a secure random string
generate_short_secret() {
  openssl rand -hex 16
}

generate_long_secret() {
  openssl rand -hex 32
}

# Set the path for the .env file
ENV_FILE="$(dirname "$0")/./.env"

# --- Credentials Generation ---
SECRET_KEY=$(generate_long_secret)
POSTGRES_USER=$(generate_short_secret)
POSTGRES_PASSWORD=$(generate_long_secret)
MINIO_ROOT_PASSWORD=$(generate_long_secret)
RABBITMQ_DEFAULT_USER=$(generate_short_secret)
RABBITMQ_DEFAULT_PASS=$(generate_long_secret)

# --- Static Configuration ---
POSTGRES_DB="health-db"
MINIO_ROOT_USER="minioadmin"

# --- Create the .env file ---
# The URLs are configured for local development/testing, pointing to localhost
# where Docker containers expose their ports.
cat > "$ENV_FILE" << EOL
# FastAPI Users Secret
SECRET_KEY=${SECRET_KEY}

# Application Connection URLs
DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB}
REDIS_URL=redis://localhost:6379
S3_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY=${MINIO_ROOT_USER}
S3_SECRET_KEY=${MINIO_ROOT_PASSWORD}
S3_BUCKET_NAME=health-data
RABBITMQ_URL=amqp://${RABBITMQ_DEFAULT_USER}:${RABBITMQ_DEFAULT_PASS}@localhost:5672/

# Rate Limiting and File Size
UPLOAD_RATE_LIMIT=10/minute
UPLOAD_RATE_LIMIT_STORAGE_URI=redis://localhost:6379
MAX_FILE_SIZE_MB=50

# --- Docker Compose Variables ---
# These are used by the docker-compose.yml file

# PostgreSQL
POSTGRES_DB=${POSTGRES_DB}
POSTGRES_USER=${POSTGRES_USER}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}

# MinIO
MINIO_ROOT_USER=${MINIO_ROOT_USER}
MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD}

# RabbitMQ
RABBITMQ_DEFAULT_USER=${RABBITMQ_DEFAULT_USER}
RABBITMQ_DEFAULT_PASS=${RABBITMQ_DEFAULT_PASS}
RABBITMQ_MAIN_EXCHANGE=health_data_exchange
EOL

echo "✅ Secure .env file created at ${ENV_FILE}"
echo "Please run 'source .env' or restart your shell if you are using auto-env loading."