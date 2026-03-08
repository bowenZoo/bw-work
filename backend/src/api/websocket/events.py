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
    # Round summary and doc update events
    ROUND_SUMMARY = "round_summary"
    DOC_UPDATE = "doc_update"
    # Agenda events
    AGENDA = "agenda"
    # Document-centric events
    DOC_PLAN = "doc_plan"
    SECTION_FOCUS = "section_focus"
    SECTION_UPDATE = "section_update"
    # Dynamic discussion events
    DOC_RESTRUCTURE = "doc_restructure"
    SECTION_REOPENED = "section_reopened"
    LEAD_PLANNER_DIGEST = "lead_planner_digest"
    INTERVENTION_ASSESSMENT = "intervention_assessment"
    HOLISTIC_REVIEW = "holistic_review"
    # Checkpoint events
    CHECKPOINT = "checkpoint"
    # Producer digest event
    PRODUCER_DIGEST = "producer_digest"
    # Super producer question cards (triggered by @超级制作人 in agent messages)
    PRODUCER_QUESTION = "producer_question"


class AgentStatus(str, Enum):
    """Agent activity status."""

    THINKING = "thinking"
    SPEAKING = "speaking"
    IDLE = "idle"
    WRITING = "writing"


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
    MAPPING_UPDATE = "mapping_update"


class AgendaEventData(BaseModel):
    """Data payload for agenda events."""

    discussion_id: str
    event_type: AgendaEventType
    item_id: str | None = None
    title: str | None = None
    summary: str | None = None
    current_index: int | None = None
    agenda: dict[str, Any] | None = None  # Full agenda for init event
    mappings: dict[str, list[str]] | None = None  # item_id -> section_ids mapping
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


# Round summary and doc update event models


class RoundSummaryEventData(BaseModel):
    """Data payload for round summary events."""

    discussion_id: str
    round: int
    content: str
    key_points: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class RoundSummaryEvent(BaseModel):
    """Event when a round summary is generated."""

    type: ServerMessageType = ServerMessageType.ROUND_SUMMARY
    data: RoundSummaryEventData

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return self.model_dump(mode="json")


class DocUpdateEventData(BaseModel):
    """Data payload for doc update events."""

    discussion_id: str
    round: int
    file_count: int
    files: list[dict[str, str]] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class DocUpdateEvent(BaseModel):
    """Event when design documents are updated."""

    type: ServerMessageType = ServerMessageType.DOC_UPDATE
    data: DocUpdateEventData

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return self.model_dump(mode="json")


def create_round_summary_event(
    discussion_id: str,
    round_num: int,
    content: str,
    key_points: list[str] | None = None,
    open_questions: list[str] | None = None,
) -> RoundSummaryEvent:
    """Create a round summary event.

    Args:
        discussion_id: The discussion ID.
        round_num: The round number.
        content: The summary content.
        key_points: Key points from the round.
        open_questions: Open questions remaining.

    Returns:
        A RoundSummaryEvent instance.
    """
    return RoundSummaryEvent(
        data=RoundSummaryEventData(
            discussion_id=discussion_id,
            round=round_num,
            content=content,
            key_points=key_points or [],
            open_questions=open_questions or [],
        )
    )


def create_doc_update_event(
    discussion_id: str,
    round_num: int,
    file_count: int,
    files: list[dict[str, str]] | None = None,
) -> DocUpdateEvent:
    """Create a doc update event.

    Args:
        discussion_id: The discussion ID.
        round_num: The round that triggered the update.
        file_count: Number of document files.
        files: List of file info dicts with 'filename' and 'title'.

    Returns:
        A DocUpdateEvent instance.
    """
    return DocUpdateEvent(
        data=DocUpdateEventData(
            discussion_id=discussion_id,
            round=round_num,
            file_count=file_count,
            files=files or [],
        )
    )


# Document-centric event models


class DocPlanEventData(BaseModel):
    discussion_id: str
    doc_plan: dict
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DocPlanEvent(BaseModel):
    type: ServerMessageType = ServerMessageType.DOC_PLAN
    data: DocPlanEventData

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class SectionFocusEventData(BaseModel):
    discussion_id: str
    section_id: str
    section_title: str
    filename: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SectionFocusEvent(BaseModel):
    type: ServerMessageType = ServerMessageType.SECTION_FOCUS
    data: SectionFocusEventData

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class SectionUpdateEventData(BaseModel):
    discussion_id: str
    filename: str
    section_id: str
    content: str  # 更新后的完整 .md 文件内容
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SectionUpdateEvent(BaseModel):
    type: ServerMessageType = ServerMessageType.SECTION_UPDATE
    data: SectionUpdateEventData

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def create_doc_plan_event(discussion_id: str, doc_plan: dict) -> DocPlanEvent:
    return DocPlanEvent(data=DocPlanEventData(discussion_id=discussion_id, doc_plan=doc_plan))


def create_section_focus_event(discussion_id: str, section_id: str, section_title: str, filename: str) -> SectionFocusEvent:
    return SectionFocusEvent(data=SectionFocusEventData(discussion_id=discussion_id, section_id=section_id, section_title=section_title, filename=filename))


