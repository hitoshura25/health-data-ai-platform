# Health Data AI Platform - Claude Memory

## Current Work (In Progress)

### Completed Infrastructure
- **✅ Data Lake Service (2025-09-26)**: Complete MinIO-based object storage with lifecycle management, intelligent naming, and integration tests
- **✅ Message Queue Service (2025-09-25)**: RabbitMQ-based message processing with containerization
- **✅ Initial CI/CD Pipeline**: GitHub Actions workflows for data-lake and message-queue services

### Planned Development
- **Health API Service** - FastAPI upload service for Android Health Connect data
- **ETL Narrative Engine** - Clinical data processing pipeline
- **AI Query Interface** - MLflow-powered natural language queries

## Project Overview

This is a Python-based microservices platform that processes health data from Android Health Connect into clinical narratives for AI model training and querying.

### Key Technologies
- **Language**: Python 3.11+ with Pydantic for data validation
- **Framework**: FastAPI for API services
- **Storage**: MinIO (S3-compatible) for data lake, PostgreSQL for structured data
- **Message Queue**: RabbitMQ for async processing
- **AI/ML**: MLflow for model management, transformers for NLP
- **Testing**: pytest with asyncio support, Docker for integration tests
- **Containerization**: Docker with docker-compose for local development
- **CI/CD**: GitHub Actions with per-service workflows

### Architecture Overview
```
Health API ──→ Message Queue ──→ Data Lake
    │              │               │
    ▼              ▼               ▼
AI Query ◀─── ETL Narrative ◀─── Raw Processing
Interface      Engine            Service
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
- **All Services**: `docker-compose up -d`
- **Individual Service**: `docker-compose up -d {service-name}`
- **Logs**: `docker-compose logs -f {service-name}`

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

### 🚨 CRITICAL: Git Commit Policy - NEVER Auto-Commit

**🛑 MANDATORY: User Must Review and Commit All Changes**

- **❌ NEVER run**: `git add`, `git commit`, `git push` commands
- **✅ ALWAYS prepare**: Changes and inform user they are ready for review

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

- **Health API Service**: 8000 (FastAPI default)
- **Data Lake (MinIO)**: 9000 (API), 9001 (Console)
- **Message Queue (RabbitMQ)**: 5672 (AMQP), 15672 (Management)
- **ETL Narrative Engine**: 8001
- **AI Query Interface**: 8002
- **PostgreSQL**: 5432 (when added)

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