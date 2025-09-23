#!/bin/bash

# Health Data AI Platform - Test All Services Script
# This script runs tests for all services in the platform

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

# Services to be implemented (currently empty - tests will be added as services are implemented)
SERVICES=()

# Track test results
declare -A test_results

# Run tests for a specific service
run_service_tests() {
    local service=$1
    local service_dir="services/${service}"

    print_status "Running tests for ${service}..."

    if [ ! -d "$service_dir" ]; then
        print_warning "Service directory ${service_dir} not found, skipping"
        test_results[$service]="SKIPPED"
        return
    fi

    # Check if service has tests
    if [ ! -d "${service_dir}/tests" ] && [ ! -f "${service_dir}/pytest.ini" ] && [ ! -f "${service_dir}/test_*.py" ]; then
        print_warning "No tests found for ${service}, skipping"
        test_results[$service]="NO_TESTS"
        return
    fi

    # Run tests based on what's available
    cd "$service_dir"

    local test_command=""
    if [ -f "requirements.txt" ]; then
        # Python service - use pytest
        if command -v pytest &> /dev/null; then
            test_command="pytest -v"
        elif python -m pytest --version &> /dev/null 2>&1; then
            test_command="python -m pytest -v"
        else
            print_warning "pytest not found for ${service}, attempting to install"
            pip install pytest pytest-asyncio pytest-cov
            test_command="python -m pytest -v"
        fi
    elif [ -f "package.json" ]; then
        # Node.js service - use npm test
        if command -v npm &> /dev/null; then
            test_command="npm test"
        else
            print_error "npm not found for Node.js service ${service}"
            test_results[$service]="ERROR"
            cd - > /dev/null
            return
        fi
    elif [ -f "Cargo.toml" ]; then
        # Rust service - use cargo test
        if command -v cargo &> /dev/null; then
            test_command="cargo test"
        else
            print_error "cargo not found for Rust service ${service}"
            test_results[$service]="ERROR"
            cd - > /dev/null
            return
        fi
    else
        print_warning "Unable to determine test framework for ${service}"
        test_results[$service]="UNKNOWN"
        cd - > /dev/null
        return
    fi

    # Execute tests
    if eval "$test_command"; then
        print_success "Tests passed for ${service}"
        test_results[$service]="PASSED"
    else
        print_error "Tests failed for ${service}"
        test_results[$service]="FAILED"
    fi

    cd - > /dev/null
}

# Run shared components tests
run_shared_tests() {
    print_status "Running shared components tests..."

    if [ -d "shared/tests" ]; then
        cd shared
        if python -m pytest tests/ -v; then
            print_success "Shared components tests passed"
            test_results["shared"]="PASSED"
        else
            print_error "Shared components tests failed"
            test_results["shared"]="FAILED"
        fi
        cd - > /dev/null
    else
        print_warning "No shared tests found"
        test_results["shared"]="NO_TESTS"
    fi
}

# Run integration tests (currently only infrastructure connectivity tests)
run_integration_tests() {
    print_status "Running integration tests..."

    if [ -d "tests/integration" ]; then
        if python -m pytest tests/integration/ -v; then
            print_success "Integration tests passed"
            test_results["integration"]="PASSED"
        else
            print_error "Integration tests failed"
            test_results["integration"]="FAILED"
        fi
    else
        print_warning "No integration tests found - will be added as services are implemented"
        test_results["integration"]="NO_TESTS"
    fi
}

# Generate test report
generate_report() {
    echo
    print_status "Test Results Summary"
    echo "===================="

    local total=0
    local passed=0
    local failed=0
    local skipped=0

    for service in "shared" "integration"; do
        local result=${test_results[$service]:-"NOT_RUN"}
        local status_color=""
        local status_symbol=""

        case $result in
            "PASSED")
                status_color=$GREEN
                status_symbol="✅"
                ((passed++))
                ((total++))
                ;;
            "FAILED")
                status_color=$RED
                status_symbol="❌"
                ((failed++))
                ((total++))
                ;;
            "SKIPPED"|"NO_TESTS"|"UNKNOWN")
                status_color=$YELLOW
                status_symbol="⚠️"
                ((skipped++))
                ;;
            *)
                status_color=$RED
                status_symbol="❌"
                ((failed++))
                ((total++))
                ;;
        esac

        printf "  %-25s %s %s%s%s\n" "$service" "$status_symbol" "$status_color" "$result" "$NC"
    done

    echo
    print_status "Summary:"
    echo "  Total: $((total + skipped))"
    echo "  Passed: $passed"
    echo "  Failed: $failed"
    echo "  Skipped: $skipped"

    if [ $failed -gt 0 ]; then
        echo
        print_error "Some tests failed!"
        exit 1
    else
        echo
        print_success "All tests passed!"
    fi
}

# Main execution
main() {
    echo "🧪 Health Data AI Platform - Test Suite"
    echo "======================================="
    echo

    # Ensure we're in the project root
    if [ ! -f "docker-compose.yml" ]; then
        print_error "Please run this script from the project root directory"
        exit 1
    fi

    # Check if infrastructure is running (for integration tests)
    if ! docker-compose ps | grep -q "Up"; then
        print_warning "Infrastructure services don't appear to be running"
        print_warning "Some integration tests may fail"
        echo
    fi

    # Run shared tests first
    run_shared_tests

    # Service tests will be added here as services are implemented
    # Currently no services exist yet - only shared components and infrastructure

    # Run integration tests (currently only infrastructure connectivity)
    run_integration_tests

    # Generate report
    generate_report
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --service)
            SERVICE="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [--service SERVICE_NAME] [--help]"
            echo
            echo "Options:"
            echo "  --service SERVICE_NAME    Run tests for specific service only"
            echo "  --help                   Show this help message"
            echo
            echo "Current test suites:"
            echo "  shared                   Shared components (schemas, types, validation)"
            echo "  integration              Infrastructure connectivity tests"
            echo
            echo "Note: Service tests will be added as services are implemented"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Run specific service or all tests
if [ -n "$SERVICE" ]; then
    echo "🧪 Running tests for: $SERVICE"
    echo "================================"
    echo
    run_service_tests "$SERVICE"
    echo
    if [ "${test_results[$SERVICE]}" = "PASSED" ]; then
        print_success "Tests passed for $SERVICE"
    else
        print_error "Tests failed for $SERVICE"
        exit 1
    fi
else
    main "$@"
fi