#!/usr/bin/env python3

import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from storage.client import SecureMinIOClient
from core.lifecycle import DataLifecycleManager
from config.settings import settings
import json
import structlog

logger = structlog.get_logger()

async def setup_data_lake():
    """Complete data lake setup"""

    try:
        # Initialize client
        logger.info("Initializing MinIO client")
        client = SecureMinIOClient(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
            region=settings.minio_region
        )

        # Initialize bucket with security features
        logger.info("Initializing bucket")
        await client.initialize_bucket(
            settings.bucket_name,
            enable_versioning=settings.enable_versioning,
            enable_encryption=settings.enable_encryption
        )

        # Setup lifecycle policies
        logger.info("Setting up lifecycle policies")
        lifecycle_manager = DataLifecycleManager(client.client)
        lifecycle_config = {
            'raw_data_glacier_days': settings.raw_data_glacier_days,
            'raw_data_deep_archive_days': settings.raw_data_deep_archive_days,
            'raw_data_expiration_days': settings.raw_data_expiration_days,
            'processed_data_glacier_days': settings.processed_data_glacier_days,
            'processed_data_expiration_days': settings.processed_data_expiration_days,
            'quarantine_retention_days': settings.quarantine_retention_days
        }

        lifecycle_manager.setup_lifecycle_policies(settings.bucket_name, lifecycle_config)

        # Setup bucket policy
        logger.info("Setting up bucket policy")
        bucket_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": "arn:aws:iam::health-api-service"},
                    "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
                    "Resource": f"arn:aws:s3:::{settings.bucket_name}/raw/*"
                },
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": "arn:aws:iam::etl-worker"},
                    "Action": ["s3:GetObject", "s3:PutObject"],
                    "Resource": [
                        f"arn:aws:s3:::{settings.bucket_name}/raw/*",
                        f"arn:aws:s3:::{settings.bucket_name}/processed/*",
                        f"arn:aws:s3:::{settings.bucket_name}/quarantine/*"
                    ]
                },
                {
                    "Effect": "Deny",
                    "Principal": "*",
                    "Action": "*",
                    "Resource": f"arn:aws:s3:::{settings.bucket_name}/*",
                    "Condition": {
                        "Bool": {"aws:SecureTransport": "false"}
                    }
                }
            ]
        }

        client.setup_bucket_policy(settings.bucket_name, bucket_policy)

        logger.info("Data lake setup completed successfully")

    except Exception as e:
        logger.error("Data lake setup failed", error=str(e))
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(setup_data_lake())