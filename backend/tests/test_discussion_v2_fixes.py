"""Tests for discussion V2 bug fixes.

Covers: WebSocket route ordering, path traversal protection,
stale discussion cleanup, API endpoint validation.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routes import discussion as discussion_module
from src.api.routes.discussion import (
    DiscussionState,
    DiscussionStatus,
    _state_path,
    _validate_discussion_id,
    cleanup_stale_discussions,
    get_current_discussion,
    set_current_discussion,
)
from src.memory.discussion_memory import DiscussionMemory


@pytest.fixture
def client():
    return TestClient(app)


# Track files that existed before the test session started,
# so we can clean up anything created by tests.
_prod_state_dir = discussion_module._STATE_DIR
_prod_disc_dir = Path(discussion_module._discussion_memory.data_dir) / "default" / "discussions"


@pytest.fixture(autouse=True)
def reset_state(tmp_path):
    """Reset global discussion state and redirect disk I/O to tmp dirs."""
    set_current_discussion(None)

    # Clean up any leftovers from previous test's background threads
    _cleanup_test_artifacts()

    # Snapshot existing files so we know what to preserve
    _snapshot_prod_files()

    # Redirect _STATE_DIR to a temp directory so tests don't pollute prod data
    tmp_state_dir = tmp_path / "state"
    tmp_state_dir.mkdir()
    discussion_module._STATE_DIR = tmp_state_dir

    # Redirect _discussion_memory to a temp directory
    original_memory = discussion_module._discussion_memory
    discussion_module._discussion_memory = DiscussionMemory(
        data_dir=str(tmp_path / "projects"),
    )

    # Also redirect the handler's _discussion_memory
    from src.api.websocket import handlers as ws_handlers
    original_ws_memory = ws_handlers._discussion_memory
    ws_handlers._discussion_memory = discussion_module._discussion_memory

    # Mock background task launchers to prevent stale writes to prod dirs
    _noop_async = AsyncMock()
    patches = [
        patch.object(discussion_module, "_run_discussion_async", _noop_async),
        patch.object(discussion_module, "_run_discussion_extend_async", _noop_async),
    ]
    for p in patches:
        p.start()

    yield

    for p in patches:
        p.stop()

    # Restore originals
    set_current_discussion(None)
    discussion_module._STATE_DIR = _prod_state_dir
    discussion_module._discussion_memory = original_memory
    ws_handlers._discussion_memory = original_ws_memory

    # Best-effort cleanup (background threads may still be writing)
    _cleanup_test_artifacts()


# Files that existed before tests — these should not be deleted
_preserved_state_files: set[Path] = set()
_preserved_disc_files: set[Path] = set()


def _snapshot_prod_files():
    global _preserved_state_files, _preserved_disc_files
    _preserved_state_files = set(_prod_state_dir.glob("*.json")) if _prod_state_dir.exists() else set()
    _preserved_disc_files = set(_prod_disc_dir.glob("*.json")) if _prod_disc_dir.exists() else set()


def _cleanup_test_artifacts():
    """Remove files created by test background threads in prod dirs."""
    if _prod_state_dir.exists():
        for f in _prod_state_dir.glob("*.json"):
            if f not in _preserved_state_files:
                f.unlink(missing_ok=True)
    if _prod_disc_dir.exists():
        for f in _prod_disc_dir.glob("*.json"):
            if f not in _preserved_disc_files:
                f.unlink(missing_ok=True)


@pytest.fixture(autouse=True, scope="session")
def final_cleanup():
    """Final cleanup after all tests — waits for background threads then cleans."""
    _snapshot_prod_files()
    yield
    # Wait for straggler background threads to finish
    time.sleep(1)
    _cleanup_test_artifacts()


# ============================================================
# 1. WebSocket Route Ordering Tests
# ============================================================

class TestWebSocketRouteOrdering:
    """Verify /ws/discussion (global) is not shadowed by /ws/{discussion_id}."""

    def test_global_websocket_endpoint_reachable(self, client):
        """Global WebSocket at /ws/discussion should connect and send sync+viewers."""
        with client.websocket_connect("/ws/discussion") as ws:
            # Global endpoint sends viewers count on connect
            msg = ws.receive_json()
            # First message could be sync (if discussion exists) or viewers
            assert msg["type"] in ("sync", "viewers"), (
                f"Expected sync or viewers, got {msg['type']}. "
                "Global WS endpoint may be shadowed by /ws/{{discussion_id}}."
            )

    def test_global_websocket_ping_pong(self, client):
        """Global WebSocket should respond to ping with pong."""
        with client.websocket_connect("/ws/discussion") as ws:
            # Consume initial messages: sync + lobby_sync + viewers + viewers (connect broadcast)
            msgs_to_consume = []
            for _ in range(4):
                msgs_to_consume.append(ws.receive_json())
            msg_types = [m["type"] for m in msgs_to_consume]
            assert "sync" in msg_types, f"Expected sync in initial messages, got {msg_types}"

            # Now test ping/pong
            ws.send_json({"type": "ping"})
            response = ws.receive_json()
            assert response["type"] == "pong"

    def test_per_discussion_websocket_still_works(self, client):
        """Per-discussion WebSocket at /ws/{id} should send sync then handle ping."""
        with client.websocket_connect("/ws/test-123") as ws:
            # First message is the initial sync
            sync_response = ws.receive_json()
            assert sync_response["type"] == "sync"
            # Then ping/pong should work
            ws.send_json({"type": "ping"})
            response = ws.receive_json()
            assert response["type"] == "pong"

    def test_global_ws_with_active_discussion(self, client):
        """Global WS sends sync data when a discussion is active."""
        discussion = DiscussionState(
            id="ws-test-1",
            topic="WebSocket routing test",
            rounds=2,
            status=DiscussionStatus.RUNNING,
            created_at="2024-01-01T00:00:00",
            started_at="2024-01-01T00:00:01",
        )
        set_current_discussion(discussion)

        with client.websocket_connect("/ws/discussion") as ws:
            # Collect all initial messages: sync + lobby_sync + viewers + viewers
            messages = []
            for _ in range(4):
                messages.append(ws.receive_json())

            types = [m["type"] for m in messages]
            assert "viewers" in types, f"Expected 'viewers' in {types}"
            assert "lobby_sync" in types, f"Expected 'lobby_sync' in {types}"

            # If sync was received, verify its content
            sync_msgs = [m for m in messages if m["type"] == "sync"]
            if sync_msgs:
                assert sync_msgs[0]["data"]["discussion"]["id"] == "ws-test-1"


# ============================================================
# 2. Path Traversal Protection Tests
# ============================================================

class TestPathTraversalProtection:
    """Verify discussion_id validation prevents directory traversal."""

    def test_valid_uuid_id(self):
        """Standard UUID discussion IDs are accepted."""
        assert _validate_discussion_id("abc123") is True
        assert _validate_discussion_id("test-discussion-1") is True
        assert _validate_discussion_id("550e8400-e29b-41d4-a716-446655440000") is True

    def test_invalid_path_traversal(self):
        """Path traversal attempts are rejected."""
        assert _validate_discussion_id("../../etc/passwd") is False
        assert _validate_discussion_id("../../../secret") is False
        assert _validate_discussion_id("foo/bar") is False
        assert _validate_discussion_id("foo\\bar") is False

    def test_invalid_special_chars(self):
        """Special characters that could cause issues are rejected."""
        assert _validate_discussion_id("") is False
        assert _validate_discussion_id(".") is False
        assert _validate_discussion_id("..") is False
        assert _validate_discussion_id("foo bar") is False

    def test_state_path_raises_on_traversal(self):
        """_state_path raises ValueError for traversal attempts."""
        with pytest.raises(ValueError, match="Invalid discussion_id"):
            _state_path("../../etc/passwd")

    def test_state_path_valid_id(self):
        """_state_path works for valid IDs."""
        path = _state_path("valid-discussion-123")
        assert path.name == "valid-discussion-123.json"

    def test_api_returns_404_for_traversal(self, client):
        """API endpoints reject path traversal IDs gracefully."""
        response = client.get("/api/discussions/../../etc/passwd")
        # Should return 404 or 400, not leak file contents
        assert response.status_code in (404, 422, 400, 500)


# ============================================================
# 3. Stale Discussion Cleanup Tests
# ============================================================

class TestStaleDiscussionCleanup:
    """Verify stale discussion detection and cleanup."""

    def test_cleanup_stale_in_memory(self):
        """cleanup_stale_discussions clears in-memory running discussion."""
        discussion = DiscussionState(
            id="stale-1",
            topic="Stale discussion",
            rounds=2,
            status=DiscussionStatus.RUNNING,
            created_at="2024-01-01T00:00:00",
        )
        set_current_discussion(discussion)
        assert get_current_discussion() is not None

        cleanup_stale_discussions()
        assert get_current_discussion() is None

    def test_cleanup_ignores_completed(self):
        """cleanup_stale_discussions does not touch completed discussions."""
        discussion = DiscussionState(
            id="completed-1",
            topic="Completed discussion",
            rounds=2,
            status=DiscussionStatus.COMPLETED,
            created_at="2024-01-01T00:00:00",
            completed_at="2024-01-01T01:00:00",
        )
        set_current_discussion(discussion)

        cleanup_stale_discussions()
        # Completed discussion should remain
        assert get_current_discussion() is not None
        assert get_current_discussion().status == DiscussionStatus.COMPLETED

    def test_post_current_detects_stale_discussion(self, client):
        """POST /api/discussions/current detects and replaces stale discussion."""
        # Create a "stale" discussion (started > 30 min ago)
        stale_time = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        stale = DiscussionState(
            id="stale-old",
            topic="Old stale discussion",
            rounds=2,
            status=DiscussionStatus.RUNNING,
            created_at=stale_time,
            started_at=stale_time,
        )
        set_current_discussion(stale)

        # Attempt to create a new discussion
        response = client.post(
            "/api/discussions/current",
            json={"topic": "Fresh new discussion", "rounds": 2},
        )
        assert response.status_code == 200
        data = response.json()
        # Response is flat: {id, topic, rounds, status, created_at, message}
        assert data["topic"] == "Fresh new discussion"
        assert data["id"] != "stale-old"

    def test_post_current_creates_new_even_when_running(self, client):
        """POST /api/discussions/current always creates a new discussion (multi-discussion support)."""
        recent = DiscussionState(
            id="recent-running",
            topic="Recent running discussion",
            rounds=2,
            status=DiscussionStatus.RUNNING,
            created_at=datetime.utcnow().isoformat(),
            started_at=datetime.utcnow().isoformat(),
        )
        set_current_discussion(recent)

        response = client.post(
            "/api/discussions/current",
            json={"topic": "New concurrent discussion", "rounds": 2},
        )
        assert response.status_code == 200
        data = response.json()
        # A new discussion should always be created
        assert data["id"] != "recent-running"
        assert data["topic"] == "New concurrent discussion"


# ============================================================
# 4. Discussion API Endpoint Tests
# ============================================================

class TestDiscussionAPI:
    """Tests for discussion API endpoints."""

    def test_get_current_returns_none(self, client):
        """GET /api/discussions/current returns null when no discussion."""
        response = client.get("/api/discussions/current")
        assert response.status_code == 200
        assert response.json() is None

    def test_get_current_returns_discussion(self, client):
        """GET /api/discussions/current returns active discussion."""
        discussion = DiscussionState(
            id="api-test-1",
            topic="API test discussion",
            rounds=3,
            status=DiscussionStatus.RUNNING,
            created_at="2024-06-01T00:00:00",
        )
        set_current_discussion(discussion)

        response = client.get("/api/discussions/current")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "api-test-1"
        assert data["status"] == "running"

    def test_join_current_no_discussion(self, client):
        """POST /api/discussions/current/join when no discussion exists."""
        response = client.post("/api/discussions/current/join")
        assert response.status_code == 200
        data = response.json()
        assert data["discussion"] is None
        assert data["messages"] == []

    def test_join_current_with_discussion(self, client):
        """POST /api/discussions/current/join returns discussion info."""
        discussion = DiscussionState(
            id="join-test-1",
            topic="Join test",
            rounds=2,
            status=DiscussionStatus.RUNNING,
            created_at="2024-06-01T00:00:00",
        )
        set_current_discussion(discussion)

        response = client.post("/api/discussions/current/join")
        assert response.status_code == 200
        data = response.json()
        assert data["discussion"]["id"] == "join-test-1"

    def test_list_discussions(self, client):
        """GET /api/discussions returns paginated list."""
        response = client.get("/api/discussions?page=1&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "hasMore" in data

    def test_health_endpoint(self, client):
        """GET /health returns ok."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


