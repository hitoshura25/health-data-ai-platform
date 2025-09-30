import os
import subprocess
import pytest
import requests
import time

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

@pytest.mark.usefixtures("docker_services")
def test_health_live_endpoint():
    """Tests that the /health/live endpoint is responding."""
    response = requests.get("http://localhost:8000/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "Health Data API"
    assert data["version"] == "1.0.0"
