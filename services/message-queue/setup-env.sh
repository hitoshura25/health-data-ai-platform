#!/bin/bash

# This script generates a secure .env file for the message-queue service.

# Function to generate a secure random string
generate_secret() {
  openssl rand -base64 24
}

# Set the path for the .env file
ENV_FILE="./.env"

# Generate credentials
MQ_RABBITMQ_USER=$(generate_secret)
MQ_RABBITMQ_PASS=$(generate_secret)

# Create the .env file
cat > "$ENV_FILE" << EOL
# RabbitMQ Configuration
MQ_RABBITMQ_URL=amqp://${MQ_RABBITMQ_USER}:${MQ_RABBITMQ_PASS}@localhost:5672
MQ_RABBITMQ_MANAGEMENT_URL=http://localhost:15672
MQ_RABBITMQ_USER=${MQ_RABBITMQ_USER}
MQ_RABBITMQ_PASS=${MQ_RABBITMQ_PASS}

# Exchange and Queue Names
MQ_MAIN_EXCHANGE=health_data_exchange
MQ_DLX_EXCHANGE=health_data_dlx
MQ_PROCESSING_QUEUE=health_data_processing
MQ_FAILED_QUEUE=health_data_failed

# Retry Configuration
MQ_MAX_RETRIES=3
MQ_RETRY_DELAYS=[30, 300, 900]

# Redis
MQ_REDIS_URL=redis://localhost:6379

# Deduplication
MQ_DEDUPLICATION_RETENTION_HOURS=72

# Message Settings
MQ_MESSAGE_TTL_SECONDS=1800
MQ_ENABLE_PUBLISHER_CONFIRMS=true

# Monitoring
MQ_ENABLE_METRICS=true
MQ_METRICS_PORT=8001
EOL

echo "✅ Secure .env file created at ${ENV_FILE}"
echo "RabbitMQ User: ${MQ_RABBITMQ_USER}"
