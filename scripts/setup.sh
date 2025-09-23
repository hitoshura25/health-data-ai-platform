#!/bin/bash

# Health Data AI Platform - Development Setup Script
# This script sets up the development environment for the health data AI platform

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."

    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi

    # Check if Docker is running
    if ! docker info &> /dev/null; then
        print_error "Docker is not running. Please start Docker first."
        exit 1
    fi

    print_success "Prerequisites check passed"
}

# Setup environment files
setup_environment() {
    print_status "Setting up environment files..."

    # Create .env file if it doesn't exist
    if [ ! -f .env ]; then
        cat > .env << EOF
# Development Environment Configuration
ENVIRONMENT=development

# Database Configuration
DATABASE_URL=postgresql://health_user:health_password@localhost:5432/health_platform

# Message Queue Configuration
RABBITMQ_URL=amqp://health_user:health_password@localhost:5672/health_data

# Object Storage Configuration
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=admin
MINIO_SECRET_KEY=password123
MINIO_BUCKET=health-data

# Redis Configuration
REDIS_URL=redis://localhost:6379

# MLflow Configuration
MLFLOW_TRACKING_URI=http://localhost:5000

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Logging Configuration
LOG_LEVEL=INFO
LOG_FORMAT=json

# Security Configuration (Change in production!)
SECRET_KEY=development-secret-key-change-in-production
JWT_SECRET=development-jwt-secret-change-in-production
EOF
        print_success "Created .env file"
    else
        print_warning ".env file already exists, skipping creation"
    fi
}

# Create necessary directories
create_directories() {
    print_status "Creating necessary directories..."

    # Create data directories for persistent storage
    mkdir -p data/{postgres,minio,redis,mlflow}
    mkdir -p logs

    # Create shared component test directory
    mkdir -p shared/tests

    print_success "Directories created"
}

# Setup infrastructure
setup_infrastructure() {
    print_status "Starting infrastructure services..."

    # Start only infrastructure services
    docker-compose up -d rabbitmq minio redis postgres mlflow

    print_status "Waiting for services to be healthy..."

    # Wait for services to be ready
    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if docker-compose ps | grep -q "unhealthy\|starting"; then
            print_status "Waiting for services... (attempt $attempt/$max_attempts)"
            sleep 10
            attempt=$((attempt + 1))
        else
            break
        fi
    done

    if [ $attempt -gt $max_attempts ]; then
        print_error "Services failed to start within expected time"
        exit 1
    fi

    print_success "Infrastructure services are running"
}

# Setup MinIO buckets
setup_minio() {
    print_status "Setting up MinIO buckets..."

    # Wait a bit more for MinIO to be fully ready
    sleep 5

    # Install MinIO client if not present
    if ! command -v mc &> /dev/null; then
        print_status "Installing MinIO client..."
        if [[ "$OSTYPE" == "darwin"* ]]; then
            if command -v brew &> /dev/null; then
                brew install minio/stable/mc
            else
                print_warning "Homebrew not found. Please install MinIO client manually."
                return
            fi
        else
            print_warning "Please install MinIO client (mc) manually for your platform."
            return
        fi
    fi

    # Configure MinIO client
    mc alias set local http://localhost:9000 admin password123

    # Create buckets
    mc mb local/health-data --ignore-existing
    mc mb local/mlflow-artifacts --ignore-existing
    mc mb local/training-data --ignore-existing
    mc mb local/quarantine --ignore-existing

    print_success "MinIO buckets created"
}

# Setup RabbitMQ
setup_rabbitmq() {
    print_status "Setting up RabbitMQ exchanges and queues..."

    # Wait for RabbitMQ to be ready
    sleep 5

    # Setup exchanges and queues using management API
    curl -u health_user:health_password -X PUT \
        "http://localhost:15672/api/exchanges/health_data/health_data_exchange" \
        -H "content-type:application/json" \
        -d '{"type":"topic","durable":true}' || true

    curl -u health_user:health_password -X PUT \
        "http://localhost:15672/api/exchanges/health_data/health_data_dlx" \
        -H "content-type:application/json" \
        -d '{"type":"topic","durable":true}' || true

    curl -u health_user:health_password -X PUT \
        "http://localhost:15672/api/queues/health_data/health_data_processing" \
        -H "content-type:application/json" \
        -d '{"durable":true,"arguments":{"x-message-ttl":1800000,"x-dead-letter-exchange":"health_data_dlx"}}' || true

    print_success "RabbitMQ setup completed"
}

# Display service URLs
display_urls() {
    print_success "Development environment is ready!"
    echo
    print_status "Service URLs:"
    echo "  🐰 RabbitMQ Management: http://localhost:15672 (health_user/health_password)"
    echo "  🗄️  MinIO Console: http://localhost:9001 (admin/password123)"
    echo "  📊 MLflow UI: http://localhost:5000"
    echo "  🔄 Redis: localhost:6379"
    echo "  🐘 PostgreSQL: localhost:5432 (health_user/health_password)"
    echo
    print_status "Next steps:"
    echo "  📖 Read implementation plans: services/{service-name}/implementation_plan.md"
    echo "  🔧 Use service template: services/_template/ (to be created)"
    echo "  🧪 Test shared components: cd shared && python -m pytest tests/"
    echo
    print_status "To view logs:"
    echo "  docker-compose logs -f [service-name]"
    echo
    print_status "To stop all services:"
    echo "  docker-compose down"
}

# Main execution
main() {
    echo "🏥 Health Data AI Platform - Development Setup"
    echo "=============================================="
    echo

    check_prerequisites
    setup_environment
    create_directories
    setup_infrastructure
    setup_minio
    setup_rabbitmq
    display_urls
}

# Run main function
main "$@"