def create_section_update_event(discussion_id: str, filename: str, section_id: str, content: str) -> SectionUpdateEvent:
    return SectionUpdateEvent(data=SectionUpdateEventData(discussion_id=discussion_id, filename=filename, section_id=section_id, content=content))


# Dynamic discussion event models


class DocRestructureEventData(BaseModel):
    """Data payload for doc restructure events."""

    discussion_id: str
    operation: str  # "split" | "merge" | "add_section" | "add_file"
    details: dict[str, Any] = Field(default_factory=dict)
    updated_doc_plan: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DocRestructureEvent(BaseModel):
    """Event when document structure is modified."""

    type: ServerMessageType = ServerMessageType.DOC_RESTRUCTURE
    data: DocRestructureEventData

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)


class SectionReopenedEventData(BaseModel):
    """Data payload for section reopened events."""

    discussion_id: str
    section_id: str
    title: str
    filename: str
    reason: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SectionReopenedEvent(BaseModel):
    """Event when a completed section is reopened."""

    type: ServerMessageType = ServerMessageType.SECTION_REOPENED
    data: SectionReopenedEventData

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)


class LeadPlannerDigestEventData(BaseModel):
    """Data payload for lead planner digest events."""

    discussion_id: str
    digest_summary: str
    key_points: list[str] = Field(default_factory=list)
    guidance: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class LeadPlannerDigestEvent(BaseModel):
    """Event when lead planner digests intervention input."""

    type: ServerMessageType = ServerMessageType.LEAD_PLANNER_DIGEST
    data: LeadPlannerDigestEventData

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)


class InterventionAssessmentEventData(BaseModel):
    """Data payload for intervention assessment events."""

    discussion_id: str
    impact_level: str  # "ABSORB" | "ADJUST" | "REOPEN"
    affected_sections: list[str] = Field(default_factory=list)
    reason: str = ""
    action_plan: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class InterventionAssessmentEvent(BaseModel):
    """Event when lead planner assesses intervention impact."""

    type: ServerMessageType = ServerMessageType.INTERVENTION_ASSESSMENT
    data: InterventionAssessmentEventData

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)


class ReviewDimension(BaseModel):
    """A single dimension in holistic review."""

    name: str
    score: str  # "pass" | "warning" | "fail"
    notes: str = ""


class HolisticReviewEventData(BaseModel):
    """Data payload for holistic review events."""

    discussion_id: str
    review_round: int
    conclusion: str  # "APPROVED" | "NEEDS_REVISION" | "NEEDS_NEW_TOPIC"
    review_dimensions: list[ReviewDimension] = Field(default_factory=list)
    revisions_needed: list[dict[str, Any]] = Field(default_factory=list)
    new_topics: list[dict[str, str]] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class HolisticReviewEvent(BaseModel):
    """Event when holistic review is completed."""

    type: ServerMessageType = ServerMessageType.HOLISTIC_REVIEW
    data: HolisticReviewEventData

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)


def create_doc_restructure_event(
    discussion_id: str,
    operation: str,
    details: dict[str, Any],
    updated_doc_plan: dict[str, Any],
) -> DocRestructureEvent:
    return DocRestructureEvent(
        data=DocRestructureEventData(
            discussion_id=discussion_id,
            operation=operation,
            details=details,
            updated_doc_plan=updated_doc_plan,
        )
    )


def create_section_reopened_event(
    discussion_id: str,
    section_id: str,
    title: str,
    filename: str,
    reason: str,
) -> SectionReopenedEvent:
    return SectionReopenedEvent(
        data=SectionReopenedEventData(
            discussion_id=discussion_id,
            section_id=section_id,
            title=title,
            filename=filename,
            reason=reason,
        )
    )


def create_lead_planner_digest_event(
    discussion_id: str,
    digest_summary: str,
    key_points: list[str] | None = None,
    guidance: str = "",
) -> LeadPlannerDigestEvent:
    return LeadPlannerDigestEvent(
        data=LeadPlannerDigestEventData(
            discussion_id=discussion_id,
            digest_summary=digest_summary,
            key_points=key_points or [],
            guidance=guidance,
        )
    )


def create_intervention_assessment_event(
    discussion_id: str,
    impact_level: str,
    affected_sections: list[str] | None = None,
    reason: str = "",
    action_plan: str = "",
) -> InterventionAssessmentEvent:
    return InterventionAssessmentEvent(
        data=InterventionAssessmentEventData(
            discussion_id=discussion_id,
            impact_level=impact_level,
            affected_sections=affected_sections or [],
            reason=reason,
            action_plan=action_plan,
        )
    )


