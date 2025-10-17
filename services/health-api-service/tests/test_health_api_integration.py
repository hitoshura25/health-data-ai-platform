import os
import subprocess
import pytest
import pytest_asyncio
import httpx
from httpx import ASGITransport
from uuid import uuid4
import asyncio
import avro.schema
import avro.io
import avro.datafile
import io
import structlog
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from datetime import datetime, timezone, timedelta

# The TestClient will automatically load .env.
# Ensure your .env file has the correct localhost URLs for the services below.
from app.main import app
from app.db.models import Base
from app.db.session import get_async_session, rollback_session_if_active
from app.config import settings
from app.limiter import limiter

logger = structlog.get_logger()

# Create a test engine that will be disposed properly between tests
def get_test_engine():
    return create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        poolclass=NullPool  # Use NullPool to avoid connection pool issues in tests
    )

@pytest.fixture(autouse=True)
def test_limiter(monkeypatch):
    """Clear out in memory storage for rate limiting for tests."""
    limiter.limiter.storage.reset()  

@pytest_asyncio.fixture(scope="session")
def docker_services():
    """Starts and stops the dependency services for the integration tests."""
    # Use root docker-compose.yml which includes all services via include directive
    compose_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'docker-compose.yml'))
    # Use root .env file which has all infrastructure variables
    env_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env'))
    # Only start the services needed for health-api tests (postgres renamed from db)
    services = ["postgres", "redis", "minio", "rabbitmq"]
    
    # Ensure a clean slate before starting
    subprocess.run(["docker", "compose", "-f", compose_file, "--env-file", env_file, "down", "-v"], check=True)

    try:
        print("\nStarting dependency services...")
        subprocess.run(
            ["docker", "compose", "-f", compose_file, "--env-file", env_file, "up", "-d", "--build", "--wait"] + services,
            check=True,
            text=True
        )
        yield
    except subprocess.CalledProcessError as e:
        print(f"Docker compose up failed: {e.stdout}\n{e.stderr}")
        raise e
    finally:
        print("\nStopping dependency services...")
        subprocess.run(
            ["docker", "compose", "-f", compose_file, "--env-file", env_file, "down", "-v"],
            check=True
        )

@pytest.fixture(scope="session")
def db_setup(docker_services):
    """Creates and tears down the test database tables for the test session."""
    # Use a temporary engine just for setup/teardown
    # Run async setup/teardown using asyncio.run() to avoid event loop issues
    async def async_setup():
        setup_engine = get_test_engine()
        async with setup_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        await setup_engine.dispose()

    async def async_teardown():
        setup_engine = get_test_engine()
        async with setup_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await setup_engine.dispose()

    asyncio.run(async_setup())
    yield
    asyncio.run(async_teardown())

@pytest.fixture(scope="session")
def s3_bucket_setup(docker_services):
    """Creates the S3 bucket for the tests."""
    setup_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'deployment/scripts/setup_bucket.py'))
    subprocess.run(["python", setup_file], check=True)

@pytest_asyncio.fixture(scope="function")
async def client(db_setup, s3_bucket_setup):
    """
    Provides a transactional database session and an AsyncClient for each test function.
    """
    # Create a fresh engine for each test to avoid event loop issues
    test_engine = get_test_engine()
    async_session_maker = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    connection = await test_engine.connect()
    transaction = await connection.begin()
    session = async_session_maker(bind=connection)

    async def _override_get_async_session():
        yield session

    app.dependency_overrides[get_async_session] = _override_get_async_session

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    del app.dependency_overrides[get_async_session]
    await session.close()
    await rollback_session_if_active(session)
    await connection.close()
    await test_engine.dispose()

