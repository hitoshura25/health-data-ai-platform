import sys
import os
from dotenv import load_dotenv

# Load environment variables from .env file
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)

# Add the service root directory to the Python path to allow imports from 'app'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
