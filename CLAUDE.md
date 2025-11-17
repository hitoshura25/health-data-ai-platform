# Health Data AI Platform - Claude Memory

## Current Work (In Progress)

### Completed Infrastructure
- **✅ Data Lake Service (2025-09-26)**: Complete MinIO-based object storage with lifecycle management, intelligent naming, and integration tests
- **✅ Message Queue Service (2025-09-25)**: RabbitMQ-based message processing with containerization
- **✅ Initial CI/CD Pipeline**: GitHub Actions workflows for data-lake and message-queue services
- **✅ WebAuthn Authentication Stack (2025-10-21)**: MCP-generated zero-trust WebAuthn stack with Jaeger tracing, separate from health services

### Planned Development
- **Health API Service** - FastAPI upload service for Android Health Connect data
- **ETL Narrative Engine** - Clinical data processing pipeline
- **AI Query Interface** - MLflow-powered natural language queries

## Project Overview

This is a Python-based microservices platform that processes health data from Android Health Connect into clinical narratives for AI model training and querying.

### Key Technologies
- **Language**: Python 3.11+ with Pydantic for data validation
- **Framework**: FastAPI for API services
- **Authentication**: WebAuthn/Passkeys (zero-trust stack in `webauthn-stack/`)
- **Storage**: MinIO (S3-compatible) for data lake, PostgreSQL for structured data
- **Message Queue**: RabbitMQ for async processing
- **Observability**: Jaeger distributed tracing (provided by webauthn-stack)
- **AI/ML**: MLflow for model management, transformers for NLP
- **Testing**: pytest with asyncio support, Docker for integration tests
- **Containerization**: Docker with docker-compose for local development
- **CI/CD**: GitHub Actions with per-service workflows

### Architecture Overview
```
┌──────────────────────────────────────────────────────────┐
│  WebAuthn Stack (webauthn-stack/)                        │
│  - Envoy Gateway (port 8000)                             │
│  - WebAuthn Server (FIDO2 + JWT)                         │
│  - PostgreSQL (port 5433) - credentials only             │
│  - Redis (port 6380) - sessions only                     │
│  - Jaeger (port 16687) - distributed tracing             │
└────────────────────┬─────────────────────────────────────┘
                     │ (JWT verification)
                     ▼
┌──────────────────────────────────────────────────────────┐
│  Health Services Stack (main docker-compose.yml)         │
│                                                           │
│  Health API ──→ Message Queue ──→ Data Lake              │
│      │              │               │                     │
│      ▼              ▼               ▼                     │
│  AI Query ◀─── ETL Narrative ◀─── Raw Processing         │
│  Interface      Engine            Service                │
│                                                           │
│  Infrastructure:                                          │
│  - PostgreSQL (port 5432) - health data                  │
│  - Redis (port 6379) - rate limiting                     │
│  - MinIO (port 9000/9001) - data lake                    │
│  - RabbitMQ (port 5672/15672) - message queue            │
└──────────────────────────────────────────────────────────┘
```

## Development Commands

### **CRITICAL: Virtual Environment Activation**
**ALWAYS activate the Python virtual environment before running any Python commands:**
```bash
source .venv/bin/activate
```

### Project-Level Commands
- **All Tests**: `pytest` (runs all service tests)
- **Specific Service Tests**: `pytest services/{service-name}/tests/`
- **Integration Tests**: Requires Docker services running first
- **Linting**: `black .` and `ruff check .` (when available)

### Service-Specific Commands

#### Data Lake Service
- **Tests**: `source .venv/bin/activate && pytest services/data-lake/tests/`
- **Integration Setup**: `docker-compose up -d minio` → set env vars → activate venv → run tests
- **Environment**: Uses MinIO with DATALAKE_MINIO_* environment variables

#### Message Queue Service
- **Tests**: `source .venv/bin/activate && pytest services/message-queue/tests/`
- **Run Service**: `docker-compose up -d rabbitmq`

### Docker Development

#### Starting the Complete Platform
```bash
# 1. Start WebAuthn stack (authentication + Jaeger tracing)
cd webauthn-stack/docker && docker compose up -d && cd ../..

# 2. Start health services
docker compose up -d

# 3. Verify all services are running
docker ps
```

#### Individual Service Management
- **Health Services**: `docker compose up -d {service-name}`
- **WebAuthn Stack**: `cd webauthn-stack/docker && docker compose up -d`
- **Logs**: `docker compose logs -f {service-name}`

#### Port Reference
**WebAuthn Stack:**
- Gateway (Envoy): `http://localhost:8000`
- Jaeger UI: `http://localhost:16687`
- PostgreSQL: `localhost:5433`
- Redis: `localhost:6380`

