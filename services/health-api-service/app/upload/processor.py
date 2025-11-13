import uuid
import hashlib
import avro.io
import avro.datafile
from datetime import datetime, timezone
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from opentelemetry import trace
from app.db.models import User, Upload
from app.db.session import rollback_session_if_active
from app.upload.validator import HealthDataValidator
from app.services.storage import S3StorageService
from app.services.messaging import RabbitMQService
from app.config import settings
import structlog

logger = structlog.get_logger()
tracer = trace.get_tracer(__name__)

class UploadProcessor:
    def __init__(self):
        self.validator = HealthDataValidator(settings.MAX_FILE_SIZE_MB * 1024 * 1024)
        self.storage = S3StorageService()
        self.messaging = RabbitMQService()

    async def process_upload(self, db: AsyncSession, file: UploadFile, user: User, description: str = None) -> dict:
        """
        Process upload with streaming - minimal memory usage.

        Memory efficient: Only holds Avro header + current record in memory.
        Streams file directly to MinIO while calculating hash and counting records.
        """
        correlation_id = uuid.uuid4()

        with structlog.contextvars.bound_contextvars(
            correlation_id=str(correlation_id),
            user_id=str(user.id),
            filename=file.filename
        ):
            # Create parent span for entire upload processing
            with tracer.start_as_current_span("process_upload") as span:
                span.set_attribute("user_id", str(user.id))
                span.set_attribute("filename", file.filename)
                span.set_attribute("correlation_id", str(correlation_id))

                logger.info("Upload processing started (streaming mode)")

                try:
                    # 1. Lightweight validation (only reads header + samples first 10 records)
                    with tracer.start_as_current_span("validate_upload"):
                        validation = await self.validator.validate_upload_streaming(file)
                        if not validation.is_valid:
                            logger.warning("File validation failed", errors=validation.errors)
                            raise ValueError(f"Validation failed: {', '.join(validation.errors)}")
                        span.set_attribute("record_type", validation.record_type)

                    # 2. Generate timestamp and object key
                    timestamp = datetime.now(timezone.utc)

                    # 3. Stream to MinIO + calculate hash + count records simultaneously
                    file_obj = file.file
                    with tracer.start_as_current_span("stream_to_storage") as storage_span:
                        object_key, file_size, file_hash, record_count = await self._stream_with_metadata(
                            file_obj,
                            validation.record_type,
                            str(user.id),
                            timestamp
                        )
                        storage_span.set_attribute("object_key", object_key)
                        storage_span.set_attribute("file_size_bytes", file_size)
                        storage_span.set_attribute("record_count", record_count)

                    # 5. Create upload record in database
                    with tracer.start_as_current_span("persist_upload_metadata"):
                        upload = Upload(
                            correlation_id=correlation_id,
                            user_id=user.id,
                            object_key=object_key,
                            file_name=file.filename,
                            file_size_bytes=file_size,
                            record_type=validation.record_type,
                            record_count=record_count,
                            status="queued",
                            description=description,
                        )
                        db.add(upload)
                        await db.commit()

                    # 6. Publish processing message
                    with tracer.start_as_current_span("publish_to_message_queue") as msg_span:
                        await self.messaging.initialize()
                        message_data = {
                            "bucket": settings.S3_BUCKET_NAME,
                            "key": object_key,
                            "user_id": str(user.id),
                            "record_type": validation.record_type,
                            "upload_timestamp_utc": timestamp.isoformat(),
                            "correlation_id": str(correlation_id),
                            "file_size_bytes": file_size,
                            "file_hash": file_hash,
                            "record_count": record_count,
                            "idempotency_key": self._generate_idempotency_key(
                                str(user.id), file_hash
                            )
                        }

                        await self.messaging.publish_health_data_message(message_data)
                        await self.messaging.close()
                        msg_span.set_attribute("routing_key", f"health.processing.{validation.record_type.lower()}")

                    logger.info("Upload processing completed (streaming)",
                               object_key=object_key,
                               file_size=file_size,
                               record_count=record_count)

                    return {
                        "status": "accepted",
                        "object_key": object_key,
                        "correlation_id": correlation_id,
                        "record_type": validation.record_type,
                        "record_count": record_count,
                        "file_size_bytes": file_size,
                        "upload_timestamp": timestamp,
                        "processing_status": "queued",
                    }

                except Exception as e:
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    logger.error("Upload processing failed", error=str(e))
                    await rollback_session_if_active(db)
                    raise

    async def _stream_with_metadata(self, file_obj, record_type: str, user_id: str, timestamp: datetime) -> tuple[str, int, str, int]:
        """
        Process file with minimal memory usage - three efficient passes:
        1. Hash calculation (chunked read from disk)
        2. Upload to MinIO (chunked read from disk)
        3. Record counting (streaming read from disk)

        Returns: (object_key, file_size, file_hash, record_count)

        Memory efficiency:
        - Files >1MB are already on disk (FastAPI's SpooledTemporaryFile)
        - Each pass reads in small chunks (8KB) - only one chunk in memory at a time
        - Peak memory: ~16KB regardless of file size
        - Disk I/O is efficient for local temporary files

        This approach is practical because:
        - We MUST calculate hash for integrity/deduplication
        - We MUST upload file to MinIO
        - We MUST count records for metadata
        - Doing all three in separate passes is simpler and more maintainable
        - For local disk files, multiple chunked passes are fast enough
        """
        # Get file size first (needed for S3 upload)
        file_obj.seek(0, 2)  # Seek to end
        file_size = file_obj.tell()
        file_obj.seek(0)  # Seek back to start

        # Pass 1: Calculate hash by reading file in chunks
        # For files >1MB, this reads from disk, not memory
        hasher = hashlib.sha256()
        chunk_size = 8192  # 8KB chunks - only this much in memory at once
        while True:
            chunk = file_obj.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
        file_hash = hasher.hexdigest()

        # Seek back to start for upload
        file_obj.seek(0)

        # Generate object key (timestamp-based, hash stored in DB not in key)
        object_key = self._generate_object_key_streaming(record_type, user_id, timestamp)

        # Pass 2: Upload to MinIO
        # boto3 will read file_obj in chunks internally - another efficient disk read
        await self.storage.upload_file_streaming(file_obj, object_key, content_length=file_size)

        # Pass 3: Count records (file already uploaded, seek back to start)
        # Avro reader streams records - doesn't load entire file into memory
        file_obj.seek(0)
        record_count = 0
        reader = None
        try:
            datum_reader = avro.io.DatumReader()
            reader = avro.datafile.DataFileReader(file_obj, datum_reader)
            for record in reader:
                record_count += 1
            reader.close()
            logger.info("Record counting completed", record_count=record_count)
        except Exception as e:
            logger.warning("Could not count records", error=str(e))
            record_count = 0  # Upload succeeded, count is optional
        finally:
            if reader is not None:
                reader.close()

        return object_key, file_size, file_hash, record_count

    def _generate_object_key_streaming(self, record_type: str, user_id: str, timestamp: datetime) -> str:
        """
        Generate object key for streaming upload (timestamp-based).

        Note: Hash is calculated during upload and stored in DB, not in object key.
        This avoids needing to read file twice or copy objects in MinIO.
        """
        date_path = timestamp.strftime("%Y/%m/%d")
        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S_%f")  # Include microseconds for uniqueness
        filename = f"{user_id}_{timestamp_str}.avro"
        return f"raw/{record_type}/{date_path}/{filename}"

    def _generate_object_key(self, record_type: str, user_id: str,
                           timestamp: datetime, file_hash: str) -> str:
        """Generate intelligent object key with embedded metadata (legacy - kept for compatibility)"""
        date_path = timestamp.strftime("%Y/%m/%d")
        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
        short_hash = file_hash[:8]

        filename = f"{user_id}_{timestamp_str}_{short_hash}.avro"
        return f"raw/{record_type}/{date_path}/{filename}"

    def _generate_idempotency_key(self, user_id: str, file_hash: str) -> str:
        """Generate idempotency key for deduplication"""
        import hashlib
        key_input = f"{user_id}:{file_hash}"
        return hashlib.sha256(key_input.encode()).hexdigest()[:16]
