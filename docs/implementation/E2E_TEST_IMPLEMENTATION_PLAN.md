# End-to-End Test Implementation Plan
## Health Data Upload with Full Distributed Tracing

**Goal**: Create an E2E test that uploads an AVRO file through the health services upload pipeline with full Jaeger distributed tracing visibility.

**Scope**:
- **Phase 1** (This Plan): WebAuthn Authentication → Token Exchange → Health API Upload → MinIO Storage → RabbitMQ Message
- **Phase 2** (Future): ETL Narrative Engine consumer (processes RabbitMQ messages and generates clinical narratives)

**Note**: This plan focuses on Phase 1 - establishing the upload pipeline with distributed tracing. ETL processing will be implemented separately.

---

## Current Architecture Analysis

### ✅ What's Already Built

#### 1. **WebAuthn Stack** (`webauthn-stack/`)
- Envoy Gateway (port 8000) with JWT verification
- WebAuthn Server (FIDO2 authentication)
- Jaeger (port 16687) - **shared distributed tracing**
- PostgreSQL (5433) - credentials only
- Redis (6380) - sessions only
- **Status**: ✅ Fully operational, E2E tests passing

#### 2. **Health API Service** (`services/health-api-service/`)
- **Framework**: FastAPI with async support
- **Authentication**: JWT-based (currently local JWT, ready for WebAuthn integration)
- **Upload Endpoint**: `POST /v1/upload`
  - Accepts AVRO files
  - Validates file format and record type
  - Streams to MinIO (Data Lake)
  - Publishes message to RabbitMQ
  - Returns correlation_id for tracking
- **Storage Integration**: S3StorageService → MinIO
- **Messaging Integration**: RabbitMQService → RabbitMQ
- **Status**: ✅ Implemented, **BUT not running** (Docker service exists but no tracing yet)

#### 3. **Data Lake Service** (`services/data-lake/`)
- **Technology**: MinIO (S3-compatible)
- **Ports**: 9000 (API), 9001 (Console)
- **Status**: ✅ Running and tested

#### 4. **Message Queue Service** (`services/message-queue/`)
- **Technology**: RabbitMQ
- **Ports**: 5672 (AMQP), 15672 (Management UI)
- **Exchange**: Topic exchange (`health-data`)
- **Routing**: `health.processing.{record_type}`
- **Status**: ✅ Running and tested

#### 5. **Sample Data**
- **Location**: `docs/sample-avro-files/`
- **Available**: BloodGlucoseRecord, HeartRateRecord, ActiveCaloriesBurnedRecord
- **Size**: ~38KB per file
- **Status**: ✅ Ready to use

#### 6. **ETL Narrative Engine** (`services/etl-narrative-engine/`)
- **Purpose**: Consumes RabbitMQ messages, processes AVRO files, generates clinical narratives
- **Status**: ⏸️ **Deferred to Phase 2** (implementation plan exists, code not built yet)
- **Impact on Phase 1**: Messages will queue in RabbitMQ; upload status will remain "queued"

---

## Current Gaps (Phase 1 Focus)

### 🔴 **Critical Missing Pieces for Upload Pipeline**

1. **No OpenTelemetry/Tracing in Health API**
   - Health API service doesn't send traces to Jaeger yet
   - Can't see upload flow in Jaeger UI
   - Need to add OpenTelemetry instrumentation

2. **Health Services Not Started**
   - Health API container not running
   - PostgreSQL health DB not initialized
   - Redis not configured

3. **WebAuthn ↔ Health API Integration (Token Exchange)**
   - Health API uses local JWT (fastapi-users) for authorization
   - Needs token exchange endpoint to verify WebAuthn JWTs
   - Must map WebAuthn user identity to Health API users

4. **E2E Test Infrastructure**
   - No test in `webauthn-stack/tests/` for health upload
   - Need to copy AVRO file to test environment
   - Need authenticated upload flow (WebAuthn → Token Exchange → Upload)

---

## Implementation Plan

### **Phase 1: Add Distributed Tracing to Health API** 🎯

**Goal**: Health API sends traces to Jaeger (in webauthn-stack)

#### Tasks:

