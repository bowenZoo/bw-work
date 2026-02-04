"""WebSocket module for real-time communication."""

from src.api.websocket.handlers import router as websocket_router
from src.api.websocket.manager import ConnectionManager, connection_manager

__all__ = ["ConnectionManager", "connection_manager", "websocket_router"]