def create_holistic_review_event(
    discussion_id: str,
    review_round: int,
    conclusion: str,
    review_dimensions: list[dict[str, str]] | None = None,
    revisions_needed: list[dict[str, Any]] | None = None,
    new_topics: list[dict[str, str]] | None = None,
) -> HolisticReviewEvent:
    dims = [ReviewDimension(**d) for d in (review_dimensions or [])]
    return HolisticReviewEvent(
        data=HolisticReviewEventData(
            discussion_id=discussion_id,
            review_round=review_round,
            conclusion=conclusion,
            review_dimensions=dims,
            revisions_needed=revisions_needed or [],
            new_topics=new_topics or [],
        )
    )


# Checkpoint event models


class CheckpointEventType(str, Enum):
    """Sub-types of checkpoint events."""

    PROGRESS = "progress"
    DECISION_REQUEST = "decision_request"
    DECISION_RESPONDED = "decision_responded"
    DECISION_ANNOUNCED = "decision_announced"


class CheckpointEventData(BaseModel):
    """Data payload for checkpoint events."""

    discussion_id: str
    event_type: CheckpointEventType
    checkpoint: dict[str, Any] | None = None  # Full checkpoint data (progress/decision_request)
    checkpoint_id: str | None = None  # For responded/announced events
    response: str | None = None  # Selected option ID
    response_text: str | None = None  # Free text input
    responded_at: str | None = None
    announcement: str | None = None  # Lead planner announcement text
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CheckpointEvent(BaseModel):
    """Event for checkpoint notifications."""

    type: ServerMessageType = ServerMessageType.CHECKPOINT
    data: CheckpointEventData

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)


def create_checkpoint_progress_event(
    discussion_id: str,
    checkpoint: dict[str, Any],
) -> CheckpointEvent:
    """Create a PROGRESS checkpoint event (non-blocking notice)."""
    return CheckpointEvent(
        data=CheckpointEventData(
            discussion_id=discussion_id,
            event_type=CheckpointEventType.PROGRESS,
            checkpoint=checkpoint,
        )
    )


def create_checkpoint_decision_event(
    discussion_id: str,
    checkpoint: dict[str, Any],
) -> CheckpointEvent:
    """Create a DECISION checkpoint event (blocking, requires user response)."""
    return CheckpointEvent(
        data=CheckpointEventData(
            discussion_id=discussion_id,
            event_type=CheckpointEventType.DECISION_REQUEST,
            checkpoint=checkpoint,
        )
    )


def create_checkpoint_responded_event(
    discussion_id: str,
    checkpoint_id: str,
    response: str | None,
    response_text: str | None,
    responded_at: str,
) -> CheckpointEvent:
    """Create a checkpoint responded event (user answered a decision)."""
    return CheckpointEvent(
        data=CheckpointEventData(
            discussion_id=discussion_id,
            event_type=CheckpointEventType.DECISION_RESPONDED,
            checkpoint_id=checkpoint_id,
            response=response,
            response_text=response_text,
            responded_at=responded_at,
        )
    )


def create_decision_announced_event(
    discussion_id: str,
    checkpoint_id: str,
    announcement: str,
) -> CheckpointEvent:
    """Create a decision announced event (lead planner publicly announces the decision)."""
    return CheckpointEvent(
        data=CheckpointEventData(
            discussion_id=discussion_id,
            event_type=CheckpointEventType.DECISION_ANNOUNCED,
            checkpoint_id=checkpoint_id,
            announcement=announcement,
        )
    )


# Producer digest event models


class ProducerDigestEventData(BaseModel):
    """Data payload for producer message digest events."""

    discussion_id: str
    digest_summary: str
    action: str = "acknowledged"  # "adjust" | "follow_up_decision" | "acknowledged"
    guidance: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ProducerDigestEvent(BaseModel):
    """Event when lead planner digests a producer message."""

    type: ServerMessageType = ServerMessageType.PRODUCER_DIGEST
    data: ProducerDigestEventData

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)


def create_producer_digest_event(
    discussion_id: str,
    digest_summary: str,
    action: str = "acknowledged",
    guidance: str = "",
) -> ProducerDigestEvent:
    """Create a producer digest event."""
    return ProducerDigestEvent(
        data=ProducerDigestEventData(
            discussion_id=discussion_id,
            digest_summary=digest_summary,
            action=action,
            guidance=guidance,
        )
    )


# ── Producer Question Event ──────────────────────────────────────────────────

class ProducerQuestionItem(BaseModel):
    """A single question directed at the producer via @超级制作人."""

    from_agent: str
    question: str


class ProducerQuestionEventData(BaseModel):
    """Data for a producer_question event."""

    discussion_id: str
    questions: list[ProducerQuestionItem]
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ProducerQuestionEvent(BaseModel):
    """Event broadcasting @超级制作人 questions that need decision cards."""

    type: ServerMessageType = ServerMessageType.PRODUCER_QUESTION
    data: ProducerQuestionEventData

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def create_producer_question_event(
    discussion_id: str,
    questions: list[dict],
) -> ProducerQuestionEvent:
    """Create a producer_question event from a list of {from_agent, question} dicts."""
    items = [ProducerQuestionItem(**q) for q in questions]
    return ProducerQuestionEvent(
        data=ProducerQuestionEventData(
            discussion_id=discussion_id,
            questions=items,
        )
    )
