# Architecture - Health Data AI Platform

Technical reference for system design, zero-trust architecture, and service integration patterns.

## System Overview

The Health Data AI Platform is a microservices architecture for processing health data from Android Health Connect into clinical narratives for AI model training and querying.

### High-Level Architecture

```
┌────────────────────────────────────────────────────────────┐
│  WebAuthn Stack (webauthn-stack/)                          │
│  - Envoy Gateway (port 8000) - Zero-trust entry point      │
│  - WebAuthn Server (FIDO2 + JWT)                           │
│  - PostgreSQL (port 5433) - Credentials only               │
│  - Redis (port 6380) - Sessions only                       │
│  - Jaeger (port 16687) - Distributed tracing               │
└────────────────────┬───────────────────────────────────────┘
                     │ (JWT verification)
                     ▼
┌────────────────────────────────────────────────────────────┐
│  Health Services Stack (main docker-compose.yml)           │
│                                                             │
│  Health API ──→ Message Queue ──→ Data Lake                │
│      │              │               │                       │
│      ▼              ▼               ▼                       │
│  AI Query ◀─── ETL Narrative ◀─── Raw Processing           │
│  Interface      Engine            Service                  │
│                                                             │
│  Infrastructure:                                            │
│  - PostgreSQL (port 5432) - Health data                    │
│  - Redis (port 6379) - Rate limiting                       │
│  - MinIO (port 9000/9001) - Data lake                      │
│  - RabbitMQ (port 5672/15672) - Message queue              │
└────────────────────────────────────────────────────────────┘
```

## Design Rationale

### Why Separate Stacks?

#### ✅ Security Isolation
- **Credentials isolated**: WebAuthn database only contains authentication data
- **Blast radius limited**: Compromise of health data doesn't expose credentials
- **Principle of least privilege**: Health services cannot access credential store

#### ✅ Independent Scaling
- Scale authentication independently from data processing
- Different resource requirements (auth is lightweight, data processing is heavy)
- Can replace WebAuthn with different auth provider without touching health services

#### ✅ Technology Independence
- WebAuthn stack uses Java (hitoshura25/webauthn-server)
- Health services use Python (FastAPI)
- Each optimized for its domain

### Why Shared Jaeger?

#### ✅ Distributed Tracing Requires Cross-Service Visibility

```
User Request Flow:
1. Client → WebAuthn (authenticate)       [Span 1]
2. Client → Health API (upload)           [Span 2]
   ├─ Health API → Data Lake (store)      [Span 3]
   └─ Health API → Message Queue (async)  [Span 4]

All spans must be in ONE Jaeger instance to correlate!
```

#### ✅ Single Observability Dashboard
- One UI to monitor entire platform: `http://localhost:16687`
- See authentication latency impacting API performance
- Root cause analysis across service boundaries

#### ✅ Production Best Practice
In production, you typically have:
- **One centralized observability stack** (Jaeger, Prometheus, Grafana)
- **Multiple application stacks** (all send traces to shared Jaeger)

This mirrors that architecture in development.

## Docker Compose Architecture

### Modular Compose Files

The platform uses a modular Docker Compose architecture with reusable service definitions:

```
health-data-ai-platform/
├── docker-compose.yml              # Main orchestrator (includes)
├── webauthn-stack/
│   └── docker/docker-compose.yml   # WebAuthn stack
└── services/
    ├── health-api-service/
    │   └── health-api.compose.yml
    ├── data-lake/deployment/
    │   └── minio.compose.yml
    └── message-queue/deployment/
        └── rabbitmq.compose.yml
```

**Benefits:**
- No duplication - Each service defined once
- Include directive - Main compose file includes service-specific files
- Independent development - Services can be developed and tested independently
- Shared network - All services communicate via `health-platform-net`

### Service Dependencies

```
health-api
├── postgres (healthapi database)
├── redis (rate limiting)
├── minio (file storage)
└── rabbitmq (async messaging)

webauthn-server (in webauthn-stack/)
├── postgres (webauthn database - port 5433)
├── redis (session storage - port 6380)
└── jaeger (tracing - port 16687)
```

### Multi-Database PostgreSQL

PostgreSQL is configured to create multiple databases on first startup:
- `healthapi` - Health API Service database (port 5432)
- `webauthn` - WebAuthn Server database (port 5433)

Controlled by the `POSTGRES_MULTIPLE_DATABASES` environment variable in `.env`.

## Zero-Trust Authentication

### Architecture Components

1. **Envoy Gateway** - Entry point for all traffic
   - Validates JWT signatures using WebAuthn server's public key
   - Routes public endpoints (registration, authentication) without JWT
   - Requires JWT for all `/api/*` protected endpoints

