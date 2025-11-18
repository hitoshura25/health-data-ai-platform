#!/bin/bash
# Setup local development environment for ETL Narrative Engine
#
# This script:
# 1. Creates Python virtual environment
# 2. Installs dependencies
# 3. Creates environment file
# 4. Starts infrastructure services
# 5. Initializes MinIO bucket
# 6. Runs tests to verify setup

set -e

echo "========================================="
echo "ETL Narrative Engine Development Setup"
echo "========================================="
echo ""

# Change to project root
cd "$(dirname "$0")/.."

# 1. Create Python virtual environment
echo "📦 Creating Python virtual environment..."
if [ ! -d ".venv" ]; then
    python3.11 -m venv .venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
source .venv/bin/activate

# 2. Install dependencies
echo ""
echo "📥 Installing Python dependencies..."
pip install --upgrade pip --quiet
pip install -r services/etl-narrative-engine/requirements.txt --quiet
echo "✅ Dependencies installed"

# 3. Create environment file if not exists
echo ""
echo "📝 Setting up environment configuration..."
if [ ! -f services/etl-narrative-engine/.env ]; then
    cp services/etl-narrative-engine/.env.template services/etl-narrative-engine/.env
    echo "✅ Created .env file from template"
    echo "⚠️  Please review and update services/etl-narrative-engine/.env if needed"
else
    echo "✅ .env file already exists"
fi

# 4. Start infrastructure services (MinIO, RabbitMQ, Redis, PostgreSQL)
echo ""
echo "🐳 Starting infrastructure services with docker-compose..."
docker compose up -d minio rabbitmq redis postgres

# 5. Wait for services to be ready
echo ""
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check if services are running
echo ""
echo "🔍 Checking service health..."

# Check RabbitMQ
if docker compose ps rabbitmq | grep -q "running"; then
    echo "✅ RabbitMQ is running"
else
    echo "❌ RabbitMQ is not running"
    exit 1
fi

# Check MinIO
if docker compose ps minio | grep -q "running"; then
    echo "✅ MinIO is running"
else
    echo "❌ MinIO is not running"
    exit 1
fi

# Check Redis
if docker compose ps redis | grep -q "running"; then
    echo "✅ Redis is running"
else
    echo "❌ Redis is not running"
    exit 1
fi

# 6. Initialize MinIO bucket
echo ""
echo "🪣 Initializing MinIO bucket..."
# Check if mc (MinIO Client) is available in the MinIO container
if docker compose exec -T minio mc --version > /dev/null 2>&1; then
    docker compose exec -T minio mc alias set myminio http://localhost:9000 minioadmin minioadmin || true
    docker compose exec -T minio mc mb myminio/health-data --ignore-existing || true
    echo "✅ MinIO bucket initialized"
else
    echo "⚠️  MinIO client not available, skipping bucket initialization"
    echo "   You may need to create the 'health-data' bucket manually"
fi

# 7. Run tests to verify setup
echo ""
echo "🧪 Running tests to verify setup..."
if pytest services/etl-narrative-engine/tests/ -v --tb=short; then
    echo "✅ All tests passed"
else
    echo "⚠️  Some tests failed, but setup is complete"
fi

# Final summary
echo ""
echo "========================================="
echo "✅ Development environment setup complete!"
echo "========================================="
echo ""
echo "📚 Next steps:"
echo ""
echo "1. Activate virtual environment:"
echo "   source .venv/bin/activate"
echo ""
echo "2. Run the ETL service locally:"
echo "   python -m services.etl_narrative_engine.src.main"
echo ""
echo "3. Or run with Docker Compose:"
echo "   docker compose up -d etl-narrative-engine"
echo "   docker compose logs -f etl-narrative-engine"
echo ""
echo "4. Run tests:"
echo "   pytest services/etl-narrative-engine/tests/"
echo ""
echo "5. Check metrics:"
echo "   curl http://localhost:8004/metrics"
echo "   curl http://localhost:8004/health | jq"
echo ""
echo "6. Load sample data:"
echo "   ./scripts/load-sample-data.sh"
echo ""
echo "========================================="
