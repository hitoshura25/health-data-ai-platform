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