2. **WebAuthn Server** - FIDO2 authentication + JWT issuer
   - Issues RS256-signed JWT tokens on successful authentication
   - Exports public key at `/.well-known/jwks.json` endpoint
   - 15-minute token expiration for security

3. **Health API** - Validates JWTs via JWKS
   - Verifies JWT tokens using public key from WebAuthn server
   - Token exchange pattern for service-specific permissions
   - No direct access to WebAuthn credential store

### Token Exchange Pattern (Production Best Practice)

Instead of passing WebAuthn JWTs everywhere, Health API exchanges them for service-specific tokens:

```python
@app.post("/auth/webauthn/exchange")
async def exchange_webauthn_token(request: TokenExchangeRequest):
    """
    Exchange WebAuthn JWT for Health API JWT

    Flow:
    1. Verify WebAuthn JWT using JWKS
    2. Extract user identity (sub = username from WebAuthn)
    3. Get or create user in health database
    4. Issue Health API JWT with service-specific permissions
    """

    # Verify WebAuthn JWT
    signing_key = jwks_client.get_signing_key_from_jwt(request.webauthn_token)
    payload = jwt.decode(
        request.webauthn_token,
        signing_key.key,
        algorithms=["RS256"],
        issuer="webauthn-server",
        audience="webauthn-clients"
    )

    webauthn_username = payload["sub"]

    # Map to health user (auto-create if needed)
    user = await get_or_create_health_user(db, webauthn_username)

    # Issue Health API token
    health_token = await auth_backend.get_strategy().write_token(user)

    return {"access_token": health_token, "user": UserRead.from_orm(user)}
```

**Benefits:**
- ✅ Service-specific permissions
- ✅ Independent token lifecycles
- ✅ Audit trail per service
- ✅ Can revoke health access without affecting auth

### Security Benefits

- **No session state** (stateless authentication)
- **Short-lived tokens** (15 minutes)
- **Public key cryptography** (RS256)
- **Gateway-level JWT validation**
- **Zero-trust principle** (verify every request)

## Service Integration Patterns

### Adding Distributed Tracing to Health Services

When implementing OpenTelemetry in Python services:

```python
# Example: services/health-api-service/app/tracing.py
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

def setup_tracing(settings):
    """Configure OpenTelemetry to send traces to shared Jaeger"""

    # Use WebAuthn stack's Jaeger
    otlp_exporter = OTLPSpanExporter(
        endpoint="http://host.docker.internal:4319",  # gRPC
        insecure=True  # For local development
    )

    trace.set_tracer_provider(TracerProvider())
    trace.get_tracer_provider().add_span_processor(
        BatchSpanProcessor(otlp_exporter)
    )

    return trace.get_tracer("health-api")
```

**Docker Compose Configuration:**

```yaml
# services/health-api-service/health-api.compose.yml
services:
  health-api:
    environment:
      # Jaeger tracing (uses webauthn-stack Jaeger)
      - HEALTH_API_JAEGER_OTLP_ENDPOINT=http://host.docker.internal:4319
      - HEALTH_API_JAEGER_SERVICE_NAME=health-api
```

**Note**: Use `host.docker.internal` to access the WebAuthn stack's Jaeger from the health services network.

### JWT Verification Pattern

```python
# services/health-api-service/app/auth/webauthn_config.py
from jwt import PyJWKClient

class WebAuthnConfig:
    """Configuration for WebAuthn JWT verification"""

    def __init__(self):
        self.jwks_url = "http://host.docker.internal:8000/.well-known/jwks.json"
        self.issuer = "webauthn-server"
        self.audience = "webauthn-clients"
        self.jwks_client = PyJWKClient(self.jwks_url)

    def get_signing_key_from_jwt(self, token: str):
        """Get signing key from JWKS endpoint"""
        return self.jwks_client.get_signing_key_from_jwt(token)
```

## Network Architecture

### Current Setup (Separate Networks)

```
┌─────────────────────────────────────┐
│  webauthn-stack (default network)   │
│  - envoy-gateway                    │
│  - webauthn-server                  │
│  - postgres (5433)                  │
│  - redis (6380)                     │
│  - jaeger (16687)                   │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  health-platform-net                │
│  - health-api                       │
│  - postgres (5432)                  │
│  - redis (6379)                     │
│  - minio                            │
│  - rabbitmq                         │
└─────────────────────────────────────┘
```

**Communication**: Services communicate via `host.docker.internal` (localhost on host machine).

