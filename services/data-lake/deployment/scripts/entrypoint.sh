#!/bin/sh

set -e

host="minio"
port="9000"

# Wait for the service to be available
until nc -z "$host" "$port"; do
  echo "Waiting for $host:$port..."
  sleep 1
done

echo "$host:$port is available"

# Run the setup script
python deployment/scripts/setup_bucket.py
