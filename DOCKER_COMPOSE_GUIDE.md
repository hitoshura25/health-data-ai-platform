# Docker Compose Guide - Health Data AI Platform

## Overview

This project uses a modular Docker Compose architecture with reusable service definitions. Each service is defined in its own compose file and orchestrated by the main `docker-compose.yml`.

## Architecture

```
health-data-ai-platform/
├── docker-compose.yml              # Main orchestrator (uses 'include')
├── .env                            # Environment configuration
├── infrastructure/                  # Shared infrastructure
│   ├── postgres.compose.yml        # PostgreSQL (multi-database support)
│   ├── redis.compose.yml           # Redis cache/sessions
│   ├── jaeger.compose.yml          # Distributed tracing
│   └── webauthn.compose.yml        # WebAuthn auth server (from external repo)
└── services/
    ├── data-lake/
    │   └── deployment/
    │       └── minio.compose.yml   # MinIO object storage
    ├── message-queue/
    │   └── deployment/
    │       └── rabbitmq.compose.yml # RabbitMQ message broker
    └── health-api-service/
        └── health-api.compose.yml  # Health Data API
```

## Services & Ports

| Service | Port(s) | Description |
|---------|---------|-------------|
| **health-api** | 8000 | Health Data Upload & Query API |
| **webauthn-server** | 8080 | WebAuthn/Passkey Authentication |
| **postgres** | 5432 | PostgreSQL Database (multi-DB) |
| **redis** | 6379 | Redis Cache & Sessions |
| **minio** | 9000, 9001 | MinIO S3 API & Console |
| **rabbitmq** | 5672, 15672 | RabbitMQ AMQP & Management UI |
| **jaeger** | 16686, 4317, 4318 | Jaeger UI & OTLP receivers |
| **data-lake-monitoring** | 8002 | MinIO metrics exporter |

## Quick Start

### 1. Setup Environment

```bash
# Run the unified setup script to generate secure .env files
./setup-all-services.sh
```

This generates coordinated `.env` files with random secure credentials for all services.

### 2. Start All Services

```bash
# Start everything
docker compose up -d

# View logs
docker compose logs -f

# View logs for specific service
docker compose logs -f health-api
```

### 3. Verify Services

```bash
# Check service health
docker compose ps

# All services should show "healthy" or "running"
```

### 4. Access Services

- **Health API**: http://localhost:8000/docs (Swagger UI)
- **WebAuthn Server**: http://localhost:8080/health
- **MinIO Console**: http://localhost:9001 (login with MINIO credentials from .env)
- **RabbitMQ Management**: http://localhost:15672 (login with RABBITMQ credentials)
- **Jaeger UI**: http://localhost:16686 (distributed tracing)

## Common Commands

### Service Management

```bash
# Start specific service and its dependencies
docker compose up -d health-api

# Restart a service
docker compose restart health-api

# Stop all services
docker compose down

# Stop and remove volumes (WARNING: deletes all data!)
docker compose down -v

# Rebuild a service after code changes
docker compose up -d --build health-api
```

### Viewing Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f health-api

# Last 100 lines
docker compose logs --tail=100 health-api

# Since specific time
docker compose logs --since 2025-01-01T10:00:00 health-api
```

### Debugging

```bash
# Execute command in running container
docker compose exec health-api bash

# View environment variables
docker compose exec health-api env

# Check service dependencies
docker compose config --services

# Validate compose file
docker compose config
```

## Service Dependencies

The platform has the following dependency tree:

```
health-api
├── postgres (healthapi database)
├── redis (rate limiting)
├── minio (file storage)
└── rabbitmq (async messaging)

webauthn-server
├── postgres (webauthn database)
├── redis (session storage)
└── jaeger (tracing)

data-lake-monitoring
└── minio

data-lake-setup
└── minio

message-queue-setup
└── rabbitmq
```

## Multi-Database PostgreSQL

PostgreSQL is configured to create multiple databases on first startup:

- `healthapi` - Health API Service database
- `webauthn` - WebAuthn Server database

This is controlled by the `POSTGRES_MULTIPLE_DATABASES` environment variable in `.env`.

## Shared Network

All services communicate via a shared Docker network: `health-platform-net`

Services can reach each other using their service names:
- `http://postgres:5432`
- `http://redis:6379`
- `http://minio:9000`
- `http://rabbitmq:5672`
- `http://webauthn-server:8080`

## Scaling Services

```bash
# Scale health-api to 3 instances
docker compose up -d --scale health-api=3

# Note: You'll need a load balancer for this to work properly
```

## Updating Services

### Update WebAuthn Server to New Version

```bash
# Edit .env
WEBAUTHN_VERSION=1.0.26

# Pull new image and restart
docker compose pull webauthn-server
docker compose up -d webauthn-server
```

### Update Health API Code

```bash
# Make code changes...

# Rebuild and restart
docker compose up -d --build health-api
```

## Troubleshooting

### Service Won't Start

```bash
# Check logs
docker compose logs health-api

# Check if dependencies are healthy
docker compose ps

# Restart dependencies first
docker compose restart postgres redis
docker compose up -d health-api
```

### Port Already in Use

```bash
# Find process using port
lsof -i :8000

# Change port in .env
HEALTH_API_PORT=8001

# Restart services
docker compose up -d
```

### Database Connection Issues

```bash
# Verify postgres is healthy
docker compose ps postgres

# Check database exists
docker compose exec postgres psql -U postgres -l

# Manually create database if needed
docker compose exec postgres psql -U postgres -c "CREATE DATABASE healthapi;"
```

### Clean Slate (Reset Everything)

```bash
# Stop all services and remove volumes
docker compose down -v

# Remove any orphaned containers
docker compose down --remove-orphans

# Start fresh
docker compose up -d
```

## Adding New Services

To add a new service (e.g., `etl-narrative-engine`):

1. Create service compose file:
   ```bash
   touch services/etl-narrative-engine/etl.compose.yml
   ```

2. Define service (reference postgres, redis, minio, rabbitmq as needed):
   ```yaml
   services:
     etl-engine:
       build: .
       depends_on:
         - postgres
         - minio
         - rabbitmq
       networks:
         - health-platform-net
   ```

3. Include in main `docker-compose.yml`:
   ```yaml
   include:
     # ... existing includes ...
     - path: services/etl-narrative-engine/etl.compose.yml
   ```

4. Start the new service:
   ```bash
   docker compose up -d etl-engine
   ```

## Best Practices

1. **Never commit .env** - Generated by `setup-all-services.sh` with random credentials
2. **Use health checks** - Ensure services wait for dependencies
3. **Named volumes** - Use named volumes for data persistence
4. **Shared network** - All services use `health-platform-net`
5. **Environment variables** - Parameterize all configuration
6. **Service naming** - Use descriptive, consistent service names

## Production Deployment

For production, consider:

1. **Move to Kubernetes** - Use Helm charts for orchestration
2. **Managed services** - Use RDS, ElastiCache, S3, etc.
3. **Secrets management** - Use Vault, AWS Secrets Manager, etc.
4. **Monitoring** - Add Prometheus, Grafana, ELK stack
5. **Load balancing** - Use nginx or cloud load balancers
6. **TLS/SSL** - Enable HTTPS for all services
7. **Backup strategy** - Regular database and volume backups

## References

- [Docker Compose Include Documentation](https://docs.docker.com/compose/how-tos/multiple-compose-files/include/)
- [Docker Compose Best Practices](https://docs.docker.com/compose/production/)
- [WebAuthn Server Repository](https://github.com/hitoshura25/mpo-api-authn-server)
