import os
import subprocess
import pytest
import requests
import time
from uuid import UUID, uuid4
from dateutil.parser import isoparse

@pytest.fixture(scope="session")
def docker_services():
    """Starts and stops the health-api service for the integration tests."""
    compose_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'docker-compose.yml'))

    try:
        print("Starting docker services...")
        subprocess.run(
            ["docker", "compose", "-f", compose_file, "up", "-d", "--build", "--wait"],
            check=True,
            text=True
        )
        yield
    except subprocess.CalledProcessError as e:
        print(f"Docker compose up failed: {e.stderr}")
        subprocess.run(
            ["docker", "compose", "-f", compose_file, "logs"],
            check=True
        )
        raise e
    finally:
        print("Stopping docker services...")
        subprocess.run(
            ["docker", "compose", "-f", compose_file, "down"],
            check=True
        )

@pytest.fixture(scope="module")
def auth_token():
    """Provides an authenticated user token for tests."""
    user_email = f"testuser_{uuid4()}@example.com"
    user_password = "SecurePassword123!"

    # Register
    register_response = requests.post(
        "http://localhost:8000/auth/register",
        json={"email": user_email, "password": user_password, "first_name": "Test", "last_name": "User"}
    )
    assert register_response.status_code == 201

    # Login
    login_response = requests.post(
        "http://localhost:8000/auth/jwt/login",
        data={"username": user_email, "password": user_password}
    )
    assert login_response.status_code == 200
    return login_response.json()["access_token"]

def validate_uuid(uuid_string):
    """Helper to check if a string is a valid UUID."""
    try:
        UUID(uuid_string)
        return True
    except ValueError:
        return False

def validate_user_id(user_id):
    """Helper to check if a user ID is a valid integer."""
    return isinstance(user_id, int)

def validate_iso_timestamp(timestamp_string):
    """Helper to check if a string is a valid ISO 8601 timestamp."""
    try:
        isoparse(timestamp_string)
        return True
    except ValueError:
        return False

@pytest.mark.usefixtures("docker_services")
def test_root_endpoint():
    """Tests the root GET / endpoint for basic API information."""
    response = requests.get("http://localhost:8000/")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Health Data AI Platform API"
    assert "version" in data
    assert "documentation" in data
    assert isinstance(data["supported_formats"], list)
    assert isinstance(data["supported_record_types"], list)

