# Health API Service - Implementation Plan

A secure, resilient FastAPI service for health data upload and management, combining battle-tested authentication libraries with simple resilience patterns for enterprise-grade reliability.

## Overview

This service provides a REST API for uploading health data files (Avro format), performing validation, storing files in object storage, and publishing processing messages to a message queue. The implementation prioritizes security through proven libraries and operational simplicity through straightforward patterns.

## Architecture Goals

- **Security First:** Use FastAPI-Users for authentication instead of custom JWT implementation
- **Simple Resilience:** Basic retry patterns with tenacity instead of complex circuit breakers
- **Proven Libraries:** Leverage battle-tested components to minimize custom code
- **Production Ready:** Comprehensive health checks, monitoring, and structured logging

## Technology Stack

### Core Dependencies
```txt
fastapi==0.104.1
fastapi-users[sqlalchemy]==12.1.2
uvicorn[standard]==0.24.0
gunicorn==21.2.0
slowapi==0.1.9
structlog==23.2.0
tenacity==8.2.3
prometheus-client==0.19.0
python-multipart==0.0.6
aio-pika==9.3.1
aioboto3==12.0.0
avro==1.11.3
pydantic-settings==2.0.3
redis==5.0.1
```

### Database Dependencies
```txt
sqlalchemy==2.0.23
aiosqlite==0.19.0  # For development
asyncpg==0.29.0    # For production PostgreSQL
```

## Implementation

### 1. Project Structure
```
health-api-service/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   └── database.py
│   ├── upload/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── validator.py
│   │   └── processor.py
│   ├── health/
│   │   ├── __init__.py
│   │   └── router.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── storage.py
│   │   └── messaging.py
│   └── config.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

### 2. Configuration (app/config.py)
```python
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Application
    app_name: str = "Health Data API"
    debug: bool = False

    # Database
    database_url: str = "sqlite+aiosqlite:///./health_api.db"

    # Authentication
    secret_key: str  # Must be provided
    access_token_expire_minutes: int = 60

    # External Services
    redis_url: str = "redis://localhost:6379"
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str  # Must be provided
    s3_bucket_name: str = "health-data"
    rabbitmq_url: str = "amqp://localhost:5672"

    # Rate Limiting
    upload_rate_limit: str = "10/minute"
    default_rate_limit: str = "100/hour"

    # File Validation
    max_file_size_mb: int = 50

    class Config:
        env_file = ".env"

settings = Settings()
```

### 3. Authentication Setup (app/auth/models.py)
```python
from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import uuid

Base = declarative_base()

class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"

    # Additional fields beyond FastAPI-Users defaults
    first_name = Column(String(50), nullable=True)
    last_name = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

### 4. Authentication Schemas (app/auth/schemas.py)
```python
from fastapi_users import schemas
from typing import Optional
from datetime import datetime

class UserRead(schemas.BaseUser[uuid.UUID]):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

class UserCreate(schemas.BaseUserCreate):
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class UserUpdate(schemas.BaseUserUpdate):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
```

### 5. Database Setup (app/auth/database.py)
```python
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.auth.models import User, Base
from app.config import settings

# Create async engine
engine = create_async_engine(settings.database_url)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_async_session():
    async with async_session_maker() as session:
        yield session

async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User)
```

### 6. Authentication Manager (app/auth/__init__.py)
```python
import uuid
from fastapi_users import BaseUserManager, UUIDIDMixin
from fastapi_users.authentication import AuthenticationBackend, BearerAuthentication
from fastapi_users.authentication import JWTAuthentication
from app.auth.models import User
from app.config import settings
import structlog

logger = structlog.get_logger()

class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = settings.secret_key
    verification_token_secret = settings.secret_key

    async def on_after_register(self, user: User, request=None):
        logger.info("User registered", user_id=str(user.id), email=user.email)

    async def on_after_login(self, user: User, request=None):
        logger.info("User logged in", user_id=str(user.id), email=user.email)

async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)

# JWT Authentication
jwt_authentication = JWTAuthentication(
    secret=settings.secret_key,
    lifetime_seconds=settings.access_token_expire_minutes * 60,
)

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=BearerAuthentication(tokenUrl="auth/jwt/login"),
    get_strategy=lambda: jwt_authentication,
)
```

