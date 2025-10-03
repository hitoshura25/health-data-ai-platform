from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.limiter import limiter
from app.users import current_active_user as get_current_active_user
from app.db.models import User, Upload
from app.db.session import get_async_session
from app.upload.processor import UploadProcessor
from app.config import settings
from app.schemas import UploadResponse, UploadStatusResponse, UploadHistoryResponse, Pagination
import structlog
import uuid

logger = structlog.get_logger()
router = APIRouter(prefix="/v1", tags=["Health Data Upload"])

upload_processor = UploadProcessor()

@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit(settings.UPLOAD_RATE_LIMIT)
async def upload_health_data(
    request: Request,
    file: UploadFile = File(...),
    description: str = Form(None),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Upload health data file for processing"""

    try:
        result = await upload_processor.process_upload(db, file, user)
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
        processing_started_at=upload.processing_started_at,
        processing_completed_at=upload.processing_completed_at,
        narrative_preview=upload.narrative_preview,
        error_message=upload.error_message,
    )

@router.get("/upload/history", response_model=UploadHistoryResponse)
async def get_upload_history(
    limit: int = 20,
    offset: int = 0,
    status: str = None,
    record_type: str = None,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get user's upload history"""
    query = select(Upload).where(
        Upload.user_id == user.id
    ).order_by(Upload.upload_timestamp.desc())

    if status is not None:
        query = query.where(Upload.status == status)
    if record_type is not None:
        query = query.where(Upload.record_type == record_type)

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
            processing_started_at=upload.processing_started_at,
            processing_completed_at=upload.processing_completed_at,
            narrative_preview=upload.narrative_preview,
            error_message=upload.error_message,
        ) for upload in uploads],
        pagination=Pagination(
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + len(uploads)) < total,
        ),
    )
