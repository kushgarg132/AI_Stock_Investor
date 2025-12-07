import pytest
import os
import sys
from unittest.mock import MagicMock, AsyncMock
from fastapi.testclient import TestClient

# Add project root to sys.path
# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.server import app
from backend.configs.settings import settings
from backend.database import db

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="module")
def mock_settings():
    """Override settings for testing."""
    # settings.GEMINI_API_KEY = "test_gemini_key"
    # settings.NEWS_API_KEY = "test_news_key"
    return settings

@pytest.fixture(scope="module")
def client(mock_settings):
    """FastAPI TestClient."""
    with TestClient(app) as c:
        yield c

@pytest.fixture(scope="function", autouse=True)
def mock_db():
    """Mock Database connections to prevent actual connection attempts."""
    db.client = AsyncMock()
    db.db = AsyncMock()
    db.redis = AsyncMock()
    
    # Mock specific collection methods if needed
    db.db.a_collection = AsyncMock()
    
    yield db