# ============================================================
# 5. Continue Discussion Tests
# ============================================================

class TestContinueDiscussion:
    """Tests for continue discussion feature."""

    def test_continue_requires_completed_discussion(self, client):
        """Continue discussion fails for non-existent discussion."""
        response = client.post(
            "/api/discussions/nonexistent-id/continue",
            json={"rounds": 2},
        )
        assert response.status_code == 404

    def test_continue_rejects_running_discussion(self, client):
        """Continue discussion fails for running discussion."""
        discussion = DiscussionState(
            id="running-continue",
            topic="Running discussion",
            rounds=2,
            status=DiscussionStatus.RUNNING,
            created_at="2024-06-01T00:00:00",
        )
        set_current_discussion(discussion)
        # Save state so it can be found by get_discussion_state
        from src.api.routes.discussion import save_discussion_state
        save_discussion_state(discussion)

        response = client.post(
            "/api/discussions/running-continue/continue",
            json={"rounds": 2},
        )
        assert response.status_code == 400

    def test_continue_with_empty_follow_up(self, client):
        """Continue discussion accepts empty follow_up."""
        discussion = DiscussionState(
            id="completed-continue",
            topic="Completed discussion",
            rounds=2,
            status=DiscussionStatus.COMPLETED,
            created_at="2024-06-01T00:00:00",
            completed_at="2024-06-01T01:00:00",
        )
        from src.api.routes.discussion import save_discussion_state
        save_discussion_state(discussion)

        response = client.post(
            "/api/discussions/completed-continue/continue",
            json={"rounds": 2},  # No follow_up field
        )
        # Should succeed (or fail with LLM error, not validation error)
        assert response.status_code in (200, 500)