**Advantages**:
- ✅ Complete isolation between stacks
- ✅ Can manage stacks independently
- ✅ No shared network means no accidental coupling

**Disadvantages**:
- ⚠️ Slightly higher latency (goes through host network)
- ⚠️ Requires `host.docker.internal` support (works on Docker Desktop, may need config on Linux)

### Shared Network Communication

Services within the same network can access each other using service names:
- `http://postgres:5432`
- `http://redis:6379`
- `http://minio:9000`
- `http://rabbitmq:5672`

## Port Assignments

### WebAuthn Stack
| Service | Internal Port | Host Port | Purpose |
|---------|--------------|-----------|---------|
| Envoy Gateway | 8000 | 8000 | Zero-trust entry point |
| Envoy Admin | 9901 | 9901 | Gateway admin UI |
| WebAuthn Server | 8080 | - | Internal only |
| PostgreSQL | 5432 | 5433 | Credentials DB |
| Redis | 6379 | 6380 | Sessions |
| Jaeger UI | 16686 | 16687 | Tracing UI |
| Jaeger OTLP gRPC | 4317 | 4319 | Trace ingestion |
| Jaeger OTLP HTTP | 4318 | 4320 | Trace ingestion |

### Health Services
| Service | Internal Port | Host Port | Purpose |
|---------|--------------|-----------|---------|
| Health API | 8000 | 8001 | REST API |
| PostgreSQL | 5432 | 5432 | Health data DB |
| Redis | 6379 | 6379 | Rate limiting |
| MinIO API | 9000 | 9000 | S3-compatible API |
| MinIO Console | 9001 | 9001 | Web UI |
| RabbitMQ AMQP | 5672 | 5672 | Message queue |
| RabbitMQ Management | 15672 | 15672 | Management UI |

**Note**: Custom ports for WebAuthn stack prevent conflicts with health services.

## Rate Limiting Architecture

### Implementation: fastapi-limiter

The platform uses **fastapi-limiter** for async-native rate limiting:

```python
# Initialization (app/main.py)
from fastapi_limiter import FastAPILimiter
import redis.asyncio as redis

@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_connection = redis.from_url(settings.REDIS_URL, decode_responses=True)
    await FastAPILimiter.init(redis_connection)
    yield
    await FastAPILimiter.close()
    await redis_connection.close()

# Usage (app/upload/router.py)
from fastapi_limiter.depends import RateLimiter

@router.post(
    "/upload",
    dependencies=[Depends(RateLimiter(times=10, seconds=60))]  # 10/minute
)
async def upload_health_data(...):
    ...
```

**Why fastapi-limiter over SlowAPI?**
- ✅ Async-native (no sync Redis operations)
- ✅ No greenlet context conflicts with uvloop + async SQLAlchemy
- ✅ Production-ready
- ⚠️ Note: Doesn't add rate limit headers like SlowAPI (but returns 429 correctly)

### Production Performance

- **uvloop**: 2-4x faster I/O operations (~50% performance improvement over asyncio)
- **expire_on_commit=False**: AsyncSQLAlchemy best practice for async contexts
- **Connection pooling**: AsyncAdaptedQueuePool (default) for proper greenlet context

## Data Flow

### Upload Pipeline

```
1. Client → WebAuthn Server
   ├─ Authenticate with passkey
   └─ Receive JWT token

2. Client → Health API (/auth/webauthn/exchange)
   ├─ Exchange WebAuthn JWT
   ├─ Verify JWT using JWKS
   ├─ Create/get health user
   └─ Issue Health API JWT

3. Client → Health API (/v1/upload)
   ├─ Verify Health API JWT
   ├─ Validate AVRO file
   ├─ Stream to MinIO (Data Lake)
   ├─ Publish message to RabbitMQ
   └─ Return 202 Accepted

4. Background Processing (Future: ETL Engine)
   ├─ Consume message from RabbitMQ
   ├─ Process AVRO file
   ├─ Generate clinical narrative
   └─ Store in processed data layer
```

### Distributed Tracing Flow

All services send traces to the shared Jaeger instance:

```
1. WebAuthn authentication → Span: "webauthn.authenticate"
2. Token exchange → Span: "health-api.token_exchange"
3. File upload → Span: "health-api.upload"
   ├─ Nested Span: "minio.put_object"
   └─ Nested Span: "rabbitmq.publish"
4. ETL processing → Span: "etl.process_file" (future)
```

View all correlated spans in Jaeger UI: http://localhost:16687

## Security Considerations

### Authentication & Authorization

1. **WebAuthn FIDO2** - Passwordless authentication
   - Private keys never leave device
   - Resistant to phishing
   - Hardware-backed security keys supported