@pytest_asyncio.fixture(scope="function")
async def auth_token(client: httpx.AsyncClient):
    """Provides an authenticated user token for tests."""
    user_email = f"testuser_{uuid4()}@example.com"
    user_password = "SecurePassword123!"

    # Register
    register_response = await client.post(
        "/auth/register",
        json={"email": user_email, "password": user_password, "first_name": "Test", "last_name": "User"}
    )
    assert register_response.status_code == 201

    # Login
    login_response = await client.post(
        "/auth/jwt/login",
        data={"username": user_email, "password": user_password}
    )
    assert login_response.status_code == 200
    return login_response.json()["access_token"]

@pytest.mark.asyncio
async def test_root_endpoint(client: httpx.AsyncClient):
    """Tests the root GET / endpoint for basic API information."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Health Data AI Platform API"
    assert "version" in data

@pytest.mark.asyncio
async def test_health_live_endpoint(client: httpx.AsyncClient):
    """Tests that the /health/live endpoint is responding."""
    response = await client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"

@pytest.mark.asyncio
async def test_health_ready_endpoint(client: httpx.AsyncClient):
    """Tests the /health/ready endpoint and its dependencies."""
    response = None
    for i in range(10):
        response = await client.get("/health/ready")
        if response.status_code == 200:
            data = response.json()
            if data["status"] == "healthy":
                break
        print(f"Readiness check attempt {i+1} failed. Retrying in 2 seconds...")
        await asyncio.sleep(2)
        
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    
    expected_dependencies = ["database", "redis", "s3_storage", "message_queue"]
    assert all(dep in data["dependencies"] for dep in expected_dependencies)
    
    for dep_name, dep_status in data["dependencies"].items():
        assert dep_status["status"] == "healthy", f"{dep_name} dependency is not healthy: {dep_status.get('error')}"

@pytest.mark.asyncio
async def test_register_endpoint(client: httpx.AsyncClient):
    """Tests the /auth/register endpoint and validates the response schema."""
    user_email = f"testuser_{uuid4()}@example.com"
    response = await client.post(
        "/auth/register",
        json={"email": user_email, "password": "SecurePassword123!", "first_name": "New", "last_name": "User"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == user_email
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_register_existing_user_conflict(client: httpx.AsyncClient):
    """Tests that registering a user with an existing email returns a 409 Conflict error."""
    user_email = f"testuser_{uuid4()}@example.com"
    user_payload = {"email": user_email, "password": "SecurePassword123!", "first_name": "Existing", "last_name": "User"}

    # First registration
    response1 = await client.post("/auth/register", json=user_payload)
    assert response1.status_code == 201

    # Second registration with the same email
    response2 = await client.post("/auth/register", json=user_payload)
    assert response2.status_code == 409

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload, expected_detail_part",
    [
        ({"email": "invalid-email", "password": "SecurePassword123!"}, "is not a valid email address"),
        ({"email": f"testuser_{uuid4()}@example.com", "password": "short"}, "should have at least 8 characters"),
        ({"password": "SecurePassword123!"}, "field required"),
        ({"email": f"testuser_{uuid4()}@example.com"}, "field required"),
    ],
)
@pytest.mark.asyncio
async def test_register_invalid_payload(client: httpx.AsyncClient, payload: dict, expected_detail_part: str):
    """Tests that registering with an invalid payload returns a 422 Unprocessable Entity error."""
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == 422
    error_data = response.json()
    assert "detail" in error_data
    assert any(expected_detail_part in str(err).lower() for err in error_data["detail"])


@pytest.mark.asyncio
async def test_login_and_logout(client: httpx.AsyncClient, auth_token: str):
    """Tests the /auth/jwt/login and /auth/jwt/logout endpoint."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    
    # Logout
    logout_response = await client.post("/auth/jwt/logout", headers=headers)
    assert logout_response.status_code == 204

    # Verify token is no longer valid
    me_response = await client.get("/users/me", headers=headers)
    assert me_response.status_code == 401