**Health Services:**
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`
- MinIO API: `localhost:9000`
- MinIO Console: `localhost:9001`
- RabbitMQ: `localhost:5672` (AMQP), `localhost:15672` (Management UI)

## 🚨 TOP 5 CRITICAL PATTERNS (Essential for Immediate Productivity)

### 1. 🚨 CRITICAL: NEVER Make Assumptions - Always Validate Dependencies

**THE FUNDAMENTAL RULE**: This is a Python-based project with specific dependencies. ALWAYS check requirements.txt files and existing imports before adding new libraries.

**Quick Validation Template:**
```bash
# Check existing dependencies first
cat services/{service}/requirements.txt
grep -r "import" services/{service}/src/
# Verify library is already available before using
```

### 2. 🐳 CRITICAL: Docker Integration Test Pattern

**MANDATORY pattern for services requiring external dependencies (MinIO, RabbitMQ, PostgreSQL).**

**Essential Pattern:**
```python
# Integration test setup pattern
@pytest.fixture(scope="session")
def setup_integration_environment():
    # Verify Docker service is running
    # Set environment variables
    # Initialize service connections
    # Cleanup after tests
```

**Environment Variables Pattern:**
```bash
export DATALAKE_MINIO_ENDPOINT=localhost:9000
export DATALAKE_MINIO_ACCESS_KEY=minioadmin
export DATALAKE_MINIO_SECRET_KEY=minioadmin
```

### 3. 🔧 CRITICAL: Service-Specific Testing Strategy

**Each service has its own testing requirements and Docker dependencies.**

```python
# Data Lake: Requires MinIO
docker-compose up -d minio
pytest services/data-lake/tests/

# Message Queue: Requires RabbitMQ
docker-compose up -d rabbitmq
pytest services/message-queue/tests/

# Health API: Will require PostgreSQL + external APIs
# ETL Engine: Requires data lake + AI model dependencies
# AI Query: Requires MLflow + model storage
```

### 4. 📤 CRITICAL: Pydantic Data Validation Pattern

**MANDATORY use of Pydantic for all data models and configuration management.**

```python
# Settings pattern used across services
from pydantic_settings import BaseSettings

class ServiceSettings(BaseSettings):
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str

    class Config:
        env_prefix = "DATALAKE_"
```

### 5. 🧬 CRITICAL: Microservice Development Pattern

**Each service is independently deployable with its own requirements, tests, and Docker configuration.**

**Service Structure Pattern:**
```
services/{service-name}/
├── src/                 # Source code
├── tests/              # Service-specific tests
├── requirements.txt    # Service dependencies
├── Dockerfile         # Service containerization
├── implementation_plan.md  # Service documentation
└── deployment/        # Service deployment configs
```

## Critical Development Reminders

### 🔐 CRITICAL: WebAuthn Stack Integration

**The platform uses a separate WebAuthn stack for authentication and observability.**

#### Architecture Decision
- **Separate Stacks**: WebAuthn stack (`webauthn-stack/`) is isolated from health services
- **Shared Jaeger**: Single Jaeger instance (in webauthn-stack) for unified distributed tracing
- **Separate Databases**: WebAuthn PostgreSQL (port 5433) vs Health PostgreSQL (port 5432)
- **Separate Redis**: WebAuthn Redis (port 6380) vs Health Redis (port 6379)

#### Integration Pattern
```bash
# Always start WebAuthn stack first
cd webauthn-stack/docker && docker compose up -d && cd ../..

# Then start health services
docker compose up -d
```

#### Adding Jaeger Tracing to Health Services
When implementing distributed tracing in health services:

```python
# Use the shared Jaeger from webauthn-stack
JAEGER_OTLP_ENDPOINT = "http://localhost:4319"  # gRPC
# or
JAEGER_OTLP_ENDPOINT = "http://localhost:4320"  # HTTP
```

#### JWT Verification (Future)
Health API will verify WebAuthn JWTs:
- WebAuthn issues JWTs via gateway at `http://localhost:8000`
- Health API verifies using public key from `http://localhost:8000/public-key`
- See `webauthn-stack/docs/INTEGRATION.md` for detailed integration guide

### 🚨 CRITICAL: Git Commit Policy - User Approval Required

**🛑 MANDATORY: User Must Approve All Git Operations**

- **✅ ASK FIRST**: When work is complete, ask user if you should commit and push
- **✅ IF APPROVED**: Run `git add`, `git commit`, and `git push` commands with clear commit messages
- **❌ NEVER auto-commit**: Without explicit user approval in the current conversation
- **✅ ALWAYS prepare**: Clear commit messages summarizing the changes

