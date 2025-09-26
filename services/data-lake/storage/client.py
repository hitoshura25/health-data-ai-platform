from minio import Minio
from minio.error import S3Error
from minio.versioningconfig import VersioningConfig
from minio.commonconfig import ENABLED, DISABLED
from minio.sseconfig import SSEConfig, Rule
import structlog
import asyncio
from typing import Optional, Dict, Any, List, AsyncGenerator
from datetime import datetime
import json

logger = structlog.get_logger()

class SecureMinIOClient:
    """Secure MinIO client with enterprise features"""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        secure: bool = False,
        region: str = "us-east-1"
    ):
        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
            region=region
        )
        self.endpoint = endpoint
        self.region = region

    async def initialize_bucket(
        self,
        bucket_name: str,
        enable_versioning: bool = True,
        enable_encryption: bool = True
    ):
        """Initialize bucket with security features"""

        try:
            # Check if bucket exists
            if self.client.bucket_exists(bucket_name):
                logger.info("Bucket already exists", bucket=bucket_name)
            else:
                # Create bucket if it doesn't exist
                self.client.make_bucket(bucket_name, location=self.region)
                logger.info("Bucket created", bucket=bucket_name)

            # Enable versioning
            if enable_versioning:
                self.client.set_bucket_versioning(bucket_name, VersioningConfig(ENABLED))
                logger.info("Versioning enabled", bucket=bucket_name)

            # Enable encryption
            if enable_encryption:
                logger.info("Setting up encryption")
                rule = Rule("AES256")
                sse_config = SSEConfig(rule)
                logger.info("Setting up bucket encryption")
                self.client.set_bucket_encryption(bucket_name, sse_config)
                logger.info("Encryption enabled", bucket=bucket_name)

        except S3Error as e:
            logger.error("Failed to initialize bucket", bucket=bucket_name, error=str(e))
            raise

    def setup_bucket_policy(self, bucket_name: str, policy: Dict[str, Any]):
        """Set up bucket access policy"""
        try:
            policy_json = json.dumps(policy)
            self.client.set_bucket_policy(bucket_name, policy_json)
            logger.info("Bucket policy configured", bucket=bucket_name)

        except S3Error as e:
            logger.error("Failed to set bucket policy", bucket=bucket_name, error=str(e))
            raise

    async def upload_file(
        self,
        bucket_name: str,
        object_key: str,
        file_content: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None
    ) -> bool:
        """Upload file with metadata"""

        try:
            import io

            file_stream = io.BytesIO(file_content)

            self.client.put_object(
                bucket_name,
                object_key,
                file_stream,
                length=len(file_content),
                content_type=content_type,
                metadata=metadata or {}
            )

            logger.info("File uploaded successfully",
                       bucket=bucket_name,
                       object_key=object_key,
                       size_bytes=len(file_content))

            return True

        except S3Error as e:
            logger.error("File upload failed",
                        bucket=bucket_name,
                        object_key=object_key,
                        error=str(e))
            raise

    async def download_file(self, bucket_name: str, object_key: str) -> bytes:
        """Download file content"""
        try:
            response = self.client.get_object(bucket_name, object_key)
            content = response.read()
            response.close()
            response.release_conn()

            logger.debug("File downloaded successfully",
                        bucket=bucket_name,
                        object_key=object_key,
                        size_bytes=len(content))

            return content

        except S3Error as e:
            logger.error("File download failed",
                        bucket=bucket_name,
                        object_key=object_key,
                        error=str(e))
            raise

    async def list_objects_with_metadata(
        self,
        bucket_name: str,
        prefix: str = "",
        recursive: bool = False
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """List objects with detailed metadata"""

        try:
            objects = self.client.list_objects(
                bucket_name,
                prefix=prefix,
                recursive=recursive
            )

            for obj in objects:
                # Get additional metadata
                stat = self.client.stat_object(bucket_name, obj.object_name)

                yield {
                    "object_name": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified,
                    "etag": obj.etag,
                    "content_type": stat.content_type,
                    "metadata": stat.metadata,
                    "version_id": getattr(stat, 'version_id', None)
                }

        except S3Error as e:
            logger.error("Failed to list objects", bucket=bucket_name, error=str(e))
            raise

    async def move_to_quarantine(
        self,
        bucket_name: str,
        source_key: str,
        quarantine_key: str,
        reason: str
    ) -> bool:
        """Move file to quarantine with reason metadata"""

        try:
            # Copy to quarantine location with reason metadata
            copy_source = {"Bucket": bucket_name, "Key": source_key}

            self.client.copy_object(
                bucket_name,
                quarantine_key,
                copy_source,
                metadata={
                    "quarantine_reason": reason,
                    "quarantine_timestamp": datetime.utcnow().isoformat(),
                    "original_key": source_key
                },
                metadata_directive="REPLACE"
            )

            # Delete original file
            self.client.remove_object(bucket_name, source_key)

            logger.info("File moved to quarantine",
                       original_key=source_key,
                       quarantine_key=quarantine_key,
                       reason=reason)

            return True

        except S3Error as e:
            logger.error("Failed to quarantine file",
                        source_key=source_key,
                        error=str(e))
            raise

    async def get_bucket_stats(self, bucket_name: str) -> Dict[str, Any]:
        """Get comprehensive bucket statistics"""

        try:
            stats = {
                "bucket_name": bucket_name,
                "total_objects": 0,
                "total_size_bytes": 0,
                "by_prefix": {},
                "by_storage_class": {},
                "last_modified_range": {
                    "earliest": None,
                    "latest": None
                }
            }

            objects = self.client.list_objects(bucket_name, recursive=True)

            for obj in objects:
                stats["total_objects"] += 1
                stats["total_size_bytes"] += obj.size

                # Track by prefix
                prefix = obj.object_name.split('/')[0]
                if prefix not in stats["by_prefix"]:
                    stats["by_prefix"][prefix] = {"objects": 0, "size_bytes": 0}

                stats["by_prefix"][prefix]["objects"] += 1
                stats["by_prefix"][prefix]["size_bytes"] += obj.size

                # Track date range
                if stats["last_modified_range"]["earliest"] is None or obj.last_modified < stats["last_modified_range"]["earliest"]:
                    stats["last_modified_range"]["earliest"] = obj.last_modified

                if stats["last_modified_range"]["latest"] is None or obj.last_modified > stats["last_modified_range"]["latest"]:
                    stats["last_modified_range"]["latest"] = obj.last_modified

            return stats

        except S3Error as e:
            logger.error("Failed to get bucket stats", bucket=bucket_name, error=str(e))
            raise

    def check_bucket_health(self, bucket_name: str) -> Dict[str, Any]:
        """Check bucket health and accessibility"""

        health_status = {
            "bucket_name": bucket_name,
            "accessible": False,
            "versioning_enabled": False,
            "encryption_enabled": False,
            "lifecycle_configured": False,
            "errors": []
        }

        try:
            # Check if bucket exists and is accessible
            if self.client.bucket_exists(bucket_name):
                health_status["accessible"] = True

                # Check versioning
                try:
                    versioning = self.client.get_bucket_versioning(bucket_name)
                    health_status["versioning_enabled"] = versioning.status == "Enabled"
                except:
                    health_status["errors"].append("Could not check versioning status")

                # Check encryption
                try:
                    encryption = self.client.get_bucket_encryption(bucket_name)
                    health_status["encryption_enabled"] = encryption is not None
                except:
                    health_status["errors"].append("Could not check encryption status")

                # Check lifecycle
                try:
                    lifecycle = self.client.get_bucket_lifecycle(bucket_name)
                    health_status["lifecycle_configured"] = len(lifecycle.rules) > 0
                except:
                    health_status["errors"].append("Could not check lifecycle configuration")

            else:
                health_status["errors"].append("Bucket does not exist or is not accessible")

        except Exception as e:
            health_status["errors"].append(f"Health check failed: {e}")

        return health_status