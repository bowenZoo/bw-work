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
