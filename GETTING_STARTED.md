# Getting Started - Health Data AI Platform

A complete guide to setting up, running, and testing the Health Data AI Platform.

## Prerequisites

- **Docker** and Docker Compose v2.20+ (for `include` directive support)
- **Python** 3.11+
- **OpenSSL** (for generating secure credentials)
- **Git**
- **Bash** shell

## Quick Start (Under 2 Minutes!)

### Step 1: Clone and Setup (30 seconds)

```bash
# Clone the repository
git clone <repository-url>
cd health-data-ai-platform

# Generate secure configuration for all services
./setup-all-services.sh
```

**What this does:**
- ✅ Generates secure random credentials for all services
- ✅ Creates coordinated `.env` files across all services
- ✅ Configures PostgreSQL with multiple databases (healthapi, webauthn)
- ✅ Sets up MinIO, RabbitMQ, Redis with matching credentials

### Step 2: Start the Platform (60 seconds)

```bash
# 1. Start WebAuthn stack (authentication + Jaeger tracing)
cd webauthn-stack/docker && docker compose up -d && cd ../..

# 2. Start health services
docker compose up -d

# 3. Verify all services are running
docker ps
```

**Services starting:**
- 🔐 WebAuthn Server (passkey authentication)
- 📊 Jaeger (distributed tracing)
- 🏥 Health API (main application)
- 🔐 PostgreSQL (databases: healthapi, webauthn)
- 💾 Redis (cache, sessions, rate limiting)
- 🗄️ MinIO (S3-compatible storage)
- 📨 RabbitMQ (message queue)

### Step 3: Access Services

| Service | URL | Credentials |
|---------|-----|-------------|
| **Health API** | http://localhost:8001/docs | Bearer token (via WebAuthn) |
| **WebAuthn Client** | http://localhost:8082 | Register with passkey |
| **Envoy Gateway** | http://localhost:8000 | Zero-trust entry point |
| **MinIO Console** | http://localhost:9001 | From `.env`: `DATALAKE_MINIO_*` |
| **RabbitMQ Management** | http://localhost:15672 | From `.env`: `MQ_RABBITMQ_*` |
| **Jaeger UI** | http://localhost:16687 | No auth (tracing dashboard) |

## Port Reference

### WebAuthn Stack
- **Envoy Gateway**: 8000 (Zero-trust entry point)
- **Jaeger UI**: 16687 (Distributed tracing)
- **Jaeger OTLP gRPC**: 4319 (Trace ingestion)
- **Jaeger OTLP HTTP**: 4320 (Trace ingestion)
- **PostgreSQL**: 5433 (Credentials only)
- **Redis**: 6380 (Sessions only)
- **WebAuthn Client**: 8082 (Test UI)

### Health Services
- **Health API**: 8001 (FastAPI REST API)
- **PostgreSQL**: 5432 (Health data)
- **Redis**: 6379 (Rate limiting)
- **MinIO API**: 9000 (S3-compatible storage)
- **MinIO Console**: 9001 (Admin UI)
- **RabbitMQ AMQP**: 5672 (Message broker)
- **RabbitMQ Management**: 15672 (Admin UI)

## Running Tests

### Prerequisites

1. **Activate virtual environment** (uses single root-level `.venv`):
   ```bash
   source .venv/bin/activate
   ```

2. **Ensure Docker services are running**:
   ```bash
   docker compose ps  # Should show all services healthy/running
   ```

### Run All Tests

```bash
./run-tests.sh all
```

**Total: 42 tests across 3 services**

### Run Service-Specific Tests

```bash
# Health API (27 tests)
./run-tests.sh health-api

# Data Lake (1 test)
./run-tests.sh data-lake

# Message Queue (14 tests)
./run-tests.sh message-queue
```

### Run Tests with Options

```bash
# Verbose output
./run-tests.sh health-api -v

# Run specific test
./run-tests.sh health-api -k upload

# Show detailed traceback
./run-tests.sh health-api -v --tb=short

# Run with coverage
./run-tests.sh health-api --cov
```

### Run Tests from Service Directory

```bash
cd services/health-api-service
source ../../.venv/bin/activate
pytest tests/
```

### Test Coverage Summary

- **Health API**: 27 integration tests
  - Authentication (register, login, logout)
  - File uploads (validation, rate limiting)
  - Health checks
  - Upload history and status

- **Data Lake**: 1 integration test
  - Upload/download to MinIO

- **Message Queue**: 14 tests (13 unit + 1 integration)
  - Message serialization
  - Deduplication logic
  - RabbitMQ integration

## Common Development Workflows

### View Service Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f health-api
docker compose logs -f postgres
docker compose logs -f minio

# WebAuthn stack logs
cd webauthn-stack/docker && docker compose logs -f
```

### Restart Services

```bash
# Restart all health services
docker compose restart

# Restart specific service
docker compose restart health-api

# Restart WebAuthn stack
cd webauthn-stack/docker && docker compose restart
```

### Rebuild After Code Changes

```bash
# Rebuild and restart specific service
docker compose up -d --build health-api

# Rebuild everything
docker compose up -d --build
```

### Stop Services

```bash
# Stop health services (keep data)
docker compose down

# Stop and remove all data
docker compose down -v

# Stop WebAuthn stack
cd webauthn-stack/docker && docker compose down
```

## Development Workflow

### 1. Make Code Changes

Edit files in the service directory (e.g., `services/health-api-service/`)

### 2. Rebuild and Test Locally

```bash
# Rebuild service
docker compose up -d --build health-api