### 7. File Validation (app/upload/validator.py)
```python
import avro.schema
import avro.io
import hashlib
from fastapi import UploadFile, HTTPException
from dataclasses import dataclass
from typing import List, Optional
import structlog

logger = structlog.get_logger()

@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    record_type: Optional[str] = None
    record_count: int = 0
    file_hash: Optional[str] = None

class HealthDataValidator:
    def __init__(self, max_file_size_bytes: int):
        self.max_file_size_bytes = max_file_size_bytes

    async def validate_upload(self, file: UploadFile) -> ValidationResult:
        """Comprehensive file validation"""
        errors = []
        warnings = []

        # Basic file checks
        if file.size > self.max_file_size_bytes:
            errors.append(f"File size {file.size} exceeds maximum {self.max_file_size_bytes}")

        if not file.filename.endswith('.avro'):
            errors.append("Only .avro files are supported")

        if errors:
            return ValidationResult(False, errors, warnings)

        # Read file content
        content = await file.read()
        await file.seek(0)  # Reset file pointer

        # Generate file hash
        file_hash = hashlib.sha256(content).hexdigest()

        # Avro validation
        try:
            bytes_reader = io.BytesIO(content)
            decoder = avro.io.BinaryDecoder(bytes_reader)

            # Read and parse schema
            schema_len = decoder.read_long()
            schema_data = decoder.read(schema_len)
            schema = avro.schema.parse(schema_data.decode('utf-8'))

            # Extract record type
            record_type = schema.name if hasattr(schema, 'name') else 'unknown'

            # Count records
            datum_reader = avro.io.DatumReader(schema)
            record_count = 0

            while True:
                try:
                    record = datum_reader.read(decoder)
                    record_count += 1
                    # Limit validation reads for performance
                    if record_count >= 100:
                        break
                except EOFError:
                    break
                except Exception as e:
                    errors.append(f"Record {record_count} parsing error: {e}")

            if record_count == 0:
                errors.append("No valid records found in Avro file")

            logger.info("File validation completed",
                       filename=file.filename,
                       record_type=record_type,
                       record_count=record_count,
                       file_hash=file_hash[:8])

            return ValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                record_type=record_type,
                record_count=record_count,
                file_hash=file_hash
            )

        except Exception as e:
            errors.append(f"Avro validation failed: {e}")
            return ValidationResult(False, errors, warnings, file_hash=file_hash)
```

### 8. Storage Service (app/services/storage.py)
```python
import aioboto3
from botocore.exceptions import ClientError
from tenacity import retry, stop_after_attempt, wait_exponential
from app.config import settings
import structlog

logger = structlog.get_logger()

class S3StorageService:
    def __init__(self):
        self.session = aioboto3.Session()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def upload_file(self, file_content: bytes, object_key: str) -> bool:
        """Upload file to S3 with retry logic"""
        try:
            async with self.session.client(
                's3',
                endpoint_url=settings.s3_endpoint_url,
                aws_access_key_id=settings.s3_access_key,
                aws_secret_access_key=settings.s3_secret_key
            ) as s3:
                await s3.put_object(
                    Bucket=settings.s3_bucket_name,
                    Key=object_key,
                    Body=file_content,
                    ServerSideEncryption='AES256'
                )

                logger.info("File uploaded successfully", object_key=object_key)
                return True

        except ClientError as e:
            logger.error("S3 upload failed", error=str(e), object_key=object_key)
            raise

    async def check_bucket_exists(self) -> bool:
        """Check if S3 bucket is accessible"""
        try:
            async with self.session.client(
                's3',
                endpoint_url=settings.s3_endpoint_url,
                aws_access_key_id=settings.s3_access_key,
                aws_secret_access_key=settings.s3_secret_key
            ) as s3:
                await s3.head_bucket(Bucket=settings.s3_bucket_name)
                return True
        except ClientError:
            return False
```