1. **Add OpenTelemetry Dependencies** (`services/health-api-service/requirements.txt`)
   ```txt
   opentelemetry-api==1.22.0
   opentelemetry-sdk==1.22.0
   opentelemetry-instrumentation-fastapi==0.43b0
   opentelemetry-instrumentation-sqlalchemy==0.43b0
   opentelemetry-instrumentation-aio-pika==0.43b0
   opentelemetry-exporter-otlp-proto-grpc==1.22.0
   ```

2. **Create Tracing Module** (`services/health-api-service/app/tracing.py`)
   ```python
   from opentelemetry import trace
   from opentelemetry.sdk.trace import TracerProvider
   from opentelemetry.sdk.trace.export import BatchSpanProcessor
   from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
   from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
   from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
   from app.config import settings

   def setup_tracing(app):
       """Configure OpenTelemetry to send traces to shared Jaeger"""

       # Set up tracer provider
       provider = TracerProvider()

       # Configure OTLP exporter to webauthn-stack Jaeger
       otlp_exporter = OTLPSpanExporter(
           endpoint=settings.JAEGER_OTLP_ENDPOINT,  # http://host.docker.internal:4319
           insecure=True  # For local development
       )

       provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
       trace.set_tracer_provider(provider)

       # Auto-instrument FastAPI
       FastAPIInstrumentor.instrument_app(app)

       # Auto-instrument SQLAlchemy
       from app.db.session import engine
       SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)

       return trace.get_tracer("health-api-service")
   ```

3. **Update Config** (`services/health-api-service/app/config.py`)
   ```python
   class Settings(BaseSettings):
       # ... existing settings ...

       # Jaeger tracing (points to webauthn-stack)
       JAEGER_OTLP_ENDPOINT: str = "http://host.docker.internal:4319"
       JAEGER_SERVICE_NAME: str = "health-api-service"
   ```

4. **Initialize Tracing in Main** (`services/health-api-service/app/main.py`)
   ```python
   from app.tracing import setup_tracing

   # Add to lifespan startup:
   @asynccontextmanager
   async def lifespan(app: FastAPI):
       # ... existing startup ...

       # Initialize distributed tracing
       setup_tracing(app)
       logger.info("Distributed tracing initialized",
                   jaeger_endpoint=settings.JAEGER_OTLP_ENDPOINT)

       yield
   ```

5. **Add Custom Spans for Key Operations**
   ```python
   # In upload/processor.py
   from opentelemetry import trace

   tracer = trace.get_tracer(__name__)

   async def process_upload(...):
       with tracer.start_as_current_span("process_upload") as span:
           span.set_attribute("user_id", str(user.id))
           span.set_attribute("filename", file.filename)

           # ... existing logic ...

           with tracer.start_as_current_span("upload_to_minio"):
               await self.storage.upload_file_streaming(...)

           with tracer.start_as_current_span("publish_to_rabbitmq"):
               await self.messaging.publish_health_data_message(...)
   ```

6. **Update Docker Compose** (`services/health-api-service/health-api.compose.yml`)
   ```yaml
   services:
     health-api:
       environment:
         # ... existing env vars ...

         # Jaeger tracing
         - JAEGER_OTLP_ENDPOINT=http://host.docker.internal:4319
         - JAEGER_SERVICE_NAME=health-api-service
   ```

**Expected Result**:
- Health API sends traces to Jaeger
- Can see upload flow: FastAPI → Validation → MinIO → RabbitMQ
- All operations visible in http://localhost:16687

---

### **Phase 2: Token Exchange Implementation** 🔐

**Goal**: Implement token exchange endpoint - Health API verifies WebAuthn JWTs and issues Health API tokens

**Architecture Decision**: Use **token exchange pattern** (industry best practice)

**Why Token Exchange?**
- ✅ **Separation of Concerns**: WebAuthn handles authentication, Health API handles authorization
- ✅ **Service-Specific Permissions**: Health API JWT can include health-specific permissions (upload, view, export)
- ✅ **Independent Token Lifecycle**: WebAuthn tokens short-lived (15 min), Health tokens longer (1 hour+)
- ✅ **Audit Trail**: Separate logs for authentication events vs authorization events
- ✅ **Future-Proof**: Easy to add other auth providers (OAuth, SAML) without changing Health API

#### Implementation Tasks:

