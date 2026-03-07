"""WebSocket tests."""

import json
import time

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.websocket.events import (
    AgentStatus,
    ClientMessageType,
    MessageEvent,
    PongEvent,
    ServerMessageType,
    StatusEvent,
    create_error_event,
    create_message_event,
    create_status_event,
)
from src.api.websocket.manager import ConnectionManager


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def manager():
    """Create a fresh ConnectionManager for testing."""
    return ConnectionManager()


class TestConnectionManager:
    """Tests for the ConnectionManager class."""

    def test_manager_initialization(self, manager):
        """Manager initializes with empty connections."""
        assert manager.connections == {}
        assert manager.get_connection_count() == 0

    def test_get_connection_count_empty(self, manager):
        """Connection count is zero when empty."""
        assert manager.get_connection_count() == 0
        assert manager.get_connection_count("test-discussion") == 0


class _FakeWebSocket:
    """Minimal fake WebSocket for ConnectionManager tests."""

    def __init__(self) -> None:
        self.accepted = False
        self.sent: list[dict] = []
        self.closed = False
        self.close_code: int | None = None
        self.close_reason: str | None = None

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict) -> None:
        self.sent.append(message)

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        self.closed = True
        self.close_code = code
        self.close_reason = reason


class TestBroadcastAndHeartbeat:
    """Tests for ConnectionManager broadcast and heartbeat cleanup."""

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all_clients(self):
        manager = ConnectionManager()
        ws1 = _FakeWebSocket()
        ws2 = _FakeWebSocket()

        await manager.connect(ws1, "discussion-1")
        await manager.connect(ws2, "discussion-1")

        payload = {"type": "message", "data": {"discussion_id": "discussion-1"}}
        await manager.broadcast("discussion-1", payload)

        assert ws1.sent == [payload]
        assert ws2.sent == [payload]

    @pytest.mark.asyncio
    async def test_broadcast_scoped_to_discussion(self):
        manager = ConnectionManager()
        ws1 = _FakeWebSocket()
        ws2 = _FakeWebSocket()

        await manager.connect(ws1, "discussion-1")
        await manager.connect(ws2, "discussion-2")

        payload = {"type": "message", "data": {"discussion_id": "discussion-1"}}
        await manager.broadcast("discussion-1", payload)

        assert ws1.sent == [payload]
        assert ws2.sent == []

    @pytest.mark.asyncio
    async def test_cleanup_stale_connections(self):
        manager = ConnectionManager()
        ws = _FakeWebSocket()

        await manager.connect(ws, "discussion-1")
        manager._last_seen[ws] = time.time() - (manager.HEARTBEAT_TIMEOUT + 1)

        await manager._cleanup_stale()

        assert ws.closed is True
        assert manager.get_connection_count("discussion-1") == 0


class TestWebSocketEvents:
    """Tests for WebSocket event models."""

    def test_create_message_event(self):
        """MessageEvent creation works correctly."""
        event = create_message_event(
            discussion_id="test-123",
            agent_id="system_designer",
            agent_role="System Designer",
            content="Test message content",
        )
        assert event.type == ServerMessageType.MESSAGE
        assert event.data.discussion_id == "test-123"
        assert event.data.agent_id == "system_designer"
        assert event.data.agent_role == "System Designer"
        assert event.data.content == "Test message content"
        assert event.data.timestamp is not None

    def test_create_status_event(self):
        """StatusEvent creation works correctly."""
        event = create_status_event(
            discussion_id="test-123",
            agent_id="number_designer",
            agent_role="Number Designer",
            status=AgentStatus.THINKING,
        )
        assert event.type == ServerMessageType.STATUS
        assert event.data.discussion_id == "test-123"
        assert event.data.agent_id == "number_designer"
        assert event.data.status == AgentStatus.THINKING

    def test_create_error_event(self):
        """ErrorEvent creation works correctly."""
        event = create_error_event(
            discussion_id="test-123",
            content="Something went wrong",
        )
        assert event.type == ServerMessageType.ERROR
        assert event.data.discussion_id == "test-123"
        assert event.data.content == "Something went wrong"

    def test_pong_event(self):
        """PongEvent creation works correctly."""
        event = PongEvent()
        assert event.type == ServerMessageType.PONG
        assert "timestamp" in event.data

    def test_message_event_serialization(self):
        """MessageEvent serializes to dict correctly."""
        event = create_message_event(
            discussion_id="test-123",
            agent_id="player_advocate",
            agent_role="Player Advocate",
            content="Player perspective",
        )
        data = event.to_dict()
        assert data["type"] == "message"
        assert data["data"]["discussion_id"] == "test-123"
        assert data["data"]["agent_id"] == "player_advocate"

    def test_status_event_serialization(self):
        """StatusEvent serializes to dict correctly."""
        event = create_status_event(
            discussion_id="test-123",
            agent_id="system_designer",
            agent_role="System Designer",
            status=AgentStatus.SPEAKING,
        )
        data = event.to_dict()
        assert data["type"] == "status"
        assert data["data"]["status"] == "speaking"


