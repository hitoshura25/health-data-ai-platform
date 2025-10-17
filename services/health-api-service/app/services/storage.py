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
                endpoint_url=settings.S3_ENDPOINT_URL,
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY
            ) as s3:
                await s3.put_object(
                    Bucket=settings.S3_BUCKET_NAME,
                    Key=object_key,
                    Body=file_content
                )

                logger.info("File uploaded successfully", object_key=object_key)
                return True

        except ClientError as e:
            logger.error("S3 upload failed", error=str(e), object_key=object_key)
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def upload_file_streaming(self, file_obj, object_key: str, content_length: int = None) -> bool:
        """
        Stream upload file to MinIO with automatic chunked transfer.

        Memory efficient: File is read in chunks automatically by MinIO client.
        For files >8MB, MinIO may use multipart upload internally.

        Args:
            file_obj: File-like object (e.g., SpooledTemporaryFile from UploadFile)
            object_key: S3 object key where file should be stored
            content_length: Optional content length (if known, helps S3 client)

        Returns:
            True if upload successful
        """
        try:
            async with self.session.client(
                's3',
                endpoint_url=settings.S3_ENDPOINT_URL,
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY
            ) as s3:
                # Prepare put_object kwargs
                put_kwargs = {
                    'Bucket': settings.S3_BUCKET_NAME,
                    'Key': object_key,
                    'Body': file_obj
                }

                # Add ContentLength if provided (helps with upload performance)
                if content_length is not None:
                    put_kwargs['ContentLength'] = content_length

                # put_object accepts file-like objects and streams them automatically
                # MinIO client handles chunked transfer encoding internally
                await s3.put_object(**put_kwargs)

                logger.info("File streamed successfully", object_key=object_key)
                return True

        except ClientError as e:
            logger.error("S3 streaming upload failed", error=str(e), object_key=object_key)
            raise

    async def check_bucket_exists(self) -> bool:
        """Check if S3 bucket is accessible"""
        try:
            async with self.session.client(
                's3',
                endpoint_url=settings.S3_ENDPOINT_URL,
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY
            ) as s3:
                await s3.head_bucket(Bucket=settings.S3_BUCKET_NAME)
                return True
        except ClientError:
            return False