@pytest.mark.asyncio
async def test_login_invalid_credentials(client: httpx.AsyncClient):
    """Tests that logging in with invalid credentials returns a 401 Unauthorized error."""
    user_email = f"testuser_{uuid4()}@example.com"
    user_password = "SecurePassword123!"

    # Register user
    register_response = await client.post(
        "/auth/register",
        json={"email": user_email, "password": user_password, "first_name": "Test", "last_name": "User"}
    )
    assert register_response.status_code == 201

    # Attempt to login with wrong password
    login_response = await client.post(
        "/auth/jwt/login",
        data={"username": user_email, "password": "WrongPassword!"}
    )

    assert login_response.status_code == 401

@pytest.mark.asyncio
async def test_get_and_update_me(client: httpx.AsyncClient, auth_token: str):
    """Tests the GET and PATCH /users/me endpoints."""
    headers = {"Authorization": f"Bearer {auth_token}"}

    # Get current user
    get_response = await client.get("/users/me", headers=headers)
    assert get_response.status_code == 200
    original_user = get_response.json()
    assert original_user["first_name"] == "Test"

    # Update user
    update_payload = {"first_name": "Jane", "last_name": "Doe"}
    patch_response = await client.patch("/users/me", headers=headers, json=update_payload)
    assert patch_response.status_code == 200
    updated_user = patch_response.json()
    assert updated_user["first_name"] == "Jane"

@pytest.mark.asyncio
async def test_upload_unsupported_file_type(client: httpx.AsyncClient, auth_token: str):
    """Tests that uploading a non-Avro file returns a 415 Unsupported Media Type error."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    
    dummy_file_content = b"This is not an Avro file."
    files = {"file": ("test.txt", dummy_file_content, "text/plain")}

    response = await client.post("/v1/upload", headers=headers, files=files)
    
    assert response.status_code == 415
    error_data = response.json()
    assert "detail" in error_data
    assert "unsupported file type" in error_data["detail"].lower()

@pytest.mark.asyncio
async def test_upload_file_too_large(client: httpx.AsyncClient, auth_token: str):
    """Tests that uploading a file larger than the limit returns a 413 Payload Too Large error."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    
    # Create a dummy file larger than the configured max size
    large_file_size = (settings.MAX_FILE_SIZE_MB * 1024 * 1024) + 1
    large_file_content = b"0" * large_file_size
    
    files = {"file": ("large_file.avro", large_file_content, "application/avro")}

    response = await client.post("/v1/upload", headers=headers, files=files)
    
    assert response.status_code == 413

