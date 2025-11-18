#!/bin/bash
# Load sample Avro files and trigger ETL processing
#
# This script:
# 1. Uploads sample Avro files to MinIO
# 2. Publishes messages to RabbitMQ to trigger ETL processing
# 3. Monitors processing via metrics endpoint

set -e

SAMPLE_DIR="docs/sample-avro-files"
BUCKET="health-data"
S3_ENDPOINT="http://localhost:9000"
RABBITMQ_HOST="localhost"
RABBITMQ_PORT="5672"

echo "========================================="
echo "Loading Sample Health Data Files"
echo "========================================="
echo ""

# Check if sample files directory exists
if [ ! -d "$SAMPLE_DIR" ]; then
    echo "❌ Sample files directory not found: $SAMPLE_DIR"
    exit 1
fi

# Count sample files
FILE_COUNT=$(find "$SAMPLE_DIR" -name "*.avro" | wc -l)
echo "📁 Found $FILE_COUNT sample Avro files"
echo ""

# Check if MinIO is running
if ! docker compose ps minio | grep -q "running"; then
    echo "❌ MinIO is not running. Start it with:"
    echo "   docker compose up -d minio"
    exit 1
fi

# Check if RabbitMQ is running
if ! docker compose ps rabbitmq | grep -q "running"; then
    echo "❌ RabbitMQ is not running. Start it with:"
    echo "   docker compose up -d rabbitmq"
    exit 1
fi

echo "✅ Infrastructure services are running"
echo ""

# Upload files and publish messages
PROCESSED=0
FAILED=0

for file in "$SAMPLE_DIR"/*.avro; do
    filename=$(basename "$file")
    # Extract record type from filename (e.g., BloodGlucoseRecord from BloodGlucoseRecord_1758407139312.avro)
    record_type=$(echo "$filename" | sed 's/_[0-9]\+\.avro//')

    echo "📤 Processing: $filename (type: $record_type)"

    # Generate S3 key with date partitioning
    year=$(date +%Y)
    month=$(date +%m)
    day=$(date +%d)
    s3_key="raw/$record_type/$year/$month/$day/$filename"

    # Upload to MinIO using mc command in container
    echo "   ↳ Uploading to MinIO: $s3_key"
    if docker compose exec -T minio mc cp "/sample-avro-files/$filename" "myminio/$BUCKET/$s3_key" 2>/dev/null; then
        echo "   ✅ Uploaded to MinIO"
    else
        # Try alternative method: copy to container first
        docker cp "$file" "$(docker compose ps -q minio):/tmp/$filename"
        docker compose exec -T minio mc cp "/tmp/$filename" "myminio/$BUCKET/$s3_key"
        echo "   ✅ Uploaded to MinIO (alternative method)"
    fi

    # Publish message to RabbitMQ to trigger processing
    echo "   ↳ Publishing message to RabbitMQ..."

    # Use Python to publish message
    python3 <<EOF
import pika
import json
import uuid
from datetime import datetime

try:
    connection = pika.BlockingConnection(
        pika.ConnectionParameters('$RABBITMQ_HOST', $RABBITMQ_PORT)
    )
    channel = connection.channel()

    # Declare exchange and queue (idempotent)
    channel.exchange_declare(
        exchange='health_data_exchange',
        exchange_type='topic',
        durable=True
    )

    channel.queue_declare(
        queue='health_data_processing',
        durable=True
    )

    channel.queue_bind(
        exchange='health_data_exchange',
        queue='health_data_processing',
        routing_key='health.processing.#'
    )

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
        routing_key='health.processing.data',
        body=json.dumps(message),
        properties=pika.BasicProperties(
            delivery_mode=2,  # make message persistent
            content_type='application/json'
        )
    )

    connection.close()
    print("   ✅ Message published successfully")
    exit(0)

except Exception as e:
    print(f"   ❌ Failed to publish message: {e}")
    exit(1)
EOF

    if [ $? -eq 0 ]; then
        ((PROCESSED++))
    else
        ((FAILED++))
    fi

    echo ""
done

# Summary
echo "========================================="
echo "Upload Summary"
echo "========================================="
echo "✅ Successfully processed: $PROCESSED files"
if [ $FAILED -gt 0 ]; then
    echo "❌ Failed: $FAILED files"
fi
echo ""

# Check if ETL service is running
if docker compose ps etl-narrative-engine | grep -q "running"; then
    echo "✅ ETL Narrative Engine is running and will process the messages"
    echo ""
    echo "📊 Monitor processing:"
    echo "   docker compose logs -f etl-narrative-engine"
    echo ""
    echo "📈 Check metrics:"
    echo "   curl -s http://localhost:8004/metrics | grep etl_messages_processed_total"
    echo ""
    echo "🔍 Check health:"
    echo "   curl -s http://localhost:8004/health | jq"
else
    echo "⚠️  ETL Narrative Engine is not running"
    echo ""
    echo "Start it with:"
    echo "   docker compose up -d etl-narrative-engine"
    echo "   docker compose logs -f etl-narrative-engine"
fi

echo ""
echo "========================================="
