import sys
import os
import pytest
from dotenv import load_dotenv

# Load environment variables from .env file
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)

# Add the service root directory to the Python path to allow imports from 'app'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.fixture(scope="function", autouse=True)
def setup_test_environment(monkeypatch):
    """
    Set up isolated test environment
    """
    test_env_vars = {}

    for key, value in test_env_vars.items():
        monkeypatch.setenv(key, value)
        