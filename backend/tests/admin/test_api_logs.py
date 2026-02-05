"""API integration tests for audit log endpoints."""

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


class TestAuditLogEndpoints:
    """Test audit log endpoints."""

    def test_get_logs_authenticated(self, client, auth_headers, setup_test_db):
        """Test getting logs when authenticated."""
        response = client.get(
            "/api/admin/logs",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data

    def test_get_logs_unauthenticated(self, client, setup_test_db):
        """Test getting logs without authentication."""
        response = client.get("/api/admin/logs")
        assert response.status_code == 401

    def test_login_creates_audit_log(self, client, setup_test_db):
        """Test that login creates an audit log entry."""
        # Login
        login_response = client.post(
            "/api/admin/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_response.json()["access_token"]

        # Check logs
        response = client.get(
            "/api/admin/logs",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = response.json()

        # Should have at least one login entry
        login_entries = [
            item for item in data["items"] if item["action"] == "login"
        ]
        assert len(login_entries) >= 1

    def test_filter_logs_by_action(self, client, auth_headers, setup_test_db):
        """Test filtering logs by action."""
        response = client.get(
            "/api/admin/logs?action=login",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["action"] == "login"

    def test_filter_logs_by_username(self, client, auth_headers, setup_test_db):
        """Test filtering logs by username."""
        response = client.get(
            "/api/admin/logs?username=admin",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["username"] == "admin"

    def test_pagination(self, client, auth_headers, setup_test_db):
        """Test logs pagination."""
        response = client.get(
            "/api/admin/logs?page=1&page_size=5",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 5
        assert len(data["items"]) <= 5

    def test_get_recent_logs(self, client, auth_headers, setup_test_db):
        """Test getting recent logs."""
        response = client.get(
            "/api/admin/logs/recent",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 10  # Default limit


class TestAuditLogContent:
    """Test audit log content."""

    def test_config_update_creates_log(self, client, auth_headers, setup_test_db):
        """Test that config update creates an audit log."""
        # Update config
        client.put(
            "/api/admin/config/general/test_key",
            headers=auth_headers,
            json={"value": "test_value", "encrypted": False},
        )

        # Check logs
        response = client.get(
            "/api/admin/logs?action=config_update",
            headers=auth_headers,
        )
        data = response.json()

        # Should have config_update entry
        config_entries = [
            item for item in data["items"] if item["action"] == "config_update"
        ]
        assert len(config_entries) >= 1
        # Target should include the key
        assert any("test_key" in (e.get("target") or "") for e in config_entries)

    def test_failed_login_creates_log(self, client, setup_test_db):
        """Test that failed login creates an audit log."""
        # Failed login
        client.post(
            "/api/admin/auth/login",
            json={"username": "admin", "password": "wrongpassword"},
        )

        # Successful login to access logs
        login_response = client.post(
            "/api/admin/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_response.json()["access_token"]

        # Check logs
        response = client.get(
            "/api/admin/logs?action=login_failed",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = response.json()

        # Should have login_failed entry
        failed_entries = [
            item for item in data["items"] if item["action"] == "login_failed"
        ]
        assert len(failed_entries) >= 1
