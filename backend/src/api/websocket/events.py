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
    # Project discussion events
    GDD_PARSING_PROGRESS = "gdd_parsing_progress"
    PROJECT_DISCUSSION_START = "project_discussion_start"
    MODULE_DISCUSSION_START = "module_discussion_start"
    MODULE_DISCUSSION_PROGRESS = "module_discussion_progress"
    MODULE_DISCUSSION_COMPLETE = "module_discussion_complete"
    PROJECT_DISCUSSION_COMPLETE = "project_discussion_complete"
    DISCUSSION_PAUSED = "discussion_paused"
    # Agenda events
    AGENDA = "agenda"


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
    sequence: int | None = None  # Message sequence number for ordering
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
    sequence: int | None = None,
) -> MessageEvent:
    """Create a message event for agent output.

    Args:
        discussion_id: The discussion ID.
        agent_id: The agent identifier.
        agent_role: The agent's role name.
        content: The message content.
        sequence: Optional message sequence number for ordering.

    Returns:
        A MessageEvent instance.
    """
    return MessageEvent(
        data=MessageData(
            discussion_id=discussion_id,
            agent_id=agent_id,
            agent_role=agent_role,
            content=content,
            sequence=sequence,
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


# Project discussion event models


class ProjectDiscussionEventData(BaseModel):
    """Data payload for project discussion events."""

    project_id: str
    discussion_id: str | None = None
    gdd_id: str | None = None
    module_id: str | None = None
    module_name: str | None = None
    module_index: int | None = None
    total_modules: int | None = None
    module_order: list[str] | None = None
    round: int | None = None
    speaker: str | None = None
    message_id: str | None = None
    summary: str | None = None
    message: str | None = None
    design_doc_path: str | None = None
    key_decisions: list[str] | None = None
    total_duration_minutes: float | None = None
    design_docs: list[str] | None = None
    summary_path: str | None = None
    checkpoint_id: str | None = None
    completed_modules: int | None = None
    status: str | None = None
    error_message: str | None = None
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ProjectDiscussionEvent(BaseModel):
    """Base event for project discussions."""

    type: ServerMessageType
    data: ProjectDiscussionEventData

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return self.model_dump(mode="json", exclude_none=True)


class GddParsingProgressEvent(ProjectDiscussionEvent):
    """Event for GDD parsing progress."""

    type: ServerMessageType = ServerMessageType.GDD_PARSING_PROGRESS


class ProjectDiscussionStartEvent(ProjectDiscussionEvent):
    """Event when project discussion starts."""

    type: ServerMessageType = ServerMessageType.PROJECT_DISCUSSION_START


class ModuleDiscussionStartEvent(ProjectDiscussionEvent):
    """Event when a module discussion starts."""

    type: ServerMessageType = ServerMessageType.MODULE_DISCUSSION_START


class ModuleDiscussionProgressEvent(ProjectDiscussionEvent):
    """Event for module discussion progress updates."""

    type: ServerMessageType = ServerMessageType.MODULE_DISCUSSION_PROGRESS


class ModuleDiscussionCompleteEvent(ProjectDiscussionEvent):
    """Event when a module discussion completes."""

    type: ServerMessageType = ServerMessageType.MODULE_DISCUSSION_COMPLETE


class ProjectDiscussionCompleteEvent(ProjectDiscussionEvent):
    """Event when project discussion completes."""

    type: ServerMessageType = ServerMessageType.PROJECT_DISCUSSION_COMPLETE


class DiscussionPausedEvent(ProjectDiscussionEvent):
    """Event when discussion is paused."""

    type: ServerMessageType = ServerMessageType.DISCUSSION_PAUSED


def create_gdd_parsing_progress_event(
    project_id: str,
    gdd_id: str,
    status: str,
    message: str | None = None,
) -> GddParsingProgressEvent:
    """Create a GDD parsing progress event."""
    return GddParsingProgressEvent(
        data=ProjectDiscussionEventData(
            project_id=project_id,
            gdd_id=gdd_id,
            status=status,
            message=message,
        )
    )


def create_project_discussion_start_event(
    project_id: str,
    discussion_id: str,
    total_modules: int,
    module_order: list[str],
) -> ProjectDiscussionStartEvent:
    """Create a project discussion start event."""
    return ProjectDiscussionStartEvent(
        data=ProjectDiscussionEventData(
            project_id=project_id,
            discussion_id=discussion_id,
            total_modules=total_modules,
            module_order=module_order,
        )
    )


def create_module_discussion_start_event(
    project_id: str,
    discussion_id: str,
    module_id: str,
    module_name: str,
    module_index: int,
    total_modules: int,
) -> ModuleDiscussionStartEvent:
    """Create a module discussion start event."""
    return ModuleDiscussionStartEvent(
        data=ProjectDiscussionEventData(
            project_id=project_id,
            discussion_id=discussion_id,
            module_id=module_id,
            module_name=module_name,
            module_index=module_index,
            total_modules=total_modules,
        )
    )


def create_module_discussion_progress_event(
    project_id: str,
    discussion_id: str,
    module_id: str,
    round: int,
    speaker: str,
    summary: str,
    message: str | None = None,
    message_id: str | None = None,
) -> ModuleDiscussionProgressEvent:
    """Create a module discussion progress event."""
    return ModuleDiscussionProgressEvent(
        data=ProjectDiscussionEventData(
            project_id=project_id,
            discussion_id=discussion_id,
            module_id=module_id,
            round=round,
            speaker=speaker,
            summary=summary,
            message=message,
            message_id=message_id,
        )
    )


def create_module_discussion_complete_event(
    project_id: str,
    discussion_id: str,
    module_id: str,
    design_doc_path: str,
    key_decisions: list[str],
) -> ModuleDiscussionCompleteEvent:
    """Create a module discussion complete event."""
    return ModuleDiscussionCompleteEvent(
        data=ProjectDiscussionEventData(
            project_id=project_id,
            discussion_id=discussion_id,
            module_id=module_id,
            design_doc_path=design_doc_path,
            key_decisions=key_decisions,
        )
    )


def create_project_discussion_complete_event(
    project_id: str,
    discussion_id: str,
    total_duration_minutes: float,
    design_docs: list[str],
    summary_path: str,
) -> ProjectDiscussionCompleteEvent:
    """Create a project discussion complete event."""
    return ProjectDiscussionCompleteEvent(
        data=ProjectDiscussionEventData(
            project_id=project_id,
            discussion_id=discussion_id,
            total_duration_minutes=total_duration_minutes,
            design_docs=design_docs,
            summary_path=summary_path,
        )
    )


def create_discussion_paused_event(
    project_id: str,
    discussion_id: str,
    checkpoint_id: str,
    current_module: str | None,
    completed_modules: int,
) -> DiscussionPausedEvent:
    """Create a discussion paused event."""
    return DiscussionPausedEvent(
        data=ProjectDiscussionEventData(
            project_id=project_id,
            discussion_id=discussion_id,
            checkpoint_id=checkpoint_id,
            module_id=current_module,
            completed_modules=completed_modules,
        )
    )


# Agenda event models


class AgendaEventType(str, Enum):
    """Types of agenda events."""

    AGENDA_INIT = "agenda_init"
    ITEM_START = "item_start"
    ITEM_COMPLETE = "item_complete"
    ITEM_SKIP = "item_skip"
    ITEM_ADD = "item_add"


class AgendaEventData(BaseModel):
    """Data payload for agenda events."""

    discussion_id: str
    event_type: AgendaEventType
    item_id: str | None = None
    title: str | None = None
    summary: str | None = None
    current_index: int | None = None
    agenda: dict[str, Any] | None = None  # Full agenda for init event
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class AgendaEvent(BaseModel):
    """Event for agenda updates."""

    type: ServerMessageType = ServerMessageType.AGENDA
    data: AgendaEventData

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return self.model_dump(mode="json", exclude_none=True)


def create_agenda_event(
    discussion_id: str,
    event_type: str,
    data: dict[str, Any],
) -> AgendaEvent:
    """Create an agenda event.

    Args:
        discussion_id: The discussion ID.
        event_type: Type of agenda event (agenda_init, item_start, item_complete, etc.).
        data: Event-specific data.

    Returns:
        An AgendaEvent instance.
    """
    # Convert string event_type to enum
    try:
        agenda_event_type = AgendaEventType(event_type)
    except ValueError:
        agenda_event_type = AgendaEventType.ITEM_START  # Default fallback

    return AgendaEvent(
        data=AgendaEventData(
            discussion_id=discussion_id,
            event_type=agenda_event_type,
            item_id=data.get("item_id"),
            title=data.get("title"),
            summary=data.get("summary"),
            current_index=data.get("current_index"),
            agenda=data.get("agenda"),
        )
    )


def create_agenda_init_event(
    discussion_id: str,
    agenda: dict[str, Any],
) -> AgendaEvent:
    """Create an agenda initialization event.

    Args:
        discussion_id: The discussion ID.
        agenda: The full agenda data.

    Returns:
        An AgendaEvent instance.
    """
    return AgendaEvent(
        data=AgendaEventData(
            discussion_id=discussion_id,
            event_type=AgendaEventType.AGENDA_INIT,
            agenda=agenda,
        )
    )


def create_agenda_item_start_event(
    discussion_id: str,
    item_id: str,
    title: str,
    current_index: int,
) -> AgendaEvent:
    """Create an agenda item start event.

    Args:
        discussion_id: The discussion ID.
        item_id: The agenda item ID.
        title: The item title.
        current_index: Current agenda index.

    Returns:
        An AgendaEvent instance.
    """
    return AgendaEvent(
        data=AgendaEventData(
            discussion_id=discussion_id,
            event_type=AgendaEventType.ITEM_START,
            item_id=item_id,
            title=title,
            current_index=current_index,
        )
    )


def create_agenda_item_complete_event(
    discussion_id: str,
    item_id: str,
    title: str,
    summary: str,
    current_index: int,
) -> AgendaEvent:
    """Create an agenda item complete event.

    Args:
        discussion_id: The discussion ID.
        item_id: The agenda item ID.
        title: The item title.
        summary: The item summary.
        current_index: Current agenda index.

    Returns:
        An AgendaEvent instance.
    """
    return AgendaEvent(
        data=AgendaEventData(
            discussion_id=discussion_id,
            event_type=AgendaEventType.ITEM_COMPLETE,
            item_id=item_id,
            title=title,
            summary=summary,
            current_index=current_index,
        )
    )


def create_agenda_item_skip_event(
    discussion_id: str,
    item_id: str,
    title: str,
    current_index: int,
) -> AgendaEvent:
    """Create an agenda item skip event.

    Args:
        discussion_id: The discussion ID.
        item_id: The agenda item ID.
        title: The item title.
        current_index: Current agenda index.

    Returns:
        An AgendaEvent instance.
    """
    return AgendaEvent(
        data=AgendaEventData(
            discussion_id=discussion_id,
            event_type=AgendaEventType.ITEM_SKIP,
            item_id=item_id,
            title=title,
            current_index=current_index,
        )
    )


def create_agenda_item_add_event(
    discussion_id: str,
    item_id: str,
    title: str,
) -> AgendaEvent:
    """Create an agenda item add event.

    Args:
        discussion_id: The discussion ID.
        item_id: The new item ID.
        title: The item title.

    Returns:
        An AgendaEvent instance.
    """
    return AgendaEvent(
        data=AgendaEventData(
            discussion_id=discussion_id,
            event_type=AgendaEventType.ITEM_ADD,
            item_id=item_id,
            title=title,
        )
    )
