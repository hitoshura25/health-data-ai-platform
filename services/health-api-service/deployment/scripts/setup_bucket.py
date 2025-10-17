#!/usr/bin/env python3

import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import aioboto3
from botocore.exceptions import ClientError
from app.config import settings
import structlog

logger = structlog.get_logger()

async def setup_bucket():
    """Create the S3 bucket"""

    try:
        logger.info("Initializing MinIO client")
        session = aioboto3.Session()
        async with session.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
        ) as s3:
            try:
                await s3.create_bucket(Bucket=settings.S3_BUCKET_NAME)
                logger.info(f"Bucket {settings.S3_BUCKET_NAME} created successfully")
            except ClientError as e:
                if e.response["Error"]["Code"] != "BucketAlreadyOwnedByYou":
                    raise
                else:
                    logger.info(f"Bucket {settings.S3_BUCKET_NAME} already exists")

    except Exception as e:
        logger.error("Bucket setup failed", error=str(e))
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(setup_bucket())