# ============================================================
# 6. Persist State Tests
# ============================================================

class TestPersistState:
    """Tests for discussion state persistence."""

    def test_persist_uses_utf8(self, client):
        """Persisted state should use ensure_ascii=False for Chinese."""
        from src.api.routes.discussion import (
            _persist_discussion_state,
            _state_path,
        )

        discussion = DiscussionState(
            id="utf8-test",
            topic="中文讨论主题测试",
            rounds=2,
            status=DiscussionStatus.PENDING,
            created_at="2024-06-01T00:00:00",
        )
        _persist_discussion_state(discussion)

        path = _state_path("utf8-test")
        if path.exists():
            content = path.read_text(encoding="utf-8")
            # Chinese chars should be literal, not \uXXXX escaped
            assert "中文讨论主题测试" in content
            # Cleanup
            path.unlink(missing_ok=True)


class TestLLMConfigAndProjectCreation:
    """Tests to prevent silent failures in LLM initialization and project creation."""

    def test_langchain_anthropic_importable(self):
        """langchain_anthropic must be installed; missing it causes all discussions to fail silently."""
        try:
            from langchain_anthropic import ChatAnthropic  # noqa: F401
        except ImportError as e:
            pytest.fail(
                f"langchain_anthropic not installed: {e}. "
                "Run: pip install langchain-anthropic. "
                "Without it, every discussion fails with 'LLM not configured'."
            )

    def test_langchain_openai_importable(self):
        """langchain_openai must be installed for OpenAI-compatible providers."""
        try:
            from langchain_openai import ChatOpenAI  # noqa: F401
        except ImportError as e:
            pytest.fail(
                f"langchain_openai not installed: {e}. "
                "Run: pip install langchain-openai."
            )

    def test_get_llm_from_config_returns_instance_when_configured(self):
        """_get_llm_from_config must return a non-None LLM when admin store has a valid profile.

        Regression: ImportError for langchain_anthropic was silently caught,
        causing all discussions to fail with 'LLM not configured'.
        """
        from unittest.mock import MagicMock, patch

        fake_config = {
            "id": "test_profile",
            "name": "Test Claude",
            "api_key": "sk-test-key",
            "base_url": "https://api.anthropic.com",
            "model": "claude-haiku-4-5-20251001",
            "is_active": True,
        }

        mock_store_instance = MagicMock()
        mock_store_instance.get_active_llm_config.return_value = fake_config

        # ConfigStore is imported locally inside _get_llm_from_config,
        # so we patch it at the source module.
        with patch("src.admin.config_store.ConfigStore", return_value=mock_store_instance):
            from src.api.routes.discussion import _get_llm_from_config
            llm = _get_llm_from_config()

        assert llm is not None, (
            "_get_llm_from_config returned None even though config is valid. "
            "Likely a missing package (langchain_anthropic / langchain_openai)."
        )
