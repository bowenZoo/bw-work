"""API endpoint tests."""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    def test_health_returns_ok(self, client):
        """Health endpoint returns ok status."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestDiscussionEndpoints:
    """Tests for discussion API endpoints."""

    def test_create_discussion(self, client):
        """Creating a discussion returns proper response."""
        response = client.post(
            "/api/discussions",
            json={"topic": "测试话题", "rounds": 2},
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["topic"] == "测试话题"
        assert data["rounds"] == 2
        assert data["status"] == "pending"

    def test_create_discussion_default_rounds(self, client):
        """Creating a discussion with default rounds."""
        response = client.post(
            "/api/discussions",
            json={"topic": "测试话题"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["rounds"] == 3  # Default

    def test_create_discussion_invalid_topic(self, client):
        """Creating a discussion with empty topic fails."""
        response = client.post(
            "/api/discussions",
            json={"topic": "", "rounds": 2},
        )
        assert response.status_code == 422  # Validation error

    def test_create_discussion_invalid_rounds(self, client):
        """Creating a discussion with invalid rounds fails."""
        response = client.post(
            "/api/discussions",
            json={"topic": "测试", "rounds": 0},
        )
        assert response.status_code == 422

        response = client.post(
            "/api/discussions",
            json={"topic": "测试", "rounds": 100},
        )
        assert response.status_code == 422

    def test_get_discussion(self, client):
        """Getting a discussion returns its status."""
        # First create a discussion
        create_response = client.post(
            "/api/discussions",
            json={"topic": "测试话题"},
        )
        discussion_id = create_response.json()["id"]

        # Then get it
        response = client.get(f"/api/discussions/{discussion_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == discussion_id
        assert data["topic"] == "测试话题"
        assert data["status"] == "pending"

    def test_get_nonexistent_discussion(self, client):
        """Getting a non-existent discussion returns 404."""
        response = client.get("/api/discussions/nonexistent-id")
        assert response.status_code == 404

    def test_start_discussion(self, client):
        """Starting a discussion changes its status."""
        # Create a discussion
        create_response = client.post(
            "/api/discussions",
            json={"topic": "测试话题"},
        )
        discussion_id = create_response.json()["id"]

        # Start it
        response = client.post(f"/api/discussions/{discussion_id}/start")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == discussion_id
        assert data["status"] == "running"

    def test_start_nonexistent_discussion(self, client):
        """Starting a non-existent discussion returns 404."""
        response = client.post("/api/discussions/nonexistent-id/start")
        assert response.status_code == 404

    def test_cannot_start_running_discussion(self, client):
        """Cannot start an already running discussion."""
        # Create and start a discussion
        create_response = client.post(
            "/api/discussions",
            json={"topic": "测试话题"},
        )
        discussion_id = create_response.json()["id"]
        client.post(f"/api/discussions/{discussion_id}/start")

        # Try to start again
        response = client.post(f"/api/discussions/{discussion_id}/start")
        assert response.status_code == 400


class TestSetCurrentModelEndpoint:
    """Tests for POST /api/config/model/set endpoint."""

    def test_no_auth_header_returns_401(self, client):
        """Missing Authorization header should return 401."""
        response = client.post(
            "/api/config/model/set",
            json={"model": "claude-sonnet-4-6"},
        )
        assert response.status_code == 401

    def test_model_not_in_whitelist_returns_400(self, client):
        """A model name not in the allowed list should return 400."""
        from unittest.mock import patch, MagicMock

        # Patch verify_access_token to simulate a valid authenticated user
        with patch("src.admin.auth.verify_token", return_value={"sub": "admin", "type": "access"}):
            # We also need to patch the import inside the route handler
            with patch.dict("sys.modules", {"src.admin.auth": MagicMock(
                verify_access_token=lambda token: {"sub": "admin", "type": "access"},
                verify_token=lambda token: {"sub": "admin", "type": "access"},
            )}):
                # Rebuild the import in the route by patching at the module level
                import src.admin.auth as auth_module
                original = getattr(auth_module, "verify_access_token", None)
                auth_module.verify_access_token = lambda token: {"sub": "admin", "type": "access"}
                try:
                    response = client.post(
                        "/api/config/model/set",
                        headers={"Authorization": "Bearer fake-valid-token"},
                        json={"model": "gpt-4"},
                    )
                    assert response.status_code == 400
                    assert "not in the allowed list" in response.json().get("detail", "")
                finally:
                    if original is not None:
                        auth_module.verify_access_token = original
                    else:
                        if hasattr(auth_module, "verify_access_token"):
                            delattr(auth_module, "verify_access_token")

    def test_model_in_whitelist_returns_success(self, client):
        """A whitelisted model should be accepted and stored (mocked ConfigStore)."""
        from unittest.mock import patch, MagicMock
        import src.admin.auth as auth_module

        # Add verify_access_token to the auth module for the duration of the test
        auth_module.verify_access_token = lambda token: {"sub": "admin", "type": "access"}

        mock_active_config = {
            "id": "profile-1",
            "name": "Default",
            "base_url": "https://api.anthropic.com",
            "model": "claude-sonnet-4-6",
        }
        mock_store = MagicMock()
        mock_store.get_active_llm_config.return_value = mock_active_config
        mock_store.save_llm_profile.return_value = None

        try:
            with patch("src.admin.config_store.ConfigStore", return_value=mock_store):
                with patch("src.config.settings.reload_config"):
                    response = client.post(
                        "/api/config/model/set",
                        headers={"Authorization": "Bearer fake-valid-token"},
                        json={"model": "claude-haiku-4-5"},
                    )
                    assert response.status_code == 200
                    data = response.json()
                    assert data["model"] == "claude-haiku-4-5"
                    assert "profile_id" in data
        finally:
            if hasattr(auth_module, "verify_access_token"):
                delattr(auth_module, "verify_access_token")
