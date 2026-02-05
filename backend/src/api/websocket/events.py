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
    # Image generation events
    IMAGE_GENERATION_START = "image_generation_start"
    IMAGE_GENERATION_COMPLETE = "image_generation_complete"
    IMAGE_GENERATION_ERROR = "image_generation_error"


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
    content: str | None = None,
) -> StatusEvent:
    """Create a status event for agent state changes.

    Args:
        discussion_id: The discussion ID.
        agent_id: The agent identifier.
        agent_role: The agent's role name.
        status: The new agent status.
        content: Optional status message.

    Returns:
        A StatusEvent instance.
    """
    return StatusEvent(
        data=MessageData(
            discussion_id=discussion_id,
            agent_id=agent_id,
            agent_role=agent_role,
            status=status,
            content=content,
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


# Image generation event models
class ImageGenerationEventData(BaseModel):
    """Data payload for image generation events."""

    request_id: str
    prompt: str | None = None
    style: str | None = None
    provider_id: str | None = None
    image_url: str | None = None
    error: str | None = None
    metadata: dict[str, Any] | None = None
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ImageGenerationEvent(BaseModel):
    """Base event for image generation."""

    type: ServerMessageType
    data: ImageGenerationEventData

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return self.model_dump(mode="json")


class ImageGenerationStartEvent(ImageGenerationEvent):
    """Event when image generation starts."""

    type: ServerMessageType = ServerMessageType.IMAGE_GENERATION_START


class ImageGenerationCompleteEvent(ImageGenerationEvent):
    """Event when image generation completes."""

    type: ServerMessageType = ServerMessageType.IMAGE_GENERATION_COMPLETE


class ImageGenerationErrorEvent(ImageGenerationEvent):
    """Event when image generation fails."""

    type: ServerMessageType = ServerMessageType.IMAGE_GENERATION_ERROR


def create_image_generation_start_event(
    request_id: str,
    prompt: str,
    style: str,
    provider_id: str,
) -> ImageGenerationStartEvent:
    """Create an image generation start event.

    Args:
        request_id: The image request ID.
        prompt: The generation prompt.
        style: The style template used.
        provider_id: The provider ID.

    Returns:
        An ImageGenerationStartEvent instance.
    """
    return ImageGenerationStartEvent(
        data=ImageGenerationEventData(
            request_id=request_id,
            prompt=prompt,
            style=style,
            provider_id=provider_id,
        )
    )


def create_image_generation_complete_event(
    request_id: str,
    image_url: str,
    metadata: dict[str, Any] | None = None,
) -> ImageGenerationCompleteEvent:
    """Create an image generation complete event.

    Args:
        request_id: The image request ID.
        image_url: URL to access the generated image.
        metadata: Optional metadata about the generation.

    Returns:
        An ImageGenerationCompleteEvent instance.
    """
    return ImageGenerationCompleteEvent(
        data=ImageGenerationEventData(
            request_id=request_id,
            image_url=image_url,
            metadata=metadata,
        )
    )


def create_image_generation_error_event(
    request_id: str,
    error: str,
) -> ImageGenerationErrorEvent:
    """Create an image generation error event.

    Args:
        request_id: The image request ID.
        error: The error message.

    Returns:
        An ImageGenerationErrorEvent instance.
    """
    return ImageGenerationErrorEvent(
        data=ImageGenerationEventData(
            request_id=request_id,
            error=error,
        )
    )
