"""API integration tests for configuration endpoints."""

import os
import pytest
import tempfile
from fastapi.testclient import TestClient

from src.api.main import app
from src.admin.database import AdminDatabase
from src.admin.auth import hash_password


@pytest.fixture(autouse=True)
def setup_test_db():
    """Set up test database for each test."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    # Set env var for database path
    os.environ["ADMIN_DB_PATH"] = db_path

    # Reset singleton and initialize
    AdminDatabase.reset_instance()
    db = AdminDatabase(db_path)
    db.init_db()

    # Create test admin user
    db.create_admin_user("admin", hash_password("admin123"))

    yield db

    # Cleanup
    db.close()
    AdminDatabase.reset_instance()
    if "ADMIN_DB_PATH" in os.environ:
        del os.environ["ADMIN_DB_PATH"]
    os.unlink(db_path)


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers(client, setup_test_db):
    """Get authentication headers."""
    response = client.post(
        "/api/admin/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestConfigEndpoints:
    """Test configuration endpoints."""

    def test_get_all_configs_authenticated(self, client, auth_headers, setup_test_db):
        """Test getting all configs when authenticated."""
        response = client.get(
            "/api/admin/config",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_all_configs_unauthenticated(self, client, setup_test_db):
        """Test getting all configs without authentication."""
        response = client.get("/api/admin/config")
        assert response.status_code == 401

    def test_get_config_status(self, client, auth_headers, setup_test_db):
        """Test getting config status."""
        response = client.get(
            "/api/admin/config/status",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "llm_configured" in data
        assert "langfuse_configured" in data
        assert "image_configured" in data

    def test_get_llm_config(self, client, auth_headers, setup_test_db):
        """Test getting LLM config."""
        response = client.get(
            "/api/admin/config/llm",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "configured" in data

    def test_update_config(self, client, auth_headers, setup_test_db):
        """Test updating config."""
        response = client.put(
            "/api/admin/config/llm/openai_model",
            headers=auth_headers,
            json={"value": "gpt-4-turbo", "encrypted": False},
        )
        assert response.status_code == 200

        # Verify update
        get_response = client.get(
            "/api/admin/config/llm",
            headers=auth_headers,
        )
        assert get_response.json()["openai_model"] == "gpt-4-turbo"

    def test_update_encrypted_config(self, client, auth_headers, setup_test_db):
        """Test updating encrypted config."""
        response = client.put(
            "/api/admin/config/llm/openai_api_key",
            headers=auth_headers,
            json={"value": "sk-test123456", "encrypted": True},
        )
        assert response.status_code == 200

        # Verify config shows as configured
        get_response = client.get(
            "/api/admin/config/llm",
            headers=auth_headers,
        )
        data = get_response.json()
        assert data["configured"] is True
        # Value should be masked
        assert "*" in data["openai_api_key"]

    def test_delete_config(self, client, auth_headers, setup_test_db):
        """Test deleting config."""
        # First create a config
        client.put(
            "/api/admin/config/general/test_key",
            headers=auth_headers,
            json={"value": "test_value", "encrypted": False},
        )

        # Delete it
        response = client.delete(
            "/api/admin/config/general/test_key",
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_delete_nonexistent_config(self, client, auth_headers, setup_test_db):
        """Test deleting nonexistent config."""
        response = client.delete(
            "/api/admin/config/general/nonexistent",
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestConfigByCategory:
    """Test getting config by category."""

    def test_get_langfuse_config(self, client, auth_headers, setup_test_db):
        """Test getting Langfuse config."""
        response = client.get(
            "/api/admin/config/langfuse",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        assert "configured" in data

    def test_get_image_config(self, client, auth_headers, setup_test_db):
        """Test getting image config."""
        response = client.get(
            "/api/admin/config/image",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "default_provider" in data
        assert "providers" in data
