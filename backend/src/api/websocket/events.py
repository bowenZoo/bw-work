"""WebSocket event definitions and message models."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ClientMessageType(str, Enum):
    """Types of messages sent from client to server."""

    PING = "ping"


class ServerMessageType(str, Enum):
    """Types of messages sent from server to client."""

    MESSAGE = "message"
    STATUS = "status"
    ERROR = "error"
    PONG = "pong"


class AgentStatus(str, Enum):
    """Agent activity status."""

    THINKING = "thinking"
    SPEAKING = "speaking"
    IDLE = "idle"


class ClientMessage(BaseModel):
    """Message sent from client to server."""

    type: ClientMessageType


class MessageData(BaseModel):
    """Data payload for server messages."""

    discussion_id: str
    agent_id: str | None = None
    agent_role: str | None = None
    content: str | None = None
    status: AgentStatus | None = None
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ServerMessage(BaseModel):
    """Message sent from server to client."""

    type: ServerMessageType
    data: MessageData

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return self.model_dump(mode="json")


class MessageEvent(ServerMessage):
    """Event for agent messages during discussion."""

    type: ServerMessageType = ServerMessageType.MESSAGE


class StatusEvent(ServerMessage):
    """Event for agent status changes."""

    type: ServerMessageType = ServerMessageType.STATUS


class ErrorEvent(ServerMessage):
    """Event for error notifications."""

    type: ServerMessageType = ServerMessageType.ERROR


class PongEvent(BaseModel):
    """Response to client ping."""

    type: ServerMessageType = ServerMessageType.PONG
    data: dict[str, str] = Field(
        default_factory=lambda: {
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return self.model_dump(mode="json")


def create_message_event(
    discussion_id: str,
    agent_id: str,
    agent_role: str,
    content: str,
) -> MessageEvent:
    """Create a message event for agent output.

    Args:
        discussion_id: The discussion ID.
        agent_id: The agent identifier.
        agent_role: The agent's role name.
        content: The message content.

    Returns:
        A MessageEvent instance.
    """
    return MessageEvent(
        data=MessageData(
            discussion_id=discussion_id,
            agent_id=agent_id,
            agent_role=agent_role,
            content=content,
        )
    )


def create_status_event(
    discussion_id: str,
    agent_id: str,
    agent_role: str,
    status: AgentStatus,
) -> StatusEvent:
    """Create a status event for agent state changes.

    Args:
        discussion_id: The discussion ID.
        agent_id: The agent identifier.
        agent_role: The agent's role name.
        status: The new agent status.

    Returns:
        A StatusEvent instance.
    """
    return StatusEvent(
        data=MessageData(
            discussion_id=discussion_id,
            agent_id=agent_id,
            agent_role=agent_role,
            status=status,
        )
    )


def create_error_event(
    discussion_id: str,
    content: str,
) -> ErrorEvent:
    """Create an error event.

    Args:
        discussion_id: The discussion ID.
        content: The error message.

    Returns:
        An ErrorEvent instance.
    """
    return ErrorEvent(
        data=MessageData(
            discussion_id=discussion_id,
            content=content,
        )
    )
