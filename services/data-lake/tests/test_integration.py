import asyncio
import os
import sys
import pytest
import pytest_asyncio
from datetime import datetime, timezone
import subprocess

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from storage.client import SecureMinIOClient
from core.naming import IntelligentObjectKeyGenerator
from config.settings import settings

@pytest.fixture(scope="session")
def docker_services():
    """Starts and stops the MinIO service for the integration tests."""
    compose_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'deployment', 'docker-compose.yml'))
    env_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))

    # Ensure the .env file exists before starting
    if not os.path.exists(env_file):
        pytest.fail(".env file not found. Please run setup-secure-env.sh first.")

    try:
        subprocess.run(
            ["docker", "compose", "-p", "data-lake", "-f", compose_file, "--env-file", env_file, "up", "-d", "--build", "--wait"],
            check=True
        )
        yield
    except subprocess.CalledProcessError as e:
        subprocess.run(
            ["docker", "compose", "-p", "data-lake", "-f", compose_file, "--env-file", env_file, "logs"],
            check=True
        )
        raise e
    finally:
        subprocess.run(
            ["docker", "compose", "-p", "data-lake", "-f", compose_file, "--env-file", env_file, "down"],
            check=True,
            capture_output=True
        )

@pytest_asyncio.fixture
async def test_env(docker_services):
    """Sets up a complete test environment for integration tests."""
    client = SecureMinIOClient(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
        region=settings.minio_region
    )
    await client.initialize_bucket(settings.bucket_name)
    yield client

@pytest.mark.timeout(60)
@pytest.mark.asyncio
async def test_upload_and_download_file(test_env):
    """Tests that a file can be uploaded and downloaded from the data lake."""
    client = test_env

    # Read the sample file
    sample_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..', 'docs/sample-avro-files/StepsRecord_1758407386729.avro'))
    with open(sample_file_path, 'rb') as f:
        file_content = f.read()

    # Generate an object key
    key_generator = IntelligentObjectKeyGenerator()
    object_key = key_generator.generate_raw_key(
        record_type="StepsRecord",
        user_id="test-user",
        timestamp=datetime.now(timezone.utc),
        file_hash="test-hash",
        source_device="test-device"
    )

    # Upload the file
    await client.upload_file(
        bucket_name=settings.bucket_name,
        object_key=object_key,
        file_content=file_content
    )

    # Download the file
    downloaded_content = await client.download_file(
        bucket_name=settings.bucket_name,
        object_key=object_key
    )

    # Assert that the content is the same
    assert file_content == downloaded_content
