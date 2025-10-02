from fastapi import FastAPI
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
import structlog
import logging
from contextlib import asynccontextmanager

from app.config import settings
from app.health.router import router as health_router
from app.users import fastapi_users, auth_backend
from app.schemas import UserRead, UserCreate, UserUpdate
from app.upload.router import router as upload_router
from app.db.session import Base, engine
from app.supported_record_types import SUPPORTED_RECORD_TYPES

from app.auth.router import router as auth_router

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Health API service started", version="1.0.0")
    yield
    # any shutdown logic would go here


app = FastAPI(
    title="Health Data AI Platform - API Service",
    description="Secure health data upload and processing API for the Health Data AI Platform.",
    version="1.0.0",
    lifespan=lifespan
)

# Rate limiting
limiter = Limiter(key_func=lambda request: request.scope["client"][0], storage_uri=settings.REDIS_URL)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(health_router)
app.include_router(upload_router)
app.include_router(auth_router)
app.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["Authentication"]
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["Authentication"],
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["User Management"],
)

@app.get("/")
async def root():
    return {
        "message": "Health Data AI Platform API",
        "version": "1.0.0",
        "documentation": "/docs",
        "supported_formats": ["Apache Avro"],
        "supported_record_types": SUPPORTED_RECORD_TYPES,
    }