class TestWebSocketEndpoint:
    """Tests for the WebSocket endpoint."""

    def test_websocket_connection(self, client):
        """WebSocket connection can be established."""
        with client.websocket_connect("/ws/test-discussion") as websocket:
            # Connection established successfully
            assert websocket is not None

    def test_websocket_ping_pong(self, client):
        """WebSocket responds to ping with pong."""
        with client.websocket_connect("/ws/test-discussion") as websocket:
            # Consume initial sync message sent upon connection
            websocket.receive_json()
            # Send ping
            websocket.send_json({"type": "ping"})
            # Receive pong
            response = websocket.receive_json()
            assert response["type"] == "pong"
            assert "timestamp" in response["data"]

    def test_websocket_invalid_json(self, client):
        """WebSocket handles invalid JSON gracefully."""
        with client.websocket_connect("/ws/test-discussion") as websocket:
            # Consume initial sync message
            websocket.receive_json()
            # Send invalid JSON
            websocket.send_text("not valid json")
            # Connection should still be alive - send a ping
            websocket.send_json({"type": "ping"})
            response = websocket.receive_json()
            assert response["type"] == "pong"

    def test_websocket_unknown_message_type(self, client):
        """WebSocket handles unknown message types gracefully."""
        with client.websocket_connect("/ws/test-discussion") as websocket:
            # Consume initial sync message
            websocket.receive_json()
            # Send unknown message type
            websocket.send_json({"type": "unknown"})
            # Connection should still be alive - send a ping
            websocket.send_json({"type": "ping"})
            response = websocket.receive_json()
            assert response["type"] == "pong"


class TestMultipleClients:
    """Tests for multiple WebSocket clients."""

    def test_multiple_clients_same_discussion(self, client):
        """Multiple clients can connect to the same discussion."""
        with client.websocket_connect("/ws/test-discussion") as ws1:
            with client.websocket_connect("/ws/test-discussion") as ws2:
                # Both connections established; consume initial sync messages
                ws1.receive_json()
                ws2.receive_json()
                ws1.send_json({"type": "ping"})
                response1 = ws1.receive_json()
                assert response1["type"] == "pong"

                ws2.send_json({"type": "ping"})
                response2 = ws2.receive_json()
                assert response2["type"] == "pong"

    def test_clients_different_discussions(self, client):
        """Clients can connect to different discussions."""
        with client.websocket_connect("/ws/discussion-1") as ws1:
            with client.websocket_connect("/ws/discussion-2") as ws2:
                # Both connections established; consume initial sync messages
                ws1.receive_json()
                ws2.receive_json()
                ws1.send_json({"type": "ping"})
                response1 = ws1.receive_json()
                assert response1["type"] == "pong"

                ws2.send_json({"type": "ping"})
                response2 = ws2.receive_json()
                assert response2["type"] == "pong"


class TestAgentStatus:
    """Tests for AgentStatus enum."""

    def test_agent_status_values(self):
        """AgentStatus has expected values."""
        assert AgentStatus.THINKING == "thinking"
        assert AgentStatus.SPEAKING == "speaking"
        assert AgentStatus.IDLE == "idle"


class TestClientMessageType:
    """Tests for ClientMessageType enum."""

    def test_client_message_type_values(self):
        """ClientMessageType has expected values."""
        assert ClientMessageType.PING == "ping"


class TestServerMessageType:
    """Tests for ServerMessageType enum."""

    def test_server_message_type_values(self):
        """ServerMessageType has expected values."""
        assert ServerMessageType.MESSAGE == "message"
        assert ServerMessageType.STATUS == "status"
        assert ServerMessageType.ERROR == "error"
        assert ServerMessageType.PONG == "pong"
