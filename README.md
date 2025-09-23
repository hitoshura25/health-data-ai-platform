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
├── infrastructure/            # Deployment configs
│   ├── docker/               # Docker configurations
│   ├── k8s/                  # Kubernetes manifests
│   └── terraform/            # Infrastructure as code
├── docs/                     # Documentation
│   └── architecture/         # Implementation plans
├── scripts/                  # Automation scripts
└── .github/workflows/        # CI/CD pipelines
```

## 📊 Implementation Order

The services should be implemented in this order based on dependencies:

1. **Message Queue** + **Data Lake** (parallel) - Foundation services
2. **Health API Service** - User-facing upload interface
3. **ETL Narrative Engine** - Clinical data processing
4. **AI Query Interface** - Natural language queries

## 📄 License

Apache 2.0

## 🆘 Support

- **Issues**: Report issues via GitHub Issues
- **Documentation**: Check `docs/` directory
- **Implementation Plans**: See `services/{service}/implementation_plan.md`
- **Architecture**: Review `docs/architecture/implementation_plan_optimal_hybrid.md`