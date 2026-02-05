"""API integration tests for authentication endpoints."""

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


class TestLoginEndpoint:
    """Test login endpoint."""

    def test_login_success(self, client, setup_test_db):
        """Test successful login."""
        response = client.post(
            "/api/admin/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_login_invalid_username(self, client, setup_test_db):
        """Test login with invalid username."""
        response = client.post(
            "/api/admin/auth/login",
            json={"username": "nonexistent", "password": "password"},
        )
        assert response.status_code == 401

    def test_login_invalid_password(self, client, setup_test_db):
        """Test login with invalid password."""
        response = client.post(
            "/api/admin/auth/login",
            json={"username": "admin", "password": "wrongpassword"},
        )
        assert response.status_code == 401

    def test_login_missing_fields(self, client, setup_test_db):
        """Test login with missing fields."""
        response = client.post(
            "/api/admin/auth/login",
            json={"username": "admin"},
        )
        assert response.status_code == 422


class TestMeEndpoint:
    """Test /me endpoint."""

    def test_me_authenticated(self, client, setup_test_db):
        """Test getting current user info when authenticated."""
        # Login first
        login_response = client.post(
            "/api/admin/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_response.json()["access_token"]

        # Get user info
        response = client.get(
            "/api/admin/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "admin"

    def test_me_unauthenticated(self, client, setup_test_db):
        """Test getting current user info without authentication."""
        response = client.get("/api/admin/auth/me")
        assert response.status_code == 401

    def test_me_invalid_token(self, client, setup_test_db):
        """Test getting current user info with invalid token."""
        response = client.get(
            "/api/admin/auth/me",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 401


class TestRefreshEndpoint:
    """Test refresh token endpoint."""

    def test_refresh_success(self, client, setup_test_db):
        """Test successful token refresh."""
        # Login first
        login_response = client.post(
            "/api/admin/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        refresh_token = login_response.json()["refresh_token"]

        # Refresh
        response = client.post(
            "/api/admin/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_refresh_invalid_token(self, client, setup_test_db):
        """Test refresh with invalid token."""
        response = client.post(
            "/api/admin/auth/refresh",
            json={"refresh_token": "invalid-token"},
        )
        assert response.status_code == 401


class TestLogoutEndpoint:
    """Test logout endpoint."""

    def test_logout_success(self, client, setup_test_db):
        """Test successful logout."""
        # Login first
        login_response = client.post(
            "/api/admin/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        tokens = login_response.json()

        # Logout
        response = client.post(
            "/api/admin/auth/logout",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert response.status_code == 200

        # Refresh token should no longer work
        refresh_response = client.post(
            "/api/admin/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert refresh_response.status_code == 401


class TestSecurityHeaders:
    """Test security headers on admin routes."""

    def test_security_headers_present(self, client, setup_test_db):
        """Test that security headers are present on admin routes."""
        response = client.post(
            "/api/admin/auth/login",
            json={"username": "admin", "password": "admin123"},
        )

        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"
