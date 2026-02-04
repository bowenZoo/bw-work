"""WebSocket connection manager for real-time communication."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import WebSocket

logger = logging.getLogger(__name__)

# Global event loop reference for sync-to-async bridging
_main_loop: asyncio.AbstractEventLoop | None = None


def set_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Set the main event loop reference for sync-to-async bridging.

    Should be called in FastAPI startup event.
    """
    global _main_loop
    _main_loop = loop


def get_event_loop() -> asyncio.AbstractEventLoop | None:
    """Get the main event loop reference."""
    return _main_loop


class ConnectionManager:
    """Manages WebSocket connections grouped by discussion_id.

    Features:
    - Connection grouping by discussion_id
    - Heartbeat timeout detection (30s)
    - Automatic cleanup of stale connections
    - Broadcast to all clients in a discussion
    """

    # Heartbeat configuration
    HEARTBEAT_TIMEOUT = 30.0  # seconds
    SWEEP_INTERVAL = 10.0  # seconds

    def __init__(self) -> None:
        """Initialize the connection manager."""
        # Connections grouped by discussion_id
        self._connections: dict[str, set[WebSocket]] = {}
        # Last seen timestamp for each connection
        self._last_seen: dict[WebSocket, float] = {}
        # Sweep task reference
        self._sweep_task: asyncio.Task[None] | None = None

    @property
    def connections(self) -> dict[str, set[WebSocket]]:
        """Get all active connections grouped by discussion_id."""
        return self._connections

    async def connect(self, websocket: WebSocket, discussion_id: str) -> None:
        """Accept a new WebSocket connection.

        Args:
            websocket: The WebSocket connection to accept.
            discussion_id: The discussion ID to associate with this connection.
        """
        await websocket.accept()

        if discussion_id not in self._connections:
            self._connections[discussion_id] = set()

        self._connections[discussion_id].add(websocket)
        self._last_seen[websocket] = time.time()

        logger.info(
            "WebSocket connected: discussion_id=%s, total_connections=%d",
            discussion_id,
            len(self._connections[discussion_id]),
        )

    def disconnect(self, websocket: WebSocket, discussion_id: str) -> None:
        """Remove a WebSocket connection.

        Args:
            websocket: The WebSocket connection to remove.
            discussion_id: The discussion ID associated with this connection.
        """
        if discussion_id in self._connections:
            self._connections[discussion_id].discard(websocket)

            # Clean up empty discussion groups
            if not self._connections[discussion_id]:
                del self._connections[discussion_id]

        # Remove from last_seen tracking
        self._last_seen.pop(websocket, None)

        logger.info("WebSocket disconnected: discussion_id=%s", discussion_id)

    def update_heartbeat(self, websocket: WebSocket) -> None:
        """Update the last seen timestamp for a connection.

        Args:
            websocket: The WebSocket connection that sent a heartbeat.
        """
        self._last_seen[websocket] = time.time()

    async def broadcast(
        self,
        discussion_id: str,
        message: dict[str, Any],
    ) -> None:
        """Broadcast a message to all clients in a discussion.

        Args:
            discussion_id: The discussion ID to broadcast to.
            message: The message data to send (will be JSON serialized).
        """
        if discussion_id not in self._connections:
            return

        # Create a copy to avoid modification during iteration
        connections = list(self._connections[discussion_id])
        disconnected: list[WebSocket] = []

        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception as exc:
                logger.warning(
                    "Failed to send message to WebSocket: %s",
                    exc,
                )
                disconnected.append(websocket)

        # Clean up disconnected clients
        for websocket in disconnected:
            self.disconnect(websocket, discussion_id)

    async def broadcast_to_all(self, message: dict[str, Any]) -> None:
        """Broadcast a message to all connected clients.

        Args:
            message: The message data to send (will be JSON serialized).
        """
        for discussion_id in list(self._connections.keys()):
            await self.broadcast(discussion_id, message)

    async def _sweep_stale_connections(self) -> None:
        """Periodically check and clean up stale connections."""
        while True:
            try:
                await asyncio.sleep(self.SWEEP_INTERVAL)
                await self._cleanup_stale()
            except asyncio.CancelledError:
                logger.info("Sweep task cancelled")
                break
            except Exception as exc:
                logger.error("Error in sweep task: %s", exc)

    async def _cleanup_stale(self) -> None:
        """Clean up connections that have exceeded heartbeat timeout."""
        now = time.time()
        stale: list[tuple[WebSocket, str]] = []

        for discussion_id, connections in self._connections.items():
            for websocket in connections:
                last_seen = self._last_seen.get(websocket, 0)
                if now - last_seen > self.HEARTBEAT_TIMEOUT:
                    stale.append((websocket, discussion_id))

        for websocket, discussion_id in stale:
            logger.info(
                "Closing stale connection: discussion_id=%s",
                discussion_id,
            )
            try:
                await websocket.close(code=1000, reason="Heartbeat timeout")
            except Exception as exc:
                logger.debug("Error closing stale connection: %s", exc)
            finally:
                self.disconnect(websocket, discussion_id)

    def start_sweep_task(self) -> None:
        """Start the background task for sweeping stale connections.

        Should be called in FastAPI startup event.
        """
        if self._sweep_task is None:
            self._sweep_task = asyncio.create_task(self._sweep_stale_connections())
            logger.info("Started connection sweep task")

    def stop_sweep_task(self) -> None:
        """Stop the background sweep task.

        Should be called in FastAPI shutdown event.
        """
        if self._sweep_task is not None:
            self._sweep_task.cancel()
            self._sweep_task = None
            logger.info("Stopped connection sweep task")

    def get_connection_count(self, discussion_id: str | None = None) -> int:
        """Get the number of active connections.

        Args:
            discussion_id: Optional discussion ID to count connections for.
                          If None, returns total connection count.

        Returns:
            Number of active connections.
        """
        if discussion_id is not None:
            return len(self._connections.get(discussion_id, set()))

        return sum(len(conns) for conns in self._connections.values())


# Global connection manager instance
connection_manager = ConnectionManager()


def broadcast_sync(discussion_id: str, message: dict[str, Any]) -> None:
    """Broadcast a message from synchronous code.

    This function bridges sync code (like CrewAI callbacks) to async WebSocket broadcast.

    Args:
        discussion_id: The discussion ID to broadcast to.
        message: The message data to send.
    """
    if _main_loop is None:
        logger.debug("Event loop not set, skipping broadcast")
        return

    try:
        asyncio.run_coroutine_threadsafe(
            connection_manager.broadcast(discussion_id, message),
            _main_loop,
        )
    except Exception as exc:
        logger.warning("Failed to schedule broadcast: %s", exc)
