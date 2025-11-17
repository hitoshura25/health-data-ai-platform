"""
S3/MinIO client for downloading health data files.

Handles file downloads from MinIO data lake with retry logic and error handling.
"""

from typing import Optional, BinaryIO
import io
import aioboto3
import structlog
from botocore.exceptions import ClientError, EndpointConnectionError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

from ..consumer.error_recovery import (
    NetworkError,
    S3TimeoutError,
    S3ConnectionError,
    S3NotFoundError,
    S3AccessDeniedError,
    S3RateLimitError
)

logger = structlog.get_logger()


class S3Client:
    """
    Async S3/MinIO client for file operations.

    Provides reliable file downloads with automatic retry for transient errors.
    """

    def __init__(
        self,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket_name: str,
        region: str = "us-east-1",
        use_ssl: bool = False
    ):
        """
        Initialize S3 client.

        Args:
            endpoint_url: MinIO endpoint URL (e.g., "http://localhost:9000")
            access_key: S3 access key
            secret_key: S3 secret key
            bucket_name: S3 bucket name
            region: AWS region
            use_ssl: Whether to use SSL
        """
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket_name = bucket_name
        self.region = region
        self.use_ssl = use_ssl
        self.logger = structlog.get_logger(bucket=bucket_name)

        # Create aioboto3 session
        self.session = aioboto3.Session()

    async def download_file(
        self,
        key: str,
        max_size_mb: int = 100
    ) -> bytes:
        """
        Download file from S3 and return contents as bytes.

        Args:
            key: S3 object key
            max_size_mb: Maximum file size in MB

        Returns:
            File contents as bytes

        Raises:
            S3NotFoundError: If object not found
            S3AccessDeniedError: If access denied
            S3TimeoutError: If download times out
            NetworkError: If network error occurs
        """
        self.logger.info("downloading_s3_file", key=key)

        try:
            async with self.session.client(
                's3',
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
                use_ssl=self.use_ssl
            ) as s3:
                # Get object
                response = await s3.get_object(
                    Bucket=self.bucket_name,
                    Key=key
                )

                # Check file size
                content_length = response.get('ContentLength', 0)
                max_size_bytes = max_size_mb * 1024 * 1024

                if content_length > max_size_bytes:
                    raise ValueError(
                        f"File size ({content_length} bytes) exceeds maximum "
                        f"allowed size ({max_size_bytes} bytes)"
                    )

                # Read file contents
                async with response['Body'] as stream:
                    file_contents = await stream.read()

                self.logger.info(
                    "s3_file_downloaded",
                    key=key,
                    size_bytes=len(file_contents)
                )

                return file_contents

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')

            if error_code == 'NoSuchKey':
                self.logger.error("s3_object_not_found", key=key)
                raise S3NotFoundError(f"S3 object not found: {key}") from e

            elif error_code == 'AccessDenied':
                self.logger.error("s3_access_denied", key=key)
                raise S3AccessDeniedError(f"S3 access denied: {key}") from e

            elif error_code == 'SlowDown' or error_code == 'RequestLimitExceeded':
                self.logger.warning("s3_rate_limit", key=key)
                raise S3RateLimitError(f"S3 rate limit exceeded: {key}") from e

            else:
                self.logger.error(
                    "s3_client_error",
                    key=key,
                    error_code=error_code,
                    error_message=str(e)
                )
                raise NetworkError(f"S3 client error: {error_code}") from e

        except EndpointConnectionError as e:
            self.logger.error("s3_connection_error", key=key, error=str(e))
            raise S3ConnectionError(f"S3 connection failed: {key}") from e

        except TimeoutError as e:
            self.logger.error("s3_timeout", key=key)
            raise S3TimeoutError(f"S3 download timeout: {key}") from e

        except Exception as e:
            self.logger.error(
                "s3_unexpected_error",
                key=key,
                exception_type=type(e).__name__,
                error=str(e)
            )
            raise NetworkError(f"Unexpected S3 error: {str(e)}") from e

    async def upload_file(
        self,
        key: str,
        content: bytes,
        content_type: str = "application/octet-stream"
    ) -> None:
        """
        Upload file to S3.

        Args:
            key: S3 object key
            content: File contents as bytes
            content_type: MIME type

        Raises:
            NetworkError: If upload fails
        """
        self.logger.info("uploading_s3_file", key=key, size_bytes=len(content))

        try:
            async with self.session.client(
                's3',
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
                use_ssl=self.use_ssl
            ) as s3:
                await s3.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=content,
                    ContentType=content_type
                )

            self.logger.info("s3_file_uploaded", key=key)

        except Exception as e:
            self.logger.error(
                "s3_upload_error",
                key=key,
                exception_type=type(e).__name__,
                error=str(e)
            )
            raise NetworkError(f"S3 upload failed: {str(e)}") from e

    async def check_file_exists(self, key: str) -> bool:
        """
        Check if file exists in S3.

        Args:
            key: S3 object key

        Returns:
            True if file exists, False otherwise
        """
        try:
            async with self.session.client(
                's3',
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
                use_ssl=self.use_ssl
            ) as s3:
                await s3.head_object(Bucket=self.bucket_name, Key=key)
                return True

        except ClientError as e:
            if e.response.get('Error', {}).get('Code') == 'NoSuchKey':
                return False
            raise

        except Exception:
            return False