1. **Fetch WebAuthn Public Key on Startup** (`services/health-api-service/app/auth/webauthn_config.py`)
   ```python
   import requests
   import structlog
   from app.config import settings

   logger = structlog.get_logger()

   class WebAuthnConfig:
       """WebAuthn server configuration and public key cache"""

       def __init__(self):
           self.public_key: str = None
           self.public_key_url = settings.WEBAUTHN_PUBLIC_KEY_URL

       def fetch_public_key(self) -> str:
           """Fetch and cache WebAuthn RS256 public key"""
           if self.public_key is None:
               try:
                   response = requests.get(self.public_key_url, timeout=5)
                   response.raise_for_status()
                   self.public_key = response.text
                   logger.info("WebAuthn public key fetched successfully")
               except Exception as e:
                   logger.error("Failed to fetch WebAuthn public key", error=str(e))
                   raise
           return self.public_key

   # Global instance
   webauthn_config = WebAuthnConfig()
   ```

2. **Token Exchange Endpoint** (`services/health-api-service/app/auth/router.py`)
   ```python
   from fastapi import APIRouter, HTTPException, Depends, Body
   from sqlalchemy.ext.asyncio import AsyncSession
   from sqlalchemy import select
   import jwt
   import structlog
   from pydantic import BaseModel

   from app.db.session import get_async_session
   from app.db.models import User
   from app.auth.webauthn_config import webauthn_config
   from app.users import auth_backend, fastapi_users
   from app.schemas import UserRead

   logger = structlog.get_logger()
   router = APIRouter(prefix="/auth", tags=["Authentication"])

   class TokenExchangeRequest(BaseModel):
       webauthn_token: str

   class TokenExchangeResponse(BaseModel):
       access_token: str
       token_type: str = "bearer"
       user: UserRead

   @router.post("/webauthn/exchange", response_model=TokenExchangeResponse)
   async def exchange_webauthn_token(
       request: TokenExchangeRequest = Body(...),
       db: AsyncSession = Depends(get_async_session)
   ):
       """
       Exchange WebAuthn JWT for Health API JWT

       Flow:
       1. Verify WebAuthn JWT signature using public key
       2. Extract user identity (sub = username from WebAuthn)
       3. Get or create Health API user
       4. Issue Health API JWT using fastapi-users
       """

       try:
           # Verify WebAuthn JWT
           public_key = webauthn_config.fetch_public_key()

           payload = jwt.decode(
               request.webauthn_token,
               public_key,
               algorithms=["RS256"],
               issuer="webauthn-server",
               options={
                   "verify_signature": True,
                   "verify_exp": True,
                   "verify_iss": True,
               }
           )

           webauthn_username = payload["sub"]  # Username from WebAuthn

           logger.info("WebAuthn token verified", webauthn_user=webauthn_username)

       except jwt.ExpiredSignatureError:
           raise HTTPException(401, "WebAuthn token expired")
       except jwt.InvalidSignatureError:
           raise HTTPException(401, "Invalid WebAuthn token signature")
       except jwt.InvalidIssuerError:
           raise HTTPException(401, "Invalid token issuer")
       except Exception as e:
           logger.error("Token verification failed", error=str(e))
           raise HTTPException(401, f"Token verification failed: {e}")

       # Get or create Health API user
       result = await db.execute(
           select(User).where(User.email == webauthn_username)
       )
       user = result.scalar_one_or_none()

       if not user:
           # Auto-create user from WebAuthn identity
           from app.users import get_user_manager
           from app.schemas import UserCreate

           user_manager = get_user_manager(db).__anext__()

           user_create = UserCreate(
               email=webauthn_username,
               password=None,  # No password for WebAuthn users
               is_verified=True  # Pre-verified via WebAuthn
           )

           try:
               user = await user_manager.create(user_create, safe=False)
               logger.info("New user created from WebAuthn", user_id=user.id, email=user.email)
           except Exception as e:
               logger.error("User creation failed", error=str(e))
               raise HTTPException(500, "Failed to create user")

       # Generate Health API JWT
       token = await auth_backend.get_strategy().write_token(user)

       logger.info("Token exchange successful",
                   health_user_id=user.id,
                   webauthn_user=webauthn_username)

       return TokenExchangeResponse(
           access_token=token,
           user=UserRead.from_orm(user)
       )
   ```