@pytest.mark.usefixtures("docker_services")
def test_health_live_endpoint():
    """Tests that the /health/live endpoint is responding."""
    response = requests.get("http://localhost:8000/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert validate_iso_timestamp(data["timestamp"])

@pytest.mark.usefixtures("docker_services")
def test_health_ready_endpoint():
    """Tests the /health/ready endpoint and its dependencies."""
    response = requests.get("http://localhost:8000/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    
    expected_dependencies = ["database", "redis", "s3_storage", "message_queue"]
    assert all(dep in data["dependencies"] for dep in expected_dependencies)
    
    for dep_name, dep_status in data["dependencies"].items():
        assert dep_status["status"] == "healthy", f"{dep_name} dependency is not healthy"
        assert "response_time_ms" in dep_status
        assert isinstance(dep_status["response_time_ms"], int)

@pytest.mark.usefixtures("docker_services")
def test_register_endpoint():
    """Tests the /auth/register endpoint and validates the response schema."""
    user_email = f"testuser_{uuid4()}@example.com"
    response = requests.post(
        "http://localhost:8000/auth/register",
        json={"email": user_email, "password": "SecurePassword123!", "first_name": "New", "last_name": "User"}
    )
    assert response.status_code == 201
    data = response.json()
    
    assert data["email"] == user_email
    assert data["first_name"] == "New"
    assert data["last_name"] == "User"
    assert validate_user_id(data["id"])
    assert data["is_active"] is True
    assert data["is_verified"] is False
    assert validate_iso_timestamp(data["created_at"])
    assert validate_iso_timestamp(data["updated_at"])

@pytest.mark.usefixtures("docker_services")
def test_login_and_logout(auth_token):
    """Tests the /auth/jwt/logout endpoint."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    
    # Logout
    logout_response = requests.post("http://localhost:8000/auth/jwt/logout", headers=headers)
    assert logout_response.status_code == 204

    # Verify token is no longer valid
    me_response = requests.get("http://localhost:8000/users/me", headers=headers)
    assert me_response.status_code == 401

@pytest.mark.usefixtures("docker_services")
def test_get_and_update_me(auth_token):
    """Tests the GET and PATCH /users/me endpoints."""
    headers = {"Authorization": f"Bearer {auth_token}"}

    # Get current user
    get_response = requests.get("http://localhost:8000/users/me", headers=headers)
    assert get_response.status_code == 200
    original_user = get_response.json()
    assert original_user["first_name"] == "Test"
    assert original_user["last_name"] == "User"

    # Update user
    update_payload = {"first_name": "Jane", "last_name": "Doe"}
    patch_response = requests.patch("http://localhost:8000/users/me", headers=headers, json=update_payload)
    assert patch_response.status_code == 200
    updated_user = patch_response.json()
    assert updated_user["first_name"] == "Jane"
    assert updated_user["last_name"] == "Doe"
    assert updated_user["email"] == original_user["email"]

@pytest.mark.usefixtures("docker_services")
def test_upload_and_status_endpoints(auth_token):
    """Tests the /v1/upload and /v1/upload/status endpoints with full schema validation."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    sample_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'docs', 'sample-avro-files', 'StepsRecord_1758407386729.avro'))
    
    with open(sample_file_path, "rb") as f:
        files = {"file": ("StepsRecord_1758407386729.avro", f.read(), "application/avro")}

    # Upload file
    upload_response = requests.post("http://localhost:8000/v1/upload", headers=headers, files=files)
    assert upload_response.status_code == 202
    upload_data = upload_response.json()
    
    # Validate UploadResponse schema
    assert upload_data["status"] == "accepted"
    assert validate_uuid(upload_data["correlation_id"])
    assert "object_key" in upload_data
    assert upload_data["record_type"] == "AvroStepsRecord"
    assert isinstance(upload_data["record_count"], int)
    assert isinstance(upload_data["file_size_bytes"], int)
    assert validate_iso_timestamp(upload_data["upload_timestamp"])
    assert upload_data["processing_status"] == "queued"

    # Check upload status
    correlation_id = upload_data["correlation_id"]
    
    # Poll for status change
    for _ in range(10): # Poll for up to 10 seconds
        status_response = requests.get(f"http://localhost:8000/v1/upload/status/{correlation_id}", headers=headers)
        if status_response.status_code == 200 and status_response.json()["status"] != "queued":
            break
        time.sleep(1)
        
    assert status_response.status_code == 200
    status_data = status_response.json()
    
    # Validate UploadStatusResponse schema
    assert status_data["correlation_id"] == correlation_id
    assert status_data["status"] in ["processing", "completed", "failed", "quarantined"]
    assert validate_iso_timestamp(status_data["upload_timestamp"])
    assert status_data["object_key"] == upload_data["object_key"]
    assert status_data["record_type"] == "AvroStepsRecord"
    assert status_data["record_count"] == upload_data["record_count"]

@pytest.mark.usefixtures("docker_services")
def test_upload_history_endpoint(auth_token):
    """Tests the /v1/upload/history endpoint with schema and pagination validation."""
    headers = {"Authorization": f"Bearer {auth_token}"}

    # Perform an upload first to ensure history is not empty
    sample_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'docs', 'sample-avro-files', 'HeartRateRecord_1758407386729.avro'))
    with open(sample_file_path, "rb") as f:
        files = {"file": ("HeartRateRecord_1758407386729.avro", f.read(), "application/avro")}
    upload_response = requests.post("http://localhost:8000/v1/upload", headers=headers, files=files)
    assert upload_response.status_code == 202

    # Get history
    history_response = requests.get("http://localhost:8000/v1/upload/history?limit=1", headers=headers)
    assert history_response.status_code == 200
    history_data = history_response.json()

    # Validate pagination object
    pagination = history_data["pagination"]
    assert "total" in pagination
    assert pagination["limit"] == 1
    assert pagination["offset"] == 0
    assert "has_more" in pagination

    # Validate uploads list and its items
    assert "uploads" in history_data
    assert len(history_data["uploads"]) > 0
    
    first_upload = history_data["uploads"][0]
    assert validate_uuid(first_upload["correlation_id"])
    assert first_upload["status"] in ["queued", "processing", "completed", "failed", "quarantined"]
    assert validate_iso_timestamp(first_upload["upload_timestamp"])
    assert "object_key" in first_upload
    assert first_upload["record_type"] == "AvroHeartRateRecord"