@pytest.mark.asyncio
async def test_upload_invalid_avro_schema(client: httpx.AsyncClient, auth_token: str):
    """Tests that uploading an Avro file with an invalid schema returns a 422 Unprocessable Entity error."""
    headers = {"Authorization": f"Bearer {auth_token}"}

    # Create a dummy Avro file with a schema that doesn't match health data
    schema_dict = {"type": "record", "name": "Invalid", "fields": [{"name": "data", "type": "string"}]}
    schema = avro.schema.make_avsc_object(schema_dict)
    
    writer_buffer = io.BytesIO()
    datum_writer = avro.io.DatumWriter(schema)
    writer = avro.datafile.DataFileWriter(writer_buffer, datum_writer, schema)
    writer.append({"data": "some invalid data"})
    writer.flush()
    writer_buffer.seek(0)
    invalid_avro_content = writer_buffer.read()
    writer.close()

    files = {"file": ("invalid_schema.avro", invalid_avro_content, "application/avro")}

    response = await client.post("/v1/upload", headers=headers, files=files)
    
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_upload_and_status_endpoints(client: httpx.AsyncClient, auth_token: str):
    """Tests the /v1/upload and /v1/upload/status endpoints."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    sample_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'docs', 'sample-avro-files', 'StepsRecord_1758407386729.avro'))
    
    with open(sample_file_path, "rb") as f:
        files = {"file": ("StepsRecord_1758407386729.avro", f.read(), "application/avro"), "description": (None, "Test upload of StepsRecord")}

    upload_response = await client.post("/v1/upload", headers=headers, files=files)
    assert upload_response.status_code == 202
    upload_data = upload_response.json()
    
    assert upload_data["status"] == "accepted"
    assert "correlation_id" in upload_data

    correlation_id = upload_data["correlation_id"]
    status_response = await client.get(f"/v1/upload/status/{correlation_id}", headers=headers)
    assert status_response.status_code == 200
    status_data = status_response.json()
    assert status_data["status"] in ["queued"]

    # Verify all expected fields are present and valid
    assert "description" in status_data
    assert status_data["description"] == "Test upload of StepsRecord"
    assert "retry_count" in status_data
    assert status_data["retry_count"] == 0  # Default value
    assert "quarantined" in status_data
    assert status_data["quarantined"] is False  # Default value
    assert "correlation_id" in status_data
    assert "upload_timestamp" in status_data
    assert "object_key" in status_data
    assert "record_type" in status_data
    assert "record_count" in status_data

@pytest.mark.asyncio
async def test_get_upload_status_not_found(client: httpx.AsyncClient, auth_token: str):
    """Tests that querying for a non-existent correlation ID returns a 404 Not Found error."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    non_existent_correlation_id = uuid4()
    
    response = await client.get(f"/v1/upload/status/{non_existent_correlation_id}", headers=headers)
    
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_upload_history_endpoint(client: httpx.AsyncClient, auth_token: str):
    """Tests the /v1/upload/history endpoint."""
    headers = {"Authorization": f"Bearer {auth_token}"}

    # Perform an upload first
    sample_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'docs', 'sample-avro-files', 'HeartRateRecord_1758407386729.avro'))
    with open(sample_file_path, "rb") as f:
        files = {"file": ("HeartRateRecord_1758407386729.avro", f.read(), "application/avro")}
    upload_resp = await client.post("/v1/upload", headers=headers, files=files)
    assert upload_resp.status_code == 202

    # Get history
    history_response = await client.get("/v1/upload/history?limit=1", headers=headers)
    assert history_response.status_code == 200
    history_data = history_response.json()

    assert "pagination" in history_data
    assert len(history_data["uploads"]) > 0

@pytest.mark.asyncio
async def test_upload_history_pagination_and_filtering(client: httpx.AsyncClient, auth_token: str):
    """Tests pagination and filtering for the /v1/upload/history endpoint."""
    headers = {"Authorization": f"Bearer {auth_token}"}

    # Upload a few files of different types
    file_types = ["StepsRecord", "HeartRateRecord"]
    for file_type in file_types:
        sample_file_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), '..', '..', '..', 'docs', 'sample-avro-files', f'{file_type}_1758407386729.avro'
        ))
        with open(sample_file_path, "rb") as f:
            files = {"file": (os.path.basename(f.name), f.read(), "application/avro")}
            upload_resp = await client.post("/v1/upload", headers=headers, files=files)
            assert upload_resp.status_code == 202

    # 1. Test basic pagination (limit)
    history_response = await client.get("/v1/upload/history?limit=1", headers=headers)
    assert history_response.status_code == 200
    history_data = history_response.json()
    assert len(history_data["uploads"]) == 1
    assert history_data["pagination"]["limit"] == 1
    assert history_data["pagination"]["total"] >= 2
    assert history_data["pagination"]["has_more"] is True

    # 2. Test pagination (offset)
    history_response_page2 = await client.get("/v1/upload/history?limit=1&offset=1", headers=headers)
    assert history_response_page2.status_code == 200
    history_data_page2 = history_response_page2.json()
    assert len(history_data_page2["uploads"]) == 1
    assert history_data_page2["pagination"]["offset"] == 1
    assert history_data["uploads"][0]["correlation_id"] != history_data_page2["uploads"][0]["correlation_id"]

    # 3. Test filtering by record_type
    history_response_steps = await client.get("/v1/upload/history?record_type=AvroStepsRecord", headers=headers)
    assert history_response_steps.status_code == 200
    history_data_steps = history_response_steps.json()
    assert len(history_data_steps["uploads"]) > 0
    for upload in history_data_steps["uploads"]:
        assert upload["record_type"] == "AvroStepsRecord"

    # 4. Test filtering by status
    history_response_queued = await client.get("/v1/upload/history?status=queued", headers=headers)
    assert history_response_queued.status_code == 200
    history_data_queued = history_response_queued.json()
    assert len(history_data_queued["uploads"]) >= 2
    for upload in history_data_queued["uploads"]:
        assert upload["status"] == "queued"


