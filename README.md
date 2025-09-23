# Health Data AI Platform

An end-to-end pipeline that automatically collects health data from Android Health Connect, stores it in a cloud backend, processes it into clinical narratives, and uses this data to fine-tune and query a personal AI model.

## 🏗️ Architecture Overview

This platform consists of 5 main services working together:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Health API     │───▶│  Message Queue  │───▶│   Data Lake     │
│   Service       │    │   (RabbitMQ)    │    │   (MinIO S3)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ AI Query        │◀───│ ETL Narrative   │◀───│ Raw Health Data │
│ Interface       │    │    Engine       │    │   Processing    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+
- Git

### 1. Clone and Setup

```bash
git clone <repository-url>
cd health-data-ai-platform
```

### 2. Start Infrastructure

```bash
# Run the setup script to start all infrastructure services
./scripts/setup.sh

# Or manually start infrastructure
docker-compose up -d
```

### 3. Access Infrastructure Services

Currently, only infrastructure services are running. Application services will be added incrementally.

- **🐰 RabbitMQ Management**: http://localhost:15672 (health_user/health_password)
- **🗄️ MinIO Console**: http://localhost:9001 (admin/password123)
- **📊 MLflow UI**: http://localhost:5000
- **🔄 Redis**: localhost:6379
- **🐘 PostgreSQL**: localhost:5432 (health_user/health_password)

### 4. Test Shared Components

```bash
# Test schemas, types, and validation framework
cd shared && python -m pytest tests/

# Run integration tests (infrastructure connectivity)
./scripts/test-all.sh
```

## 📁 Project Structure

```
health-data-ai-platform/
├── services/                    # Microservices
│   ├── health-api-service/     # FastAPI upload service
│   ├── message-queue/          # RabbitMQ message processing
│   ├── data-lake/             # MinIO data storage
│   ├── etl-narrative-engine/  # Clinical data processing
│   └── ai-query-interface/    # MLflow-powered AI queries
├── shared/                     # Shared components
│   ├── schemas/               # Avro schemas (real Android Health Connect data)
│   ├── types/                 # Python type definitions
│   ├── validation/            # Clinical validation framework
│   ├── common/               # Utilities, logging, config
│   └── contracts/            # API contracts
├── infrastructure/            # Deployment configs
│   ├── docker/               # Docker configurations
│   ├── k8s/                  # Kubernetes manifests
│   └── terraform/            # Infrastructure as code
├── docs/                     # Documentation
│   └── architecture/         # Implementation plans
├── scripts/                  # Automation scripts
└── .github/workflows/        # CI/CD pipelines
```

## 🩺 Health Data Types

The platform processes real Android Health Connect data:

- **Blood Glucose**: CGM readings with meal context and clinical ranges
- **Heart Rate**: Time-series measurements with variability analysis
- **Sleep Sessions**: Detailed sleep stage tracking (Light, Deep, REM)
- **Steps**: Activity tracking with temporal patterns
- **Active Calories**: Energy expenditure calculations
- **Heart Rate Variability**: RMSSD measurements for wellness tracking

## 🛠️ Development

### Current Development Status

**✅ Ready for Use:**
- Infrastructure services (RabbitMQ, MinIO, Redis, PostgreSQL, MLflow)
- Shared components (Avro schemas, Python types, validation framework)
- Development tooling (setup scripts, testing framework)
- Service implementation template

**🔄 To Be Implemented:**
- Application services (Health API, Message Queue, Data Lake, ETL Engine, AI Interface)

### Running Tests

```bash
# Run all available tests (currently shared components and infrastructure)
./scripts/test-all.sh

# Test shared components only
cd shared && python -m pytest tests/

# Run schema validation
cd .github/workflows && # Schema validation runs automatically on CI
```

### Service Development

Use the service template to implement new services:

```bash
# Copy template for new service
cp -r services/_template services/your-service-name
cd services/your-service-name

# Follow the template README.md for implementation guidance
# Check the implementation plan in your copied docs/implementation_plan.md
```

Each service should follow the template structure with:
- Complete technical specifications
- Code examples and patterns
- Testing strategies
- Deployment guidelines

## 📊 Implementation Order

The services should be implemented in this order based on dependencies:

1. **Message Queue** + **Data Lake** (parallel) - Foundation services
2. **Health API Service** - User-facing upload interface
3. **ETL Narrative Engine** - Clinical data processing
4. **AI Query Interface** - Natural language queries

## 🔧 Configuration

Environment variables are managed through `.env` file:

```bash
# Database
DATABASE_URL=postgresql://health_user:health_password@localhost:5432/health_platform

# Message Queue
RABBITMQ_URL=amqp://health_user:health_password@localhost:5672/health_data

# Object Storage
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=admin
MINIO_SECRET_KEY=password123

# See .env for complete configuration
```

## 🧪 Testing Strategy

The platform currently implements testing for available components:

- **✅ Schema Validation**: Avro schema compatibility testing
- **✅ Clinical Validation**: Health data range and pattern testing
- **✅ Integration Tests**: Infrastructure connectivity testing
- **🔄 Unit Tests**: Will be added per service as they're implemented
- **🔄 End-to-End Tests**: Will be added as complete pipeline is built

## 🚢 Deployment

### Development (Infrastructure Only)
```bash
# Deploy infrastructure services
./scripts/deploy.sh --env development

# Or manually
docker-compose up -d
```

### Staging & Production
```bash
# Not yet available - will be added as services are implemented
# ./scripts/deploy.sh --env staging
# ./scripts/deploy.sh --env production
```

**Note**: Currently only development environment (infrastructure) deployment is supported. Staging and production deployments will be enabled as application services are implemented.

## 📈 Monitoring

The platform includes comprehensive monitoring:

- **Prometheus Metrics**: Performance and business metrics
- **Structured Logging**: JSON-formatted logs with correlation IDs
- **Health Checks**: Service dependency monitoring
- **Clinical Alerts**: Automated health data anomaly detection

## 🔒 Security

- **Authentication**: FastAPI-Users with JWT tokens
- **Rate Limiting**: Per-endpoint rate limiting with Redis
- **Data Encryption**: Encryption at rest and in transit
- **HIPAA Considerations**: Health data handling best practices
- **Input Validation**: Comprehensive Avro schema validation

## 🏥 Clinical Intelligence

The platform includes clinical domain expertise:

- **Physiological Range Validation**: Normal ranges for all health metrics
- **Clinical Context**: Meal timing, specimen sources, device types
- **Quality Scoring**: Data completeness and accuracy assessment
- **Alert Generation**: Automated detection of concerning values
- **Narrative Generation**: Human-readable clinical summaries

## 📚 Documentation

- **API Documentation**: OpenAPI/Swagger specifications
- **Schema Documentation**: Avro schema definitions and examples
- **Architecture Documentation**: Complete implementation plans
- **Clinical Documentation**: Health data interpretation guidelines

## 🤝 Contributing

1. **Use the service template**: Copy `services/_template/` for new services
2. **Follow implementation order**: Message Queue → Data Lake → API → ETL → AI
3. **Use Test-Driven Development (TDD)** where possible
4. **Implement clinical validation** for all health data
5. **Add comprehensive logging and metrics** using shared components
6. **Follow established patterns** in implementation plans and shared libraries

## 📄 License

Apache 2.0

## 🆘 Support

- **Issues**: Report issues via GitHub Issues
- **Documentation**: Check `docs/` directory
- **Implementation Plans**: See `services/{service}/implementation_plan.md`
- **Architecture**: Review `docs/architecture/implementation_plan_optimal_hybrid.md`