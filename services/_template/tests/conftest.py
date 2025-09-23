"""
Test Configuration Template

Pytest fixtures and configuration for service tests.
"""

import asyncio
import pytest
import os
from typing import Generator, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

# Testing frameworks
from httpx import AsyncClient
from fastapi.testclient import TestClient

# Your service imports
from app.main import app  # For FastAPI services
from app.config import Settings


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings() -> Settings:
    """Test configuration settings."""
    return Settings(
        environment="test",
        log_level="DEBUG",
        database_url="sqlite:///:memory:",  # In-memory test database
        redis_url="redis://localhost:6379/15",  # Test Redis database
        secret_key="test-secret-key",
        jwt_secret="test-jwt-secret",
        # Override other settings for testing
        external_api_timeout=5,
        max_retries=1,
        rate_limit_requests=1000,  # Higher limits for tests
    )


@pytest.fixture
def test_client(test_settings: Settings) -> TestClient:
    """Test client for FastAPI application."""
    # Override settings for testing
    app.dependency_overrides[Settings] = lambda: test_settings

    with TestClient(app) as client:
        yield client

    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture
async def async_test_client(test_settings: Settings) -> AsyncGenerator[AsyncClient, None]:
    """Async test client for FastAPI application."""
    # Override settings for testing
    app.dependency_overrides[Settings] = lambda: test_settings

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture
def mock_database():
    """Mock database connection."""
    mock_db = MagicMock()
    # Add common database operations
    mock_db.execute = AsyncMock()
    mock_db.fetch = AsyncMock(return_value=[])
    mock_db.fetchrow = AsyncMock(return_value=None)
    return mock_db


@pytest.fixture
def mock_message_queue():
    """Mock message queue client."""
    mock_queue = MagicMock()
    mock_queue.publish = AsyncMock()
    mock_queue.consume = AsyncMock()
    mock_queue.ack = AsyncMock()
    mock_queue.nack = AsyncMock()
    return mock_queue


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()
    mock_redis.delete = AsyncMock()
    mock_redis.exists = AsyncMock(return_value=False)
    return mock_redis


@pytest.fixture
def mock_storage():
    """Mock storage client (MinIO/S3)."""
    mock_storage = MagicMock()
    mock_storage.put_object = AsyncMock()
    mock_storage.get_object = AsyncMock()
    mock_storage.remove_object = AsyncMock()
    mock_storage.list_objects = AsyncMock(return_value=[])
    return mock_storage


@pytest.fixture
def mock_ml_model():
    """Mock ML model for testing."""
    mock_model = MagicMock()
    mock_model.predict = MagicMock(return_value={"prediction": "test", "confidence": 0.95})
    mock_model.load = MagicMock()
    return mock_model


@pytest.fixture
def sample_health_data():
    """Sample health data for testing."""
    return {
        "blood_glucose": {
            "value": 120.5,
            "unit": "mg/dL",
            "timestamp": "2024-01-23T10:30:00Z",
            "meal_context": "before_meal",
        },
        "heart_rate": {
            "value": 72,
            "unit": "bpm",
            "timestamp": "2024-01-23T10:30:00Z",
        },
        "sleep_session": {
            "start_time": "2024-01-22T22:00:00Z",
            "end_time": "2024-01-23T06:00:00Z",
            "duration_minutes": 480,
            "stages": [
                {"stage": "awake", "duration_minutes": 30},
                {"stage": "light", "duration_minutes": 200},
                {"stage": "deep", "duration_minutes": 180},
                {"stage": "rem", "duration_minutes": 70},
            ],
        },
    }


@pytest.fixture
def sample_task_request():
    """Sample task request for testing."""
    return {
        "task_type": "example_task",
        "input_data": {"test": "data"},
        "priority": 5,
        "timeout_seconds": 300,
    }


@pytest.fixture
def sample_processing_message():
    """Sample processing message for testing."""
    from shared.types import HealthDataProcessingMessage

    return HealthDataProcessingMessage(
        id="test-message-123",
        user_id="test-user",
        record_type="blood_glucose",
        file_path="/test/data.avro",
        processing_step="validation",
        created_at="2024-01-23T10:30:00Z",
    )


# Environment setup
@pytest.fixture(autouse=True)
def setup_test_environment():
    """Setup test environment variables."""
    # Set test environment variables
    os.environ["ENVIRONMENT"] = "test"
    os.environ["LOG_LEVEL"] = "DEBUG"

    yield

    # Cleanup
    test_vars = ["ENVIRONMENT", "LOG_LEVEL"]
    for var in test_vars:
        if var in os.environ:
            del os.environ[var]


# Database fixtures (if using a real database for integration tests)
@pytest.fixture(scope="session")
async def test_database():
    """Setup test database for integration tests."""
    # Create test database
    # Run migrations
    # Setup test data

    yield  # Database is ready for tests

    # Cleanup
    # Drop test database


# Async test utilities
@pytest.fixture
def anyio_backend():
    """Specify the async backend for anyio pytest plugin."""
    return "asyncio"


# Custom markers for different test types
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "slow: Slow tests")
    config.addinivalue_line("markers", "api: API tests")
    config.addinivalue_line("markers", "worker: Background worker tests")
    config.addinivalue_line("markers", "ml: Machine learning tests")


# Test data factories (if using factory_boy)
# import factory
# from factory import LazyAttribute, SubFactory

# class TaskFactory(factory.Factory):
#     class Meta:
#         model = TaskRequest
#
#     task_type = "example_task"
#     input_data = {"test": "data"}
#     priority = 5