**Workflow:**
1. Complete implementation and verify tests pass
2. Ask user: "Should I commit and push these changes to [branch-name]?"
3. If user approves → run git commands
4. If user declines → inform them of manual commands

### 🚨 CRITICAL: Environment-Specific Configuration

**ALWAYS use environment variables for service configuration, never hardcode credentials or endpoints.**

```python
# Correct pattern for service configuration
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    api_key: str
    debug: bool = False

    class Config:
        env_file = ".env"
```

### 🚨 CRITICAL: Docker Development Workflow

**Services depend on external systems (MinIO, RabbitMQ, PostgreSQL). Always start dependencies before testing.**

```bash
# Standard workflow for integration testing
1. docker-compose up -d {required-services}
2. export {SERVICE}_* environment variables
3. source .venv/bin/activate
4. pytest services/{service}/tests/
5. docker-compose down
```

### 🧹 CRITICAL: Python Dependency Management

**Each service manages its own dependencies. When adding libraries:**

1. **Check existing requirements.txt** for compatible versions
2. **Add to service-specific requirements.txt** not root level
3. **Test in isolated service environment** before integrating
4. **Update CI workflows** if new dependencies affect testing

## Port Assignments

**WebAuthn Stack:**
- **Envoy Gateway**: 8000 (Zero-trust entry point)
- **Jaeger UI**: 16687 (Distributed tracing)
- **PostgreSQL**: 5433 (Credentials only)
- **Redis**: 6380 (Sessions only)

**Health Services:**
- **Health API Service**: 8001 (FastAPI)
- **PostgreSQL**: 5432 (Health data)
- **Redis**: 6379 (Rate limiting)
- **Data Lake (MinIO)**: 9000 (API), 9001 (Console)
- **Message Queue (RabbitMQ)**: 5672 (AMQP), 15672 (Management)
- **ETL Narrative Engine**: 8002 (planned)
- **AI Query Interface**: 8003 (planned)

## Testing Architecture

- **Integration Tests**: Use Docker containers for external dependencies
- **Unit Tests**: Mock external services, test business logic
- **Service Isolation**: Each service has independent test suite
- **CI/CD**: GitHub Actions workflows per service for parallel testing
- **Test Configuration**: pytest.ini for global test settings

## Implementation Order

Services should be implemented in this dependency order:

1. **✅ Message Queue + Data Lake** (foundation services - COMPLETED)
2. **Health API Service** (user-facing upload interface)
3. **ETL Narrative Engine** (clinical data processing)
4. **AI Query Interface** (natural language queries)

## Service-Specific Notes

### Data Lake Service
- **Storage**: MinIO S3-compatible object storage
- **Features**: Intelligent object naming, lifecycle management, data quality validation
- **Testing**: Requires MinIO container and environment variables

### Message Queue Service
- **Technology**: RabbitMQ with async message processing
- **Pattern**: Publisher/subscriber for service communication
- **Testing**: Requires RabbitMQ container

### Health API Service (Planned)
- **Framework**: FastAPI for REST API
- **Integration**: Android Health Connect data ingestion
- **Dependencies**: PostgreSQL for metadata, MinIO for raw data

### ETL Narrative Engine (Planned)
- **Purpose**: Transform health data into clinical narratives
- **AI Integration**: Prepare data for model fine-tuning
- **Dependencies**: Data Lake access, NLP libraries

### AI Query Interface (Planned)
- **Framework**: MLflow for model management
- **Features**: Natural language health data queries
- **Dependencies**: Trained models, vector storage for embeddings

## Important Notes

- **Service Independence**: Each service can be developed and deployed independently
- **Docker First**: All services designed for containerized deployment
- **Environment Configuration**: Use pydantic-settings for type-safe configuration
- **Testing Strategy**: Integration tests require Docker, unit tests should be fast and isolated
- **🚨 NEVER commit changes automatically** - Always let user review and commit changes themselves

---

## Implementation Plans

Each service has detailed implementation documentation:
- **Data Lake**: `services/data-lake/implementation_plan.md`
- **Message Queue**: `services/message-queue/implementation_plan.md`
- **Health API**: `services/health-api-service/implementation_plan.md`
- **ETL Engine**: `services/etl-narrative-engine/implementation_plan.md`
- **AI Query**: `services/ai-query-interface/implementation_plan.md`
- **Architecture Overview**: `docs/architecture/implementation_plan_optimal_hybrid.md`