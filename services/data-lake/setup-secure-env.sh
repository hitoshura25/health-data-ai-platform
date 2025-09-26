#!/bin/bash

# This script generates a secure .env file for the data-lake service.

# Function to generate a secure random string
generate_secret() {
  openssl rand -hex 24
}

# Function to generate a secure random base64 string for KMS
generate_kms_key() {
  openssl rand -base64 32
}

# Set the path for the .env file
ENV_FILE="./.env"

# Generate credentials
DATALAKE_MINIO_ACCESS_KEY=$(generate_secret)
DATALAKE_MINIO_SECRET_KEY=$(generate_secret)
DATALAKE_MINIO_KMS_KEY=$(generate_kms_key)

# Create the .env file
cat > "$ENV_FILE" << EOL
# MinIO Configuration
DATALAKE_MINIO_ENDPOINT=localhost:9000
DATALAKE_MINIO_ACCESS_KEY=${DATALAKE_MINIO_ACCESS_KEY}
DATALAKE_MINIO_SECRET_KEY=${DATALAKE_MINIO_SECRET_KEY}
DATALAKE_MINIO_KMS_SECRET_KEY=my-minio-key:${DATALAKE_MINIO_KMS_KEY}
DATALAKE_MINIO_SECURE=false
DATALAKE_MINIO_REGION=us-east-1

# Bucket Configuration
DATALAKE_BUCKET_NAME=health-data
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
DATALAKE_METRICS_PORT=8002
DATALAKE_ANALYTICS_UPDATE_INTERVAL_HOURS=6
EOL

echo "✅ Secure .env file created at ${ENV_FILE}"