### 9. Messaging Service (app/services/messaging.py)
```python
import aio_pika
import json
from tenacity import retry, stop_after_attempt, wait_exponential
from app.config import settings
from datetime import datetime
import structlog

logger = structlog.get_logger()

class RabbitMQService:
    def __init__(self):
        self.connection = None
        self.channel = None

    async def initialize(self):
        """Initialize RabbitMQ connection"""
        self.connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        self.channel = await self.connection.channel()
        await self.channel.confirm_delivery()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5)
    )
    async def publish_health_data_message(self, message_data: dict) -> bool:
        """Publish health data processing message"""
        try:
            # Create message with persistence
            message = aio_pika.Message(
                json.dumps(message_data).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                timestamp=datetime.utcnow()
            )

            # Publish to topic exchange
            exchange = await self.channel.get_exchange("health_data_exchange")
            routing_key = f"health.processing.{message_data.get('record_type', 'unknown').lower()}"

            await exchange.publish(message, routing_key=routing_key, mandatory=True)

            logger.info("Message published successfully",
                       correlation_id=message_data.get('correlation_id'),
                       routing_key=routing_key)
            return True

        except Exception as e:
            logger.error("Message publishing failed", error=str(e))
            raise

    async def check_connection(self) -> bool:
        """Check RabbitMQ connection health"""
        try:
            if self.connection and not self.connection.is_closed:
                return True
        except Exception:
            pass
        return False

    async def close(self):
        """Close RabbitMQ connection"""
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
```

### 10. Upload Processing (app/upload/processor.py)
```python
import uuid
from datetime import datetime
from fastapi import UploadFile
from app.auth.models import User
from app.upload.validator import HealthDataValidator, ValidationResult
from app.services.storage import S3StorageService
from app.services.messaging import RabbitMQService
from app.config import settings
import structlog

logger = structlog.get_logger()

class UploadProcessor:
    def __init__(self):
        self.validator = HealthDataValidator(settings.max_file_size_mb * 1024 * 1024)
        self.storage = S3StorageService()
        self.messaging = RabbitMQService()

    async def process_upload(self, file: UploadFile, user: User) -> dict:
        """Process complete upload workflow"""
        correlation_id = str(uuid.uuid4())

        with structlog.contextvars.bound_contextvars(
            correlation_id=correlation_id,
            user_id=str(user.id),
            filename=file.filename
        ):
            logger.info("Upload processing started", file_size=file.size)

            try:
                # 1. Validate file
                validation = await self.validator.validate_upload(file)
                if not validation.is_valid:
                    logger.warning("File validation failed", errors=validation.errors)
                    raise ValueError(f"Validation failed: {', '.join(validation.errors)}")

                # 2. Generate object key
                timestamp = datetime.utcnow()
                object_key = self._generate_object_key(
                    validation.record_type,
                    str(user.id),
                    timestamp,
                    validation.file_hash
                )

                # 3. Upload to storage
                file_content = await file.read()
                await self.storage.upload_file(file_content, object_key)

                # 4. Publish processing message
                message_data = {
                    "bucket": settings.s3_bucket_name,
                    "key": object_key,
                    "user_id": str(user.id),
                    "record_type": validation.record_type,
                    "upload_timestamp_utc": timestamp.isoformat(),
                    "correlation_id": correlation_id,
                    "file_size_bytes": len(file_content),
                    "file_hash": validation.file_hash,
                    "record_count": validation.record_count,
                    "idempotency_key": self._generate_idempotency_key(
                        str(user.id), validation.file_hash, timestamp
                    )
                }

                await self.messaging.publish_health_data_message(message_data)

                logger.info("Upload processing completed", object_key=object_key)

                return {
                    "status": "accepted",
                    "object_key": object_key,
                    "correlation_id": correlation_id,
                    "record_type": validation.record_type,
                    "record_count": validation.record_count
                }

            except Exception as e:
                logger.error("Upload processing failed", error=str(e))
                raise

    def _generate_object_key(self, record_type: str, user_id: str,
                           timestamp: datetime, file_hash: str) -> str:
        """Generate intelligent object key with embedded metadata"""
        date_path = timestamp.strftime("%Y/%m/%d")
        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
        short_hash = file_hash[:8]

        filename = f"{user_id}_{timestamp_str}_{short_hash}.avro"
        return f"raw/{record_type}/{date_path}/{filename}"

    def _generate_idempotency_key(self, user_id: str, file_hash: str,
                                timestamp: datetime) -> str:
        """Generate idempotency key for deduplication"""
        import hashlib
        key_input = f"{user_id}:{file_hash}:{timestamp.isoformat()}"
        return hashlib.sha256(key_input.encode()).hexdigest()[:16]
```

