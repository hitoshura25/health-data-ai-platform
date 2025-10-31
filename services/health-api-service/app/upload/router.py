from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi_limiter.depends import RateLimiter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.limiter import UPLOAD_RATE_LIMIT
from app.users import current_active_user as get_current_active_user
from app.db.models import User, Upload
from app.db.session import get_async_session
from app.upload.processor import UploadProcessor
from app.config import settings
from app.schemas import UploadResponse, UploadStatusResponse, UploadHistoryResponse, Pagination
import structlog
import uuid
from datetime import datetime

logger = structlog.get_logger()
router = APIRouter(prefix="/v1", tags=["Health Data Upload"])

upload_processor = UploadProcessor()

# Parse rate limit string (e.g., "10/minute")
rate_parts = UPLOAD_RATE_LIMIT.split("/")
rate_times = int(rate_parts[0])
rate_period = rate_parts[1] if len(rate_parts) > 1 else "minute"

# Convert period to seconds for RateLimiter
period_seconds = {
    "second": 1,
    "minute": 60,
    "hour": 3600,
    "day": 86400
}.get(rate_period, 60)

@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(RateLimiter(times=rate_times, seconds=period_seconds))]
)
async def upload_health_data(
    file: UploadFile = File(...),
    description: str = Form(None),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Upload health data file for processing"""

    try:
        result = await upload_processor.process_upload(db, file, user, description)
        return UploadResponse(
            status=result["status"],
            correlation_id=result["correlation_id"],
            object_key=result["object_key"],
            record_type=result["record_type"],
            record_count=result["record_count"],
            file_size_bytes=result["file_size_bytes"],
            upload_timestamp=result["upload_timestamp"],
            processing_status=result["processing_status"],
        )

    except ValueError as e:
        # Validation errors
        error_str = str(e).lower()
        if "file size" in error_str:
            raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=f"File is too large. Maximum size is {settings.MAX_FILE_SIZE_MB}MB.")
        if "unsupported record type" in error_str:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))
        if "only .avro files are supported" in error_str:
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported file type. Only .avro files are supported.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    except Exception as e:
        logger.error("Upload endpoint failed", error=str(e))
        raise HTTPException(status_code=500, detail="Upload processing failed")

@router.get("/upload/status/{correlation_id}", response_model=UploadStatusResponse)
async def get_upload_status(
    correlation_id: uuid.UUID,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get upload processing status"""
    upload = await db.execute(
        select(Upload).where(Upload.correlation_id == correlation_id, Upload.user_id == user.id)
    )
    upload = upload.scalar_one_or_none()

    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    return UploadStatusResponse(
        correlation_id=upload.correlation_id,
        status=upload.status,
        upload_timestamp=upload.upload_timestamp,
        object_key=upload.object_key,
        record_type=upload.record_type,
        record_count=upload.record_count,
        description=upload.description,
        processing_started_at=upload.processing_started_at,
        processing_completed_at=upload.processing_completed_at,
        narrative_preview=upload.narrative_preview,
        error_message=upload.error_message,
        retry_count=upload.retry_count,
        quarantined=upload.quarantined,
    )

@router.get("/upload/history", response_model=UploadHistoryResponse)
async def get_upload_history(
    limit: int = 20,
    offset: int = 0,
    status: str = None,
    record_type: str = None,
    from_date: str = None,
    to_date: str = None,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get user's upload history with optional filtering by status, record_type, and date range"""
    query = select(Upload).where(
        Upload.user_id == user.id
    ).order_by(Upload.upload_timestamp.desc())

    if status is not None:
        query = query.where(Upload.status == status)
    if record_type is not None:
        query = query.where(Upload.record_type == record_type)
    if from_date is not None:
        from_date_dt = datetime.fromisoformat(from_date.replace(' ', '+'))
        query = query.where(Upload.upload_timestamp >= from_date_dt)
    if to_date is not None:
        to_date_dt = datetime.fromisoformat(to_date.replace(' ', '+'))
        query = query.where(Upload.upload_timestamp <= to_date_dt)

    total_query = select(func.count()).select_from(query.alias())
    
    total = await db.scalar(total_query)

    uploads_query = query.limit(limit).offset(offset)
    uploads_result = await db.execute(uploads_query)
    uploads = uploads_result.scalars().all()

    return UploadHistoryResponse(
        uploads=[UploadStatusResponse(
            correlation_id=upload.correlation_id,
            status=upload.status,
            upload_timestamp=upload.upload_timestamp,
            object_key=upload.object_key,
            record_type=upload.record_type,
            record_count=upload.record_count,
            description=upload.description,
            processing_started_at=upload.processing_started_at,
            processing_completed_at=upload.processing_completed_at,
            narrative_preview=upload.narrative_preview,
            error_message=upload.error_message,
            retry_count=upload.retry_count,
            quarantined=upload.quarantined,
        ) for upload in uploads],
        pagination=Pagination(
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + len(uploads)) < total,
        ),
    )
