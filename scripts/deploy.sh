#!/bin/bash

# Health Data AI Platform - Deployment Script
# This script handles deployment to different environments

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Default values
ENVIRONMENT=""
RUN_TESTS=true
SKIP_CONFIRMATION=false

# Show usage
show_usage() {
    echo "Usage: $0 --env ENVIRONMENT [OPTIONS]"
    echo
    echo "Environments:"
    echo "  development    Deploy infrastructure to local development environment"
    echo
    echo "Options:"
    echo "  --skip-tests   Skip running tests before deployment"
    echo "  --yes          Skip confirmation prompts"
    echo "  --help         Show this help message"
    echo
    echo "Note: Currently only infrastructure deployment is supported."
    echo "Application services will be added as they are implemented."
    echo
    echo "Examples:"
    echo "  $0 --env development"
    echo "  $0 --env development --skip-tests"
}

# Validate environment
validate_environment() {
    case $ENVIRONMENT in
        development)
            ;;
        staging|production)
            print_error "Environment '$ENVIRONMENT' not yet supported. Only 'development' is currently available."
            print_error "Staging and production deployment will be added as services are implemented."
            exit 1
            ;;
        *)
            print_error "Invalid environment: $ENVIRONMENT"
            show_usage
            exit 1
            ;;
    esac
}

# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites for $ENVIRONMENT deployment..."

    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        exit 1
    fi

    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose is not installed"
        exit 1
    fi

    # Check if Docker is running
    if ! docker info &> /dev/null; then
        print_error "Docker is not running. Please start Docker first."
        exit 1
    fi

    print_success "Prerequisites check passed"
}

# Run tests
run_tests() {
    if [ "$RUN_TESTS" = true ]; then
        print_status "Running tests before deployment..."

        if ! ./scripts/test-all.sh; then
            print_error "Tests failed. Aborting deployment."
            exit 1
        fi

        print_success "All tests passed"
    else
        print_warning "Skipping tests"
    fi
}

# Note: Image building will be added as services are implemented
# Currently only infrastructure services are deployed

# Deploy to development
deploy_development() {
    print_status "Deploying infrastructure to development environment..."

    # Stop existing services
    docker-compose down || true

    # Start infrastructure services
    docker-compose up -d rabbitmq minio redis postgres mlflow

    # Wait for infrastructure to be ready
    print_status "Waiting for infrastructure services to be healthy..."
    sleep 30

    print_success "Infrastructure deployment completed"
    print_status "Infrastructure services available at:"
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
}

# Staging and production deployments will be added as services are implemented

# Main deployment function
deploy() {
    case $ENVIRONMENT in
        development)
            deploy_development
            ;;
        *)
            print_error "Environment $ENVIRONMENT is not yet supported"
            exit 1
            ;;
    esac
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --skip-tests)
            RUN_TESTS=false
            shift
            ;;
        --yes)
            SKIP_CONFIRMATION=true
            shift
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate required parameters
if [ -z "$ENVIRONMENT" ]; then
    print_error "Environment is required"
    show_usage
    exit 1
fi

# Main execution
main() {
    echo "🚀 Health Data AI Platform - Deployment"
    echo "========================================"
    echo

    validate_environment
    check_prerequisites
    run_tests
    deploy

    print_success "Deployment to $ENVIRONMENT completed successfully!"
}

# Run main function
main "$@"