### 11. Upload Router (app/upload/router.py)
```python
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from app.auth import current_active_user
from app.auth.models import User
from app.upload.processor import UploadProcessor
from app.config import settings
import structlog

logger = structlog.get_logger()

# Rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.redis_url,
    default_limits=[settings.default_rate_limit]
)

router = APIRouter(prefix="/v1", tags=["upload"])

upload_processor = UploadProcessor()

@router.post("/upload")
@limiter.limit(settings.upload_rate_limit)
async def upload_health_data(
    file: UploadFile = File(...),
    current_user: User = Depends(current_active_user)
):
    """Upload health data file for processing"""

    try:
        result = await upload_processor.process_upload(file, current_user)
        return result

    except ValueError as e:
        # Validation errors
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error("Upload endpoint failed", error=str(e))
        raise HTTPException(status_code=500, detail="Upload processing failed")
```

### 12. Health Check Router (app/health/router.py)
```python
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from app.services.storage import S3StorageService
from app.services.messaging import RabbitMQService
from datetime import datetime
import redis.asyncio as redis
import asyncio
import structlog

logger = structlog.get_logger()

router = APIRouter(prefix="/health", tags=["health"])

@router.get("/live")
async def liveness_check():
    """Liveness probe - returns 200 if service is running"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@router.get("/ready")
async def readiness_check():
    """Readiness probe - checks all dependencies"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "dependencies": {}
    }

    overall_healthy = True

    # Check Redis
    try:
        redis_client = redis.from_url(settings.redis_url)
        await asyncio.wait_for(redis_client.ping(), timeout=2.0)
        health_status["dependencies"]["redis"] = {"status": "healthy"}
        await redis_client.close()
    except Exception as e:
        health_status["dependencies"]["redis"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False

    # Check S3
    try:
        storage_service = S3StorageService()
        s3_healthy = await storage_service.check_bucket_exists()
        if s3_healthy:
            health_status["dependencies"]["s3"] = {"status": "healthy"}
        else:
            health_status["dependencies"]["s3"] = {"status": "unhealthy", "error": "bucket not accessible"}
            overall_healthy = False
    except Exception as e:
        health_status["dependencies"]["s3"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False

    # Check RabbitMQ
    try:
        messaging_service = RabbitMQService()
        await messaging_service.initialize()
        rabbit_healthy = await messaging_service.check_connection()
        await messaging_service.close()

        if rabbit_healthy:
            health_status["dependencies"]["rabbitmq"] = {"status": "healthy"}
        else:
            health_status["dependencies"]["rabbitmq"] = {"status": "unhealthy", "error": "connection failed"}
            overall_healthy = False
    except Exception as e:
        health_status["dependencies"]["rabbitmq"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False

    health_status["status"] = "healthy" if overall_healthy else "unhealthy"
    status_code = status.HTTP_200_OK if overall_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(status_code=status_code, content=health_status)
```