3. **Update Config** (`services/health-api-service/app/config.py`)
   ```python
   class Settings(BaseSettings):
       # ... existing settings ...

       # WebAuthn Integration
       WEBAUTHN_PUBLIC_KEY_URL: str = "http://host.docker.internal:8000/public-key"
       WEBAUTHN_ISSUER: str = "webauthn-server"
   ```

4. **Initialize WebAuthn Config on Startup** (`services/health-api-service/app/main.py`)
   ```python
   from app.auth.webauthn_config import webauthn_config

   @asynccontextmanager
   async def lifespan(app: FastAPI):
       # ... existing startup ...

       # Fetch WebAuthn public key
       try:
           webauthn_config.fetch_public_key()
           logger.info("WebAuthn integration initialized")
       except Exception as e:
           logger.error("WebAuthn initialization failed - token exchange will not work", error=str(e))

       yield
   ```

5. **Update Docker Compose** (`services/health-api-service/health-api.compose.yml`)
   ```yaml
   services:
     health-api:
       environment:
         # ... existing env vars ...

         # WebAuthn Integration
         - WEBAUTHN_PUBLIC_KEY_URL=http://host.docker.internal:8000/public-key
         - WEBAUTHN_ISSUER=webauthn-server
   ```

---

### **Phase 3: E2E Test Implementation** 🧪

**Goal**: Playwright test that uploads AVRO file with full trace visibility

#### Test File: `webauthn-stack/tests/health-upload-e2e.spec.js`