# Watch logs
docker compose logs -f health-api

# Run tests
source .venv/bin/activate
./run-tests.sh health-api
```

### 3. Run E2E Tests

```bash
# Ensure all stacks are running
cd webauthn-stack && docker compose -f docker/docker-compose.yml up -d && cd ..
docker compose up -d

# Run E2E tests
cd webauthn-stack
npx playwright test
```

## Troubleshooting

### Services Won't Start

```bash
# Check for port conflicts
lsof -i :8001  # Health API
lsof -i :8000  # Envoy Gateway
lsof -i :5432  # PostgreSQL

# View detailed logs
docker compose logs postgres
docker compose logs redis
docker compose logs health-api
```

### Database Connection Issues

```bash
# Verify PostgreSQL is healthy
docker compose exec postgres psql -U postgres -l

# Should see: healthapi, webauthn databases

# Check database connections
docker compose exec postgres psql -U postgres -d healthapi -c "SELECT version();"
```

### MinIO Bucket Not Found

```bash
# Check if bucket exists
docker exec health-minio mc ls myminio/

# Create bucket if missing
docker exec health-minio mc alias set myminio http://localhost:9000 <ACCESS_KEY> <SECRET_KEY>
docker exec health-minio mc mb myminio/health-data --ignore-existing
```

### WebAuthn Stack Issues

```bash
# Check WebAuthn stack status
cd webauthn-stack/docker && docker compose ps

# View logs
docker compose logs -f webauthn-server
docker compose logs -f envoy-gateway
docker compose logs -f jaeger
```

### Re-generate Configuration

```bash
# Stop all services
docker compose down -v
cd webauthn-stack/docker && docker compose down -v && cd ../..

# Remove old .env files
rm -f .env infrastructure/.env services/*/.env

# Re-run setup
./setup-all-services.sh

# Start fresh
cd webauthn-stack/docker && docker compose up -d && cd ../..
docker compose up -d
```

### Test Failures

```bash
# Ensure Docker services are running
docker compose ps

# Check Docker service health
docker compose exec postgres psql -U postgres -c "SELECT 1;"
docker compose exec redis redis-cli ping
docker compose exec minio mc admin info myminio/

# Clear test artifacts
rm -rf test-results/ .pytest_cache/

# Re-run tests
source .venv/bin/activate
./run-tests.sh health-api -v
```

## Next Steps

### Using WebAuthn Authentication

1. **Register a user**:
   - Open http://localhost:8082
   - Enter username and display name
   - Click "Register Passkey"
   - Follow browser prompt to create passkey

2. **Authenticate**:
   - Enter username
   - Click "Authenticate with Passkey"
   - Follow browser prompt

3. **Get JWT token**:
   - Token is stored in sessionStorage
   - Extract and use in API requests

4. **Make API requests**:
   ```bash
   # Exchange WebAuthn token for Health API token
   curl -X POST http://localhost:8001/auth/webauthn/exchange \
     -H "Content-Type: application/json" \
     -d '{"webauthn_token": "<YOUR_JWT>"}'

   # Use Health API token for uploads
   curl -X POST http://localhost:8001/v1/upload \
     -H "Authorization: Bearer <HEALTH_API_TOKEN>" \
     -F "file=@sample.avro"
   ```

### Adding a New Service

1. **Create service directory**:
   ```bash
   mkdir -p services/new-service
   ```

2. **Create compose file**:
   ```bash
   touch services/new-service/new-service.compose.yml
   ```

3. **Add to main docker-compose.yml**:
   ```yaml
   include:
     # ... existing includes ...
     - path: services/new-service/new-service.compose.yml
   ```

4. **Update setup script** to generate service `.env`

5. **Start service**:
   ```bash
   ./setup-all-services.sh
   docker compose up -d new-service
   ```

## Project Structure

```
health-data-ai-platform/
├── docker-compose.yml              # Main orchestrator (health services)
├── setup-all-services.sh           # Unified setup script
├── run-tests.sh                    # Unified test runner
├── .venv/                          # Shared virtual environment
│
├── webauthn-stack/                 # Zero-trust authentication stack
│   ├── docker/docker-compose.yml   # WebAuthn stack compose
│   ├── tests/                      # E2E Playwright tests
│   └── docs/                       # WebAuthn integration docs
│
├── services/                       # Microservices
│   ├── health-api-service/         # ✅ Complete
│   ├── message-queue/              # ✅ Complete
│   ├── data-lake/                  # ✅ Complete
│   ├── etl-narrative-engine/       # Planned
│   └── ai-query-interface/         # Planned
│
└── docs/                           # Documentation
    └── architecture/               # Design documents
```

## Additional Resources

- **Architecture Guide**: `ARCHITECTURE.md` - System design and technical decisions
- **WebAuthn Integration**: `webauthn-stack/docs/INTEGRATION.md` - JWT verification patterns
- **Service Implementation Plans**: Each service has `implementation_plan.md`
- **CLAUDE.md**: Development notes and critical patterns

## Security Notes

🔒 **Important Security Considerations:**

- Never commit `.env` files to git (automatically ignored)
- Setup script generates random credentials every time
- Use proper secrets management in production (Vault, AWS Secrets Manager)
- Change WebAuthn RP_ID and ORIGIN for your domain
- Use HTTPS in production (enforce with Envoy)
- Tokens expire in 15 minutes by default

## Support

- **Issues**: Open an issue in the GitHub repository
- **Documentation**: Check `docs/` directory and `ARCHITECTURE.md`
- **Service Help**: See each service's README and implementation_plan.md
