import os
import subprocess
import pytest
import pytest_asyncio
import httpx
from httpx import ASGITransport
from uuid import uuid4
import asyncio

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# The TestClient will automatically load .env.
# Ensure your .env file has the correct localhost URLs for the services below.
from app.main import app
from app.db.models import Base
from app.db.session import get_async_session, rollback_session_if_active
from app.config import settings

# Create a test engine that will be disposed properly between tests
def get_test_engine():
    return create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        poolclass=None  # Use NullPool to avoid connection pool issues in tests
    )

@pytest_asyncio.fixture(scope="session")
def docker_services():
    """Starts and stops the dependency services for the integration tests."""
    compose_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'docker-compose.yml'))
    env_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
    services = ["db", "redis", "minio", "rabbitmq"]
    
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

@pytest_asyncio.fixture(scope="session")
async def db_setup(docker_services):
    """Creates and tears down the test database tables for the test session."""
    # Use a temporary engine just for setup/teardown
    setup_engine = get_test_engine()
    try:
        async with setup_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        yield
    finally:
        async with setup_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await setup_engine.dispose()

@pytest_asyncio.fixture(scope="session")
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
async def test_login_and_logout(client: httpx.AsyncClient, auth_token: str):
    """Tests the /auth/jwt/logout and /auth/jwt/logout endpoint."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    
    # Logout
    logout_response = await client.post("/auth/jwt/logout", headers=headers)
    assert logout_response.status_code == 204

    # Verify token is no longer valid
    me_response = await client.get("/users/me", headers=headers)
    assert me_response.status_code == 401

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
async def test_upload_and_status_endpoints(client: httpx.AsyncClient, auth_token: str):
    """Tests the /v1/upload and /v1/upload/status endpoints."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    sample_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'docs', 'sample-avro-files', 'StepsRecord_1758407386729.avro'))
    
    with open(sample_file_path, "rb") as f:
        files = {"file": ("StepsRecord_1758407386729.avro", f.read(), "application/avro")}

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
