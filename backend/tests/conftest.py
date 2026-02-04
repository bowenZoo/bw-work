"""Pytest configuration and fixtures."""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_llm():
    """Mock LLM for testing agents without actual API calls.

    This fixture can be extended to provide a mock LLM that returns
    predefined responses for testing purposes.
    """
    # For now, return None which will use the default behavior
    # In a real test setup, this could be a mock object
    return None
