# Health Data AI Platform

An end-to-end pipeline that automatically collects health data from Android Health Connect, stores it in a cloud backend, processes it into clinical narratives, and uses this data to fine-tune and query a personal AI model.

## 🏗️ Architecture Overview

This platform consists of two separate stacks working together:

**WebAuthn Stack** - Zero-trust authentication and observability:
- Envoy Gateway (port 8000) - Entry point
- WebAuthn Server - FIDO2/Passkey authentication
- Jaeger - Distributed tracing for all services
- Dedicated PostgreSQL + Redis

**Health Services Stack** - Data processing pipeline:
- Health API (port 8001) - Upload and query service
- Data Lake (MinIO) - S3-compatible storage
- Message Queue (RabbitMQ) - Async processing
- ETL Narrative Engine (planned) - Clinical data processing
- AI Query Interface (planned) - MLflow-powered queries
- Dedicated PostgreSQL + Redis

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed design decisions.

## 🚀 Quick Start (Under 2 Minutes!)

```bash
# 1. Clone and setup
git clone <repository-url>
cd health-data-ai-platform
./setup-all-services.sh

# 2. Start WebAuthn stack (authentication + tracing)
cd webauthn-stack/docker && docker compose up -d && cd ../..

# 3. Start health services
docker compose up -d

# 4. Access services
open http://localhost:8082  # WebAuthn client
open http://localhost:8001/docs  # Health API
```

**For detailed setup, testing, and workflows**: See [GETTING_STARTED.md](GETTING_STARTED.md)

## 📁 Project Structure

```
health-data-ai-platform/
├── GETTING_STARTED.md              # Setup, testing, workflows
├── ARCHITECTURE.md                 # Technical design reference
├── docker-compose.yml              # Main orchestrator (health services)
├── setup-all-services.sh           # Unified setup script
├── run-tests.sh                    # Unified test runner
│
├── webauthn-stack/                 # Zero-trust authentication stack
│   ├── docker/docker-compose.yml   # WebAuthn stack compose
│   └── tests/                      # E2E Playwright tests
│
├── services/                       # Microservices
│   ├── health-api-service/         # ✅ FastAPI upload service
│   ├── message-queue/              # ✅ RabbitMQ processing
│   ├── data-lake/                  # ✅ MinIO storage
│   ├── etl-narrative-engine/       # 📋 Planned: Clinical processing
│   └── ai-query-interface/         # 📋 Planned: MLflow queries
│
├── docs/                           # Documentation
│   └── architecture/               # Implementation plans
│
└── .github/workflows/              # CI/CD pipelines
```

## 🧪 Running Tests

```bash
# Activate virtual environment
source .venv/bin/activate

# Run all tests (42 total)
./run-tests.sh all

# Run specific service tests
./run-tests.sh health-api     # 27 tests
./run-tests.sh data-lake      # 1 test
./run-tests.sh message-queue  # 14 tests
```

**For detailed testing documentation and troubleshooting**: See [GETTING_STARTED.md](GETTING_STARTED.md#running-tests)

## 📊 Implementation Status

1. ✅ **Message Queue** + **Data Lake** - Foundation services complete
2. ✅ **Health API Service** - User-facing upload interface complete
3. 📋 **ETL Narrative Engine** - Clinical data processing (planned)
4. 📋 **AI Query Interface** - Natural language queries (planned)

## 📖 Documentation

- **[GETTING_STARTED.md](GETTING_STARTED.md)** - Setup, testing, and development workflows
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System design and technical decisions
- **[WEBAUTHN_INTEGRATION.md](WEBAUTHN_INTEGRATION.md)** - JWT verification patterns
- **Service Implementation Plans** - `services/{service}/implementation_plan.md`

## 📄 License

Apache 2.0

## 🆘 Support

- **Issues**: Report issues via GitHub Issues
- **Quick Start**: [GETTING_STARTED.md](GETTING_STARTED.md)
- **Architecture Questions**: [ARCHITECTURE.md](ARCHITECTURE.md)
- **Developer Notes**: `CLAUDE.md`