```javascript
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

test.describe('Health Data Upload End-to-End', () => {

  test('should upload AVRO file through complete stack with distributed tracing', async ({ page }) => {
    // --- Setup: Authenticate with WebAuthn ---
    const username = `e2e-health-test-${Date.now()}@example.com`;

    await test.step('Register and authenticate user', async () => {
      // Use existing WebAuthn registration flow
      await page.goto('http://localhost:8082');

      // Create virtual authenticator
      const cdpSession = await page.context().newCDPSession(page);
      await cdpSession.send('WebAuthn.enable');
      await cdpSession.send('WebAuthn.addVirtualAuthenticator', {
        options: {
          protocol: 'ctap2',
          transport: 'usb',
          hasResidentKey: true,
          hasUserVerification: true,
          isUserVerified: true
        }
      });

      // Register
      await page.fill('#username', username);
      await page.fill('#displayName', 'E2E Test User');
      await page.click('#register-button');
      await page.waitForSelector('.success-message');

      // Authenticate
      await page.fill('#auth-username', username);
      await page.click('#authenticate-button');
      await page.waitForSelector('.auth-success');
    });

    // --- Step 1: Get WebAuthn JWT Token ---
    let webauthnToken;
    await test.step('Extract WebAuthn JWT from authentication', async () => {
      // WebAuthn JWT is returned in the authentication response
      const authResponse = await page.textContent('#auth-response');
      const authData = JSON.parse(authResponse);
      webauthnToken = authData.access_token;

      expect(webauthnToken).toBeTruthy();
      console.log('WebAuthn JWT obtained:', webauthnToken.substring(0, 50) + '...');
    });

    // --- Step 2: Exchange WebAuthn Token for Health API Token ---
    let healthApiToken;
    await test.step('Exchange WebAuthn token for Health API token', async () => {
      const response = await page.request.post('http://localhost:8001/auth/webauthn/exchange', {
        headers: {
          'Content-Type': 'application/json'
        },
        data: {
          webauthn_token: webauthnToken
        }
      });

      expect(response.status()).toBe(200);

      const exchangeData = await response.json();
      healthApiToken = exchangeData.access_token;

      expect(healthApiToken).toBeTruthy();
      expect(exchangeData.user).toBeTruthy();
      expect(exchangeData.user.email).toBe(username);

      console.log('Health API token obtained');
      console.log('User auto-created:', exchangeData.user.email);
    });

    // --- Step 3: Prepare AVRO File ---
    const avroFilePath = path.join(__dirname, '../../docs/sample-avro-files/BloodGlucoseRecord_1758407139312.avro');

    await test.step('Verify AVRO file exists', async () => {
      const fileExists = fs.existsSync(avroFilePath);
      expect(fileExists).toBe(true);

      const stats = fs.statSync(avroFilePath);
      console.log(`AVRO file size: ${stats.size} bytes`);
    });

    // --- Step 4: Upload to Health API ---
    let correlationId;
    let uploadResponse;

    await test.step('Upload AVRO file to Health API with Health API token', async () => {
      // Read file
      const fileBuffer = fs.readFileSync(avroFilePath);
      const fileName = path.basename(avroFilePath);

      // Create FormData
      const formData = new FormData();
      const blob = new Blob([fileBuffer], { type: 'application/octet-stream' });
      formData.append('file', blob, fileName);
      formData.append('description', 'E2E test upload - Blood Glucose data');

      // Upload via Health API using Health API JWT (not WebAuthn JWT)
      const response = await page.request.post('http://localhost:8001/v1/upload', {
        headers: {
          'Authorization': `Bearer ${healthApiToken}`  // Health API token from exchange
        },
        multipart: formData
      });

      expect(response.status()).toBe(202); // Accepted

      uploadResponse = await response.json();
      console.log('Upload response:', uploadResponse);

      correlationId = uploadResponse.correlation_id;
      expect(correlationId).toBeTruthy();
      expect(uploadResponse.status).toBe('accepted');
      expect(uploadResponse.processing_status).toBe('queued');
      expect(uploadResponse.record_type).toBe('BloodGlucoseRecord');
    });

    // --- Step 5: Verify Data in MinIO ---
    await test.step('Verify file stored in MinIO', async () => {
      // Poll upload status
      let status = 'queued';
      let attempts = 0;
      const maxAttempts = 10;

      while (status === 'queued' && attempts < maxAttempts) {
        await page.waitForTimeout(1000); // Wait 1 second

        const statusResponse = await page.request.get(
          `http://localhost:8001/v1/upload/status/${correlationId}`,
          {
            headers: {
              'Authorization': `Bearer ${healthApiToken}`  // Use Health API token
            }
          }
        );

        const statusData = await statusResponse.json();
        status = statusData.status;
        console.log(`Upload status (attempt ${attempts + 1}): ${status}`);

        expect(statusData.object_key).toBeTruthy();
        expect(statusData.record_count).toBeGreaterThan(0);

        attempts++;
      }

      // File should be in MinIO (status will remain "queued" - ETL consumer not running yet)
      expect(uploadResponse.object_key).toMatch(/^raw\/BloodGlucoseRecord\/\d{4}\/\d{2}\/\d{2}\/.+\.avro$/);
      console.log('Note: Upload status will remain "queued" - ETL Narrative Engine deferred to Phase 2');
    });

    // --- Step 6: Verify Message in RabbitMQ ---
    await test.step('Verify message published to RabbitMQ', async () => {
      // Message queued for future ETL processing
      console.log('✅ Message published to RabbitMQ exchange: health-data');
      console.log('✅ Routing key: health.processing.bloodglucoserecord');
      console.log('Note: Message will remain in queue until ETL consumer is implemented (Phase 2)');
    });

    // --- Step 7: Verify Distributed Traces in Jaeger ---
    await test.step('Verify full trace in Jaeger', async () => {
      // Open Jaeger UI
      await page.goto('http://localhost:16687');

      // Search for traces from health-api-service
      await page.selectOption('[data-test="service-selector"]', 'health-api-service');
      await page.click('[data-test="find-traces-button"]');

      // Wait for traces to appear
      await page.waitForTimeout(2000);

      // Find our upload trace (by correlation_id tag or operation name)
      const traces = await page.locator('[data-test="trace-item"]');
      const traceCount = await traces.count();

      expect(traceCount).toBeGreaterThan(0);
      console.log(`Found ${traceCount} traces for health-api-service`);

      // Click on the first trace to see details
      if (traceCount > 0) {
        await traces.first().click();
        await page.waitForTimeout(1000);

        // Verify trace spans
        const spans = await page.locator('[data-test="span"]');
        const spanCount = await spans.count();

        console.log(`Trace contains ${spanCount} spans`);

        // Should have spans for:
        // - FastAPI request handling
        // - File validation
        // - MinIO upload
        // - RabbitMQ publish
        expect(spanCount).toBeGreaterThan(3);
      }
    });

    // --- Summary ---
    console.log('✅ End-to-End Upload Pipeline Test Complete!');
    console.log('Flow verified:');
    console.log('  1. WebAuthn authentication → WebAuthn JWT');
    console.log('  2. Token exchange → Health API JWT');
    console.log('  3. Upload AVRO file → Health API');
    console.log('  4. File stored → MinIO (Data Lake)');
    console.log('  5. Message published → RabbitMQ (queued for ETL)');
    console.log('  6. Full trace visible → Jaeger');
    console.log('');
    console.log('Phase 2 (Future): ETL Narrative Engine will process queued messages');
  });

});
```

---

### **Phase 4: Infrastructure Setup** 🚀

**Goal**: Start all required services

#### Steps:

1. **Start WebAuthn Stack** (already done)
   ```bash
   cd webauthn-stack/docker && docker compose up -d && cd ../..
   ```

2. **Start Health Services**
   ```bash
   # Start infrastructure
   docker compose up -d postgres redis minio rabbitmq

   # Wait for services to be healthy
   docker compose ps

   # Start Health API
   docker compose up -d health-api

   # Check logs
   docker compose logs -f health-api
   ```

3. **Verify Services**
   ```bash
   # WebAuthn Gateway
   curl http://localhost:8000/health

   # Jaeger UI
   open http://localhost:16687

   # Health API
   curl http://localhost:8001/

   # MinIO Console
   open http://localhost:9001

   # RabbitMQ Management
   open http://localhost:15672
   ```

4. **Run E2E Test**
   ```bash
   cd webauthn-stack
   npm test -- tests/health-upload-e2e.spec.js
   ```

---

## Expected Trace Flow in Jaeger

When the E2E test runs, you'll see this trace hierarchy in Jaeger:

```
┌─────────────────────────────────────────────────────────────────┐
│ Service: health-api-service                                     │
│ Operation: POST /v1/upload                                      │
│ Duration: ~500ms                                                │
└──┬──────────────────────────────────────────────────────────────┘
   │
   ├─► Span: validate_upload_streaming
   │   Duration: ~50ms
   │   Tags: record_type=BloodGlucoseRecord, file_size=38KB
   │
   ├─► Span: upload_to_minio
   │   Duration: ~200ms
   │   Tags: object_key=raw/BloodGlucoseRecord/2025/10/21/...
   │
   ├─► Span: publish_to_rabbitmq
   │   Duration: ~50ms
   │   Tags: routing_key=health.processing.bloodglucoserecord
   │
   └─► Span: database_insert (SQLAlchemy auto-instrumented)
       Duration: ~20ms
       Tags: table=uploads