# Additional Test Coverage for Missing Scenarios

@pytest.mark.asyncio
async def test_upload_history_date_filtering(client: httpx.AsyncClient, auth_token: str):
    """Tests date range filtering for the /v1/upload/history endpoint."""
    headers = {"Authorization": f"Bearer {auth_token}"}

    # Upload a file
    sample_file_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..', '..', '..', 'docs', 'sample-avro-files', 'StepsRecord_1758407386729.avro'
    ))
    with open(sample_file_path, "rb") as f:
        files = {"file": (os.path.basename(f.name), f.read(), "application/avro")}
        upload_resp = await client.post("/v1/upload", headers=headers, files=files)
        assert upload_resp.status_code == 202

    # Test from_date filtering (get uploads from today onwards)
    today = datetime.now(timezone.utc).isoformat()
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

    # Get uploads from yesterday onwards (should include today's upload)
    response = await client.get(f"/v1/upload/history?from_date={yesterday}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["uploads"]) > 0

    # Get uploads until tomorrow (should include today's upload)
    response = await client.get(f"/v1/upload/history?to_date={tomorrow}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["uploads"]) > 0

    # Get uploads in a specific range
    response = await client.get(f"/v1/upload/history?from_date={yesterday}&to_date={tomorrow}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["uploads"]) > 0


@pytest.mark.asyncio
async def test_upload_rate_limiting(client: httpx.AsyncClient, auth_token: str):
    """Tests that rate limiting is enforced for uploads and SlowAPI middleware provides proper headers."""
    headers = {"Authorization": f"Bearer {auth_token}"}

    # Create a small valid Avro file for testing
    sample_file_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..', '..', '..', 'docs', 'sample-avro-files', 'StepsRecord_1758407386729.avro'
    ))

    with open(sample_file_path, "rb") as f:
        file_content = f.read()

    # Make rapid uploads until rate limited
    rate_limited = False
    rate_limit_response = None
    successful_response = None

    for i in range(15):  # Try up to 15 uploads
        files = {"file": (f"upload_{i}.avro", file_content, "application/avro")}
        response = await client.post("/v1/upload", headers=headers, files=files)

        if response.status_code == 429:
            # Rate limit hit - this is expected behavior
            error_data = response.json()
            assert "error" in error_data
            rate_limited = True
            rate_limit_response = response
            logger.info(f"Rate limit hit at upload {i+1}")
            break
        elif response.status_code == 202:
            # Upload succeeded - save first successful response for header check
            if successful_response is None:
                successful_response = response
            continue
        else:
            # Unexpected status code
            pytest.fail(f"Unexpected status code {response.status_code} at upload {i+1}")

    # Verify that rate limiting is working (hit at some point)
    assert rate_limited, "Rate limiting should have been triggered within 15 uploads"

    # Verify SlowAPI middleware is providing rate limit headers (production behavior)
    # These headers are ONLY added by SlowAPIMiddleware, not by the decorator alone
    assert successful_response is not None, "Should have at least one successful upload"

    # Check for rate limit headers in successful response (middleware adds these)
    assert "X-RateLimit-Limit" in successful_response.headers, \
        "Missing X-RateLimit-Limit header - SlowAPIMiddleware may not be installed"
    assert "X-RateLimit-Remaining" in successful_response.headers, \
        "Missing X-RateLimit-Remaining header - SlowAPIMiddleware may not be installed"
    assert "X-RateLimit-Reset" in successful_response.headers, \
        "Missing X-RateLimit-Reset header - SlowAPIMiddleware may not be installed"

    # Check for Retry-After header in rate limited response (middleware adds this)
    assert rate_limit_response is not None
    assert "Retry-After" in rate_limit_response.headers, \
        "Missing Retry-After header in 429 response - SlowAPIMiddleware may not be installed"

    logger.info(f"Rate limit headers verified: Limit={successful_response.headers['X-RateLimit-Limit']}, "
                f"Remaining={successful_response.headers['X-RateLimit-Remaining']}, "
                f"Reset={successful_response.headers['X-RateLimit-Reset']}, "
                f"Retry-After={rate_limit_response.headers['Retry-After']}")


@pytest.mark.asyncio
async def test_upload_unauthorized(client: httpx.AsyncClient):
    """Tests that uploading without authentication returns 401."""
    sample_file_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..', '..', '..', 'docs', 'sample-avro-files', 'StepsRecord_1758407386729.avro'
    ))

    with open(sample_file_path, "rb") as f:
        files = {"file": ("StepsRecord_1758407386729.avro", f.read(), "application/avro")}

    # Attempt upload without auth header
    response = await client.post("/v1/upload", files=files)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_upload_status_unauthorized(client: httpx.AsyncClient):
    """Tests that checking upload status without authentication returns 401."""
    fake_correlation_id = uuid4()

    # Attempt to get status without auth header
    response = await client.get(f"/v1/upload/status/{fake_correlation_id}")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_upload_history_unauthorized(client: httpx.AsyncClient):
    """Tests that getting upload history without authentication returns 401."""
    # Attempt to get history without auth header
    response = await client.get("/v1/upload/history")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_user_invalid_data(client: httpx.AsyncClient, auth_token: str):
    """Tests that updating user with invalid data returns 422 validation error."""
    headers = {"Authorization": f"Bearer {auth_token}"}

    # Test 1: Try to update with excessively long names (exceeds 50 char max_length)
    invalid_payload = {
        "first_name": "A" * 51,  # Exceeds 50 character limit
        "last_name": "B" * 51
    }

    response = await client.patch("/users/me", headers=headers, json=invalid_payload)
    # Should return 422 validation error due to Pydantic max_length constraint
    assert response.status_code == 422
    error_data = response.json()
    assert "detail" in error_data

    # Test 2: Valid null values should succeed (these fields are Optional)
    valid_payload = {
        "first_name": None,
        "last_name": None
    }
    response2 = await client.patch("/users/me", headers=headers, json=valid_payload)
    assert response2.status_code == 200  # Null is valid for Optional fields