2. **JWT Tokens** - Stateless authorization
   - RS256 signed (public key cryptography)
   - 15-minute expiration
   - JWKS-based key rotation support

3. **Token Exchange** - Service isolation
   - Each service issues its own tokens
   - Independent permissions model
   - Audit trail per service

### Data Security

1. **Encryption at Rest** (MinIO)
   - AES-256-GCM encryption
   - Server-side encryption (SSE-S3)

2. **Encryption in Transit**
   - HTTPS enforced by Envoy Gateway (production)
   - TLS for database connections (production)

3. **Secrets Management**
   - Docker secrets for credentials
   - Auto-generated secure passwords (32 bytes)
   - `.env` files excluded from git

### Network Security

1. **Zero-Trust Gateway** (Envoy)
   - All traffic goes through gateway
   - JWT validation at gateway level
   - No direct service access

2. **Service Isolation**
   - Separate networks for auth and health services
   - Limited blast radius on compromise
   - Principle of least privilege

3. **Rate Limiting**
   - Per-user rate limits on uploads
   - Redis-backed distributed rate limiting
   - Protection against abuse

## Production Deployment

### Migration from Development to Production

1. **Use Kubernetes** - Replace Docker Compose with Helm charts
2. **Managed Services**:
   - Amazon RDS (PostgreSQL)
   - Amazon ElastiCache (Redis)
   - Amazon S3 (replace MinIO)
   - Amazon MQ (RabbitMQ)
3. **Secrets Management** - AWS Secrets Manager or HashiCorp Vault
4. **Monitoring** - Prometheus + Grafana
5. **Load Balancing** - AWS ALB or nginx
6. **TLS/SSL** - Let's Encrypt or AWS Certificate Manager
7. **Backup Strategy** - Automated snapshots and point-in-time recovery

### Scaling Considerations

```
Health API (Stateless)
├─ Horizontal scaling: Add more instances
├─ Load balancer: nginx or ALB
└─ Session storage: Redis (already external)

Data Lake (MinIO)
├─ Use Amazon S3 in production
└─ Multi-region replication

Message Queue (RabbitMQ)
├─ Use Amazon MQ in production
└─ High availability cluster

Database (PostgreSQL)
├─ Use Amazon RDS Multi-AZ
├─ Read replicas for queries
└─ Connection pooling (pgBouncer)
```

## Migration Path

### From Old Setup to New Setup

The project previously had separate WebAuthn and Jaeger compose files in the infrastructure directory.

These have been **removed** in favor of the MCP-generated stack:
- ✅ More complete (includes Envoy Gateway, example service)
- ✅ Better security (Docker secrets, mTLS)
- ✅ Maintained by MCP (stays up-to-date)
- ✅ Follows zero-trust architecture

**No action needed** - migration is complete.

## Future Enhancements

### 1. Service Mesh Integration
Add Istio/Linkerd sidecars to health services to use the same mTLS patterns as webauthn-stack.

### 2. Unified API Gateway
Move Health API behind Envoy Gateway for unified entry point:
- `http://localhost:8000/auth/*` → WebAuthn
- `http://localhost:8000/api/*` → Health API (JWT required)

### 3. Enhanced Monitoring Stack
Add to webauthn-stack:
- Prometheus (metrics)
- Grafana (dashboards)
- Loki (logs)

All health services would send telemetry to this shared observability stack.

### 4. ETL Narrative Engine
Implement clinical data processing pipeline:
- Consume messages from RabbitMQ
- Process AVRO files from MinIO
- Generate clinical narratives
- Store in processed data layer

### 5. AI Query Interface
Implement MLflow-powered natural language queries:
- Load trained models
- Query processed health data
- Return natural language responses
- Feedback loop for model improvement

## References

- **WebAuthn Stack**: `webauthn-stack/README.md`
- **Integration Guide**: `webauthn-stack/docs/INTEGRATION.md`
- **Getting Started**: `GETTING_STARTED.md`
- **Implementation Plans**: `services/{service}/implementation_plan.md`
- **WebAuthn Server**: https://github.com/hitoshura25/mpo-api-authn-server
- **MCP Generator**: https://github.com/hitoshura25/mpo-api-authn-server/tree/main/mcp-server-webauthn-client
- **OpenTelemetry Python**: https://opentelemetry.io/docs/instrumentation/python/
- **Jaeger Documentation**: https://www.jaegertracing.io/docs/

---

**Last Updated**: 2025-10-31
**Architecture Decision**: Separate stacks with shared Jaeger for distributed tracing