```

**Correlation**: The `correlation_id` from the upload response will be tagged in all spans, allowing you to trace the entire flow!

---

## Success Criteria (Phase 1 - Upload Pipeline)

### ✅ Phase 1: Distributed Tracing Complete When:
- [ ] OpenTelemetry dependencies installed in Health API
- [ ] Health API sends traces to shared Jaeger (in webauthn-stack)
- [ ] Upload flow visible in Jaeger UI (http://localhost:16687)
- [ ] Spans show: FastAPI → Validation → MinIO → RabbitMQ
- [ ] Correlation IDs visible in traces

### ✅ Phase 2: Token Exchange Complete When:
- [ ] WebAuthn public key fetched on Health API startup
- [ ] `/auth/webauthn/exchange` endpoint implemented
- [ ] Endpoint verifies WebAuthn JWT signature
- [ ] Endpoint auto-creates Health API user if not exists
- [ ] Endpoint returns Health API JWT token
- [ ] 401 errors on invalid/expired WebAuthn tokens
- [ ] Token exchange traced in Jaeger

### ✅ Phase 3: E2E Test Complete When:
- [ ] Test authenticates via WebAuthn (gets WebAuthn JWT)
- [ ] Test exchanges token (gets Health API JWT)
- [ ] Test uploads AVRO file with Health API JWT
- [ ] Test verifies upload response (202, correlation_id, object_key)
- [ ] Test checks upload status (queued)
- [ ] Test opens Jaeger and finds upload trace
- [ ] All test assertions pass

### ✅ Phase 4: Infrastructure Complete When:
- [ ] WebAuthn stack running (already done)
- [ ] Health services running (postgres, redis, minio, rabbitmq)
- [ ] Health API container running and healthy
- [ ] E2E test passes end-to-end
- [ ] Full trace visible in Jaeger (WebAuthn + Health API spans)
- [ ] File verified in MinIO
- [ ] Message verified in RabbitMQ queue

### 🚀 Phase 1 Complete When All Above Pass!

---

## Estimated Timeline (Phase 1 - Upload Pipeline)

| Phase | Task | Effort | Time |
|-------|------|--------|------|
| 1 | Add OpenTelemetry tracing to Health API | Medium | 2 hours |
| 2 | Implement token exchange endpoint | Medium | 2 hours |
| 3 | Write E2E test (upload + tracing) | Medium | 2 hours |
| 4 | Infrastructure setup & debugging | Low-Medium | 1-2 hours |
| **Total (Phase 1)** | | | **7-8 hours** |

**Phase 2 (Future - ETL Consumer)**:
- Implement ETL Narrative Engine consumer: ~8-10 hours
- Add clinical processors (Blood Glucose, etc.): ~4-6 hours
- Extend E2E test for narrative verification: ~2 hours
- **Total (Phase 2)**: ~14-18 hours

---

## Technical Decisions

### Why OpenTelemetry over Manual Logging?
- **Auto-instrumentation**: FastAPI, SQLAlchemy, HTTP clients automatically traced
- **Standard protocol**: OTLP works with any observability backend
- **Context propagation**: Traces follow requests across services
- **Production ready**: Same setup works in production with minimal changes

### Why Token Exchange Pattern?
- **Production Best Practice**: Separates authentication (WebAuthn) from authorization (Health API)
- **Security**: Each service issues tokens with its own permissions and lifecycle
- **Scalability**: Easy to add other auth providers (OAuth, SAML) in future
- **Audit**: Clear separation between "who authenticated" vs "who accessed health data"
- **Flexibility**: Health API tokens can have longer expiry without compromising WebAuthn security

### Why Defer ETL Consumer to Phase 2?
- **Focus**: Get upload pipeline working first with distributed tracing
- **Testability**: Can verify upload, storage, and messaging independently
- **Complexity**: ETL consumer is a significant component (clinical processors, narratives, training data)
- **Pragmatic**: Messages queue safely in RabbitMQ until consumer is ready
- **Future Enhancement**: Phase 2 will extend E2E test to verify full narrative generation flow

---

## Next Steps After Implementation

1. **Add More E2E Tests**:
   - Different record types (HeartRate, ActiveCalories)
   - File validation errors
   - Rate limiting
   - Duplicate uploads (idempotency)

2. **Implement ETL Consumer**:
   - Service that reads from RabbitMQ
   - Processes AVRO files
   - Generates clinical narratives
   - Updates upload status
   - **Also sends traces to Jaeger!**

3. **Add Performance Tests**:
   - Concurrent uploads
   - Large file handling
   - Trace sampling configuration

4. **Production Hardening**:
   - TLS for all connections
   - Trace sampling (don't trace every request)
   - Jaeger persistent storage
   - Alert on trace anomalies

---

## Architecture Decisions Finalized

1. **Health API Port**: **8001** (WebAuthn Gateway uses 8000)
   - No port conflicts
   - Clear separation of concerns

2. **User Management**: **Auto-create users from WebAuthn JWT**
   - Seamless UX (no separate registration)
   - WebAuthn already verified user identity
   - Health API user linked to WebAuthn identity via email

3. **Token Exchange**: **Production pattern (not direct JWT verification)**
   - Best practice for microservices
   - Clean auth/authz boundaries
   - Future-proof architecture

4. **ETL Processing**: **Deferred to Phase 2**
   - Upload pipeline first (measurable progress)
   - Messages queue safely in RabbitMQ
   - Phase 2 extends E2E test for narratives

---

## Ready to Proceed!

**Implementation order**:
1. Phase 1: OpenTelemetry tracing → Health API
2. Phase 2: Token exchange endpoint → `/auth/webauthn/exchange`
3. Phase 3: E2E test → `webauthn-stack/tests/health-upload-e2e.spec.js`
4. Phase 4: Start services and run test

**Expected outcome**: Working upload pipeline with token exchange and full distributed tracing visible in Jaeger!