@pytest.mark.asyncio
async def test_error_response_format(client: httpx.AsyncClient):
    """Tests that error responses match the expected schema with detail field."""
    # Test 1: Login with invalid credentials should have proper error format
    response = await client.post(
        "/auth/jwt/login",
        data={"username": "nonexistent@example.com", "password": "WrongPassword123!"}
    )
    assert response.status_code == 401
    error_data = response.json()
    assert "detail" in error_data

    # Test 2: Upload without auth should have proper error format
    sample_file_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..', '..', '..', 'docs', 'sample-avro-files', 'StepsRecord_1758407386729.avro'
    ))
    with open(sample_file_path, "rb") as f:
        files = {"file": ("test.avro", f.read(), "application/avro")}

    response = await client.post("/v1/upload", files=files)
    assert response.status_code == 401
    error_data = response.json()
    assert "detail" in error_data

    # Test 3: 404 error should have proper format
    response = await client.get("/nonexistent-endpoint")
    assert response.status_code == 404
    error_data = response.json()
    assert "detail" in error_data


@pytest.mark.asyncio
async def test_users_me_unauthorized(client: httpx.AsyncClient):
    """Tests that accessing /users/me without authentication returns 401."""
    # Test GET without auth
    response = await client.get("/users/me")
    assert response.status_code == 401

    # Test PATCH without auth
    response = await client.patch("/users/me", json={"first_name": "Test"})
    assert response.status_code == 401
