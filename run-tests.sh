#!/bin/bash
# Test runner for Health Data AI Platform microservices
# Each service runs in isolation with its own Python path

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Ensure virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${RED}Error: Virtual environment not activated${NC}"
    echo "Please run: source .venv/bin/activate"
    exit 1
fi

# Parse command line arguments
SERVICE="$1"
PYTEST_ARGS="${@:2}"

run_service_tests() {
    local service_name=$1
    local service_path=$2
    shift 2
    local args="$@"

    echo -e "${BLUE}Running tests for ${service_name}...${NC}"
    export PYTHONPATH="${service_path}"
    pytest "${service_path}/tests/" $args
    unset PYTHONPATH
}

# Run tests based on argument
case "$SERVICE" in
    "health-api")
        run_service_tests "Health API" "services/health-api-service" $PYTEST_ARGS
        ;;
    "data-lake")
        run_service_tests "Data Lake" "services/data-lake" $PYTEST_ARGS
        ;;
    "message-queue")
        run_service_tests "Message Queue" "services/message-queue" $PYTEST_ARGS
        ;;
    "all")
        echo -e "${BLUE}Running all service tests...${NC}\n"
        run_service_tests "Data Lake" "services/data-lake" $PYTEST_ARGS
        echo ""
        run_service_tests "Message Queue" "services/message-queue" $PYTEST_ARGS
        echo ""
        run_service_tests "Health API" "services/health-api-service" $PYTEST_ARGS
        echo ""
        echo -e "\n${GREEN}All tests completed!${NC}"

        ;;
    *)
        echo "Usage: ./run-tests.sh {health-api|data-lake|message-queue|all} [pytest-args]"
        echo ""
        echo "Examples:"
        echo "  ./run-tests.sh all                    # Run all tests"
        echo "  ./run-tests.sh health-api             # Run health-api tests"
        echo "  ./run-tests.sh message-queue -v       # Run message-queue tests verbosely"
        echo "  ./run-tests.sh health-api -k upload   # Run health-api tests matching 'upload'"
        exit 1
        ;;
esac
