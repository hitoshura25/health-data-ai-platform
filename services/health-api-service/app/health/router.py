from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis.asyncio as redis
import time

from app.db.session import get_async_session
from app.services.storage import S3StorageService
from app.services.messaging import RabbitMQService
from app.config import settings

router = APIRouter(prefix="/health", tags=["Health Checks"])

@router.get("/live")
async def liveness_check():
    """Liveness probe - returns 200 if service is running"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "Health Data API",
        "version": "1.0.0",
    }

@router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_async_session)):
    """Readiness probe - checks all dependencies"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "Health Data API",
        "version": "1.0.0",
        "dependencies": {}
    }

    overall_healthy = True

    # Check Database
    try:
        start = time.time()
        await db.execute(text("SELECT 1"))
        response_time = int((time.time() - start) * 1000)
        health_status["dependencies"]["database"] = {
            "status": "healthy",
            "response_time_ms": response_time
        }
    except Exception as e:
        health_status["dependencies"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        overall_healthy = False

    # Check Redis
    try:
        start = time.time()
        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        await redis_client.ping()
        response_time = int((time.time() - start) * 1000)
        await redis_client.aclose()
        health_status["dependencies"]["redis"] = {
            "status": "healthy",
            "response_time_ms": response_time
        }
    except Exception as e:
        health_status["dependencies"]["redis"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        overall_healthy = False

    # Check S3
    try:
        start = time.time()
        storage_service = S3StorageService()
        s3_healthy = await storage_service.check_bucket_exists()
        response_time = int((time.time() - start) * 1000)
        if s3_healthy:
            health_status["dependencies"]["s3_storage"] = {
                "status": "healthy",
                "response_time_ms": response_time
            }
        else:
            health_status["dependencies"]["s3_storage"] = {
                "status": "unhealthy",
                "error": "bucket not accessible"
            }
            overall_healthy = False
    except Exception as e:
        health_status["dependencies"]["s3_storage"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        overall_healthy = False

    # Check RabbitMQ
    try:
        start = time.time()
        messaging_service = RabbitMQService()
        await messaging_service.initialize()
        rabbit_healthy = await messaging_service.check_connection()
        response_time = int((time.time() - start) * 1000)
        await messaging_service.close()

        if rabbit_healthy:
            health_status["dependencies"]["message_queue"] = {
                "status": "healthy",
                "response_time_ms": response_time
            }
        else:
            health_status["dependencies"]["message_queue"] = {
                "status": "unhealthy",
                "error": "connection failed"
            }
            overall_healthy = False
    except Exception as e:
        health_status["dependencies"]["message_queue"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        overall_healthy = False

    health_status["status"] = "healthy" if overall_healthy else "unhealthy"
    status_code = status.HTTP_200_OK if overall_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(status_code=status_code, content=health_status)