#!/bin/bash
# Manage ETL Narrative Engine stack
#
# This script provides convenient commands for managing the ETL stack
# including starting, stopping, monitoring, and debugging.

COMMAND=${1:-help}

case $COMMAND in
  start)
    echo "========================================="
    echo "Starting ETL Narrative Engine Stack"
    echo "========================================="
    echo ""

    # Check if webauthn-stack should be started (for Jaeger tracing)
    if [ -d "webauthn-stack/docker" ]; then
        echo "🔐 Starting WebAuthn stack (for Jaeger tracing)..."
        cd webauthn-stack/docker && docker compose up -d && cd ../..
        echo "✅ WebAuthn stack started"
        echo ""
    fi

    # Start health services stack
    echo "🏥 Starting health services stack..."
    docker compose up -d
    echo "✅ Health services stack started"
    echo ""

    # Wait for services to be ready
    echo "⏳ Waiting for services to be ready..."
    sleep 5
    echo ""

    # Show service status
    echo "📊 Service Status:"
    docker compose ps
    echo ""

    echo "========================================="
    echo "✅ ETL Stack Started Successfully"
    echo "========================================="
    echo ""
    echo "🔗 Available Endpoints:"
    echo "   • ETL Metrics:  http://localhost:8004/metrics"
    echo "   • ETL Health:   http://localhost:8004/health"
    echo "   • RabbitMQ UI:  http://localhost:15672 (guest/guest)"
    echo "   • MinIO UI:     http://localhost:9001 (minioadmin/minioadmin)"
    if [ -d "webauthn-stack/docker" ]; then
        echo "   • Jaeger UI:    http://localhost:16687"
    fi
    echo ""
    ;;

  stop)
    echo "========================================="
    echo "Stopping ETL Narrative Engine Stack"
    echo "========================================="
    echo ""

    echo "🛑 Stopping health services stack..."
    docker compose down
    echo "✅ Health services stopped"
    echo ""

    if [ -d "webauthn-stack/docker" ]; then
        echo "🛑 Stopping WebAuthn stack..."
        cd webauthn-stack/docker && docker compose down && cd ../..
        echo "✅ WebAuthn stack stopped"
    fi

    echo ""
    echo "✅ ETL stack stopped"
    ;;

  logs)
    echo "📜 Showing ETL logs (Ctrl+C to exit)..."
    echo ""
    docker compose logs -f etl-narrative-engine
    ;;

  restart)
    echo "🔄 Restarting ETL Narrative Engine..."
    docker compose restart etl-narrative-engine
    echo "✅ ETL service restarted"
    echo ""
    echo "View logs with: $0 logs"
    ;;

  rebuild)
    echo "========================================="
    echo "Rebuilding ETL Narrative Engine"
    echo "========================================="
    echo ""

    echo "🔨 Building ETL service..."
    docker compose build etl-narrative-engine

    echo ""
    echo "🚀 Starting ETL service..."
    docker compose up -d etl-narrative-engine

    echo ""
    echo "✅ ETL service rebuilt and restarted"
    echo ""
    echo "View logs with: $0 logs"
    ;;

  test)
    echo "========================================="
    echo "Running ETL Tests"
    echo "========================================="
    echo ""

    if docker compose ps etl-narrative-engine | grep -q "running"; then
        echo "🧪 Running tests inside ETL container..."
        docker compose exec etl-narrative-engine pytest /app/tests/ -v
    else
        echo "❌ ETL service is not running"
        echo ""
        echo "Start it first with: $0 start"
        exit 1
    fi
    ;;

  shell)
    echo "🐚 Opening shell in ETL container..."
    echo ""

    if docker compose ps etl-narrative-engine | grep -q "running"; then
        docker compose exec etl-narrative-engine /bin/bash
    else
        echo "❌ ETL service is not running"
        echo ""
        echo "Start it first with: $0 start"
        exit 1
    fi
    ;;

  metrics)
    echo "========================================="
    echo "Current ETL Metrics"
    echo "========================================="
    echo ""

    if curl -s http://localhost:8004/metrics > /dev/null 2>&1; then
        curl -s http://localhost:8004/metrics | grep "^etl_" | grep -v "^#"
    else
        echo "❌ Metrics endpoint not accessible"
        echo ""
        echo "Make sure ETL service is running: $0 start"
        exit 1
    fi
    ;;

  health)
    echo "========================================="
    echo "ETL Health Status"
    echo "========================================="
    echo ""

    if command -v jq > /dev/null 2>&1; then
        curl -s http://localhost:8004/health | jq
    else
        curl -s http://localhost:8004/health
    fi
    echo ""
    ;;

  status)
    echo "========================================="
    echo "ETL Stack Status"
    echo "========================================="
    echo ""

    echo "🐳 Docker Services:"
    docker compose ps
    echo ""

    if curl -s http://localhost:8004/health > /dev/null 2>&1; then
        echo "📊 ETL Health:"
        if command -v jq > /dev/null 2>&1; then
            curl -s http://localhost:8004/health | jq '.status, .dependencies'
        else
            curl -s http://localhost:8004/health
        fi
        echo ""
    else
        echo "⚠️  ETL metrics endpoint not accessible"
        echo ""
    fi
    ;;

  load-sample)
    echo "📦 Loading sample data..."
    echo ""
    ./scripts/load-sample-data.sh
    ;;

  *)
    echo "========================================="
    echo "ETL Narrative Engine Stack Management"
    echo "========================================="
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo ""
    echo "  🚀 Stack Management:"
    echo "    start       - Start the full ETL stack (including WebAuthn for Jaeger)"
    echo "    stop        - Stop the ETL stack"
    echo "    restart     - Restart ETL service"
    echo "    rebuild     - Rebuild and restart ETL service"
    echo "    status      - Show stack status"
    echo ""
    echo "  📊 Monitoring:"
    echo "    logs        - View ETL logs (live tail)"
    echo "    metrics     - Show current Prometheus metrics"
    echo "    health      - Check health status"
    echo ""
    echo "  🔧 Development:"
    echo "    test        - Run tests inside container"
    echo "    shell       - Open shell in ETL container"
    echo "    load-sample - Load sample data and trigger processing"
    echo ""
    echo "Examples:"
    echo "  $0 start              # Start the full stack"
    echo "  $0 logs               # View logs"
    echo "  $0 metrics            # Show metrics"
    echo "  $0 load-sample        # Load sample data"
    echo ""
    echo "========================================="
    ;;
esac