### 13. Main Application (app/main.py)
```python
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi_users import FastAPIUsers
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from prometheus_client import make_asgi_app
import structlog

from app.config import settings
from app.auth import auth_backend, get_user_manager
from app.auth.models import User
from app.auth.schemas import UserRead, UserCreate, UserUpdate
from app.auth.database import create_db_and_tables
from app.upload.router import router as upload_router
from app.health.router import router as health_router

# Configure structured logging
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="ISO"),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.WriteLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Initialize FastAPI
app = FastAPI(
    title=settings.app_name,
    description="Secure health data upload and processing API",
    version="1.0.0"
)

# Rate limiting
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.redis_url
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# FastAPI Users
fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [auth_backend],
)

current_active_user = fastapi_users.current_user(active=True)

# Include routers
app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(upload_router)
app.include_router(health_router)

# Prometheus metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

@app.on_event("startup")
async def on_startup():
    # Create database tables
    await create_db_and_tables()
    logger.info("Health API service started", version="1.0.0")

@app.on_event("shutdown")
async def on_shutdown():
    logger.info("Health API service shutting down")

@app.get("/")
async def root():
    return {"message": "Health Data API", "version": "1.0.0"}
```

### 14. Docker Configuration

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create application directory
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN groupadd -r healthapi && useradd -r -g healthapi healthapi
RUN chown -R healthapi:healthapi /app
USER healthapi

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health/ready || exit 1

# Run application
CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--access-logfile", "-"]
```

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  health-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://healthapi:password@db:5432/healthapi
      - SECRET_KEY=${SECRET_KEY}
      - S3_SECRET_KEY=${S3_SECRET_KEY}
      - REDIS_URL=redis://redis:6379
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672
    depends_on:
      - db
      - redis
      - rabbitmq
    restart: unless-stopped

  db:
    image: postgres:15
    environment:
      POSTGRES_DB: healthapi
      POSTGRES_USER: healthapi
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    restart: unless-stopped

  rabbitmq:
    image: rabbitmq:3.12-management
    environment:
      RABBITMQ_DEFAULT_USER: guest
      RABBITMQ_DEFAULT_PASS: guest
    ports:
      - "15672:15672"  # Management UI
    restart: unless-stopped

volumes:
  postgres_data:
```

## Deployment Instructions

### Development
1. **Install dependencies:** `pip install -r requirements.txt`
2. **Set up environment:** Run `../../setup-all-services.sh` from project root to generate `.env` files
3. **Start services:** `docker compose up -d` from project root
4. **Run application:** `uvicorn app.main:app --reload`

### Production
1. **Build image:** `docker build -t health-api:latest .`
2. **Configure environment:** Set all required environment variables
3. **Deploy:** `docker-compose up -d`

## Testing

### Unit Tests
```python
# tests/test_upload.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_upload_requires_auth():
    response = client.post("/v1/upload")
    assert response.status_code == 401

def test_health_live():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
```

### Integration Testing
Create test files for each major component and integration points with external services.

## Monitoring and Observability

The service provides:
- **Prometheus metrics** at `/metrics`
- **Structured JSON logging** with correlation IDs
- **Health checks** for dependency monitoring
- **Request tracing** through the entire pipeline

## Security Considerations

- **Authentication:** FastAPI-Users provides secure JWT handling
- **Rate limiting:** Prevents abuse and DOS attacks
- **Input validation:** Comprehensive Avro file validation
- **Secrets management:** All secrets via environment variables
- **Least privilege:** Non-root container execution

## Integration Points

- **Message Queue:** Publishes to `health_data_exchange` topic exchange
- **Object Storage:** Stores files with intelligent naming convention
- **Database:** User management and authentication
- **Redis:** Rate limiting and caching

This implementation provides a production-ready health data API service with enterprise-grade security, resilience, and observability while maintaining operational simplicity.