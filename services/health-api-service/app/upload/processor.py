import uuid
from datetime import datetime, timezone
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import User, Upload
from app.db.session import rollback_session_if_active
from app.upload.validator import HealthDataValidator
from app.services.storage import S3StorageService
from app.services.messaging import RabbitMQService
from app.config import settings
import structlog

logger = structlog.get_logger()

class UploadProcessor:
    def __init__(self):
        self.validator = HealthDataValidator(settings.MAX_FILE_SIZE_MB * 1024 * 1024)
        self.storage = S3StorageService()
        self.messaging = RabbitMQService()

    async def process_upload(self, db: AsyncSession, file: UploadFile, user: User) -> dict:
        """Process complete upload workflow"""
        correlation_id = uuid.uuid4()

        with structlog.contextvars.bound_contextvars(
            correlation_id=str(correlation_id),
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
                timestamp = datetime.now(timezone.utc)
                object_key = self._generate_object_key(
                    validation.record_type,
                    str(user.id),
                    timestamp,
                    validation.file_hash
                )

                # 3. Upload to storage
                file_content = await file.read()
                await self.storage.upload_file(file_content, object_key)

                # 4. Create upload record in database
                upload = Upload(
                    correlation_id=correlation_id,
                    user_id=user.id,
                    object_key=object_key,
                    file_name=file.filename,
                    file_size_bytes=len(file_content),
                    record_type=validation.record_type,
                    record_count=validation.record_count,
                    status="queued",
                )
                db.add(upload)
                await db.commit()

                # 5. Publish processing message
                await self.messaging.initialize()
                message_data = {
                    "bucket": settings.S3_BUCKET_NAME,
                    "key": object_key,
                    "user_id": str(user.id),
                    "record_type": validation.record_type,
                    "upload_timestamp_utc": timestamp.isoformat(),
                    "correlation_id": str(correlation_id),
                    "file_size_bytes": len(file_content),
                    "file_hash": validation.file_hash,
                    "record_count": validation.record_count,
                    "idempotency_key": self._generate_idempotency_key(
                        str(user.id), validation.file_hash, timestamp
                    )
                }

                await self.messaging.publish_health_data_message(message_data)
                await self.messaging.close()

                logger.info("Upload processing completed", object_key=object_key)

                return {
                    "status": "accepted",
                    "object_key": object_key,
                    "correlation_id": correlation_id,
                    "record_type": validation.record_type,
                    "record_count": validation.record_count,
                    "file_size_bytes": len(file_content),
                    "upload_timestamp": timestamp,
                    "processing_status": "queued",
                }

            except Exception as e:
                logger.error("Upload processing failed", error=str(e))
                await rollback_session_if_active(db)
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
