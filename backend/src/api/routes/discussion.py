"""Discussion API routes."""
import asyncio
import json
import logging
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from crewai import Crew, Process
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.agents import Summarizer
from src.api.websocket.events import AgentStatus, create_error_event, create_status_event
from src.api.websocket.manager import broadcast_sync
from src.crew.discussion_crew import DiscussionCrew
from src.memory.base import Discussion, Message
from src.memory.discussion_memory import DiscussionMemory
from src.models.agenda import Agenda, AgendaItem, AgendaItemStatus, AgendaSummaryDetails

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/discussions", tags=["discussions"])

# Memory storage for summaries
_discussion_memory = DiscussionMemory(data_dir="data/projects")


class DiscussionStatus(str, Enum):
    """Status of a discussion."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AttachmentInfo(BaseModel):
    """Attachment file info."""

    filename: str = Field(..., description="Original filename")
    content: str = Field(..., description="File content")


class CreateDiscussionRequest(BaseModel):
    """Request body for creating a discussion."""

    topic: str = Field(..., min_length=1, description="The discussion topic")
    rounds: int = Field(default=10, ge=1, le=50, description="Number of discussion rounds")
    auto_pause_interval: int = Field(default=5, ge=0, le=50, description="Auto-pause every N rounds (0=disabled)")
    attachment: AttachmentInfo | None = Field(default=None, description="Optional markdown attachment")


class CreateDiscussionResponse(BaseModel):
    """Response for creating a discussion."""

    id: str = Field(..., description="Discussion ID")
    topic: str = Field(..., description="The discussion topic")
    rounds: int = Field(..., description="Number of rounds")
    status: DiscussionStatus = Field(..., description="Current status")
    created_at: str = Field(..., description="Creation timestamp")


class DiscussionState(BaseModel):
    """Internal state of a discussion."""

    id: str
    topic: str
    rounds: int
    auto_pause_interval: int = 5
    status: DiscussionStatus
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    result: str | None = None
    error: str | None = None
    attachment: AttachmentInfo | None = None
    continued_from: str | None = None  # 原讨论 ID（如果是续前讨论）


class GetDiscussionResponse(BaseModel):
    """Response for getting discussion status."""

    id: str
    topic: str
    rounds: int
    status: DiscussionStatus
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    result: str | None = None
    error: str | None = None
    attachment: AttachmentInfo | None = None
    continued_from: str | None = None  # 原讨论 ID
    is_continuation: bool = False  # 是否是续前讨论


class StartDiscussionResponse(BaseModel):
    """Response for starting a discussion."""

    id: str
    status: DiscussionStatus
    message: str


class SummarizeRequest(BaseModel):
    """Request body for generating a summary."""

    regenerate: bool = Field(default=False, description="Force regenerate summary even if one exists")


class ContinueDiscussionRequest(BaseModel):
    """Request body for continuing a discussion."""

    follow_up: str = Field(default="", description="Follow-up topic or question to continue discussing (optional)")
    rounds: int = Field(default=2, ge=1, le=10, description="Number of additional discussion rounds")


class ContinueDiscussionResponse(BaseModel):
    """Response for continuing a discussion."""

    new_discussion_id: str = Field(..., description="ID of the new continuation discussion")
    original_discussion_id: str = Field(..., description="ID of the original discussion")
    topic: str = Field(..., description="Combined topic for the continuation")
    status: DiscussionStatus = Field(..., description="Current status")
    message: str = Field(..., description="Status message")


class SummaryResponse(BaseModel):
    """Response containing discussion summary."""

    discussion_id: str
    topic: str
    summary: str
    key_points: list[str] = Field(default_factory=list)
    agreements: list[str] = Field(default_factory=list)
    disagreements: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    generated_at: str


class DiscussionSummaryItem(BaseModel):
    """Summary item for discussion list."""

    id: str
    project_id: str
    topic: str
    summary: str | None = None
    message_count: int = 0
    created_at: str
    updated_at: str


class DiscussionListResponse(BaseModel):
    """Response for listing discussions."""

    items: list[DiscussionSummaryItem]
    hasMore: bool = Field(default=False, alias="hasMore")


class MessageResponse(BaseModel):
    """Response for a message."""

    id: str
    agent_id: str
    agent_role: str
    content: str
    timestamp: str


class DiscussionMessagesResponse(BaseModel):
    """Response for discussion messages."""

    discussion: DiscussionSummaryItem
    messages: list[MessageResponse]


class CreateCurrentDiscussionRequest(BaseModel):
    """Request body for creating a new global discussion."""

    topic: str = Field(..., min_length=1, description="The discussion topic")
    rounds: int = Field(default=10, ge=1, le=50, description="Number of discussion rounds")
    auto_pause_interval: int = Field(default=5, ge=0, le=50, description="Auto-pause every N rounds (0=disabled)")
    attachment: AttachmentInfo | None = Field(default=None, description="Optional markdown attachment")


class CreateCurrentDiscussionResponse(BaseModel):
    """Response for creating a global discussion."""

    id: str = Field(..., description="Discussion ID")
    topic: str = Field(..., description="The discussion topic")
    rounds: int = Field(..., description="Number of rounds")
    status: DiscussionStatus = Field(..., description="Current status")
    created_at: str = Field(..., description="Creation timestamp")
    message: str | None = Field(default=None, description="Optional status message")


class JoinDiscussionResponse(BaseModel):
    """Response for joining the current discussion."""

    discussion: GetDiscussionResponse | None = Field(None, description="Current discussion if exists")
    messages: list[MessageResponse] = Field(default_factory=list, description="Historical messages")


# Discussion state persistence
_STATE_DIR = Path(os.environ.get("DISCUSSION_STATUS_DIR", "data/projects/.discussion_state"))
_state_lock = threading.Lock()
_DISCUSSION_EXECUTOR = ThreadPoolExecutor(
    max_workers=int(os.environ.get("DISCUSSION_MAX_WORKERS", "4"))
)

# In-memory cache for quick reads (also persisted to disk)
_discussions: dict[str, DiscussionState] = {}

# Store generated summaries
_summaries: dict[str, SummaryResponse] = {}

# Global discussion state (single active discussion for all users)
_current_discussion: DiscussionState | None = None
_current_discussion_lock = threading.RLock()


def get_current_discussion() -> DiscussionState | None:
    """Get the current global discussion.

    Returns:
        The current discussion state, or None if no discussion is active.
    """
    with _current_discussion_lock:
        return _current_discussion


def cleanup_stale_discussions() -> int:
    """Clean up stale 'running' discussions on server startup.

    Any discussion stuck in 'running' state is marked as 'failed'
    since the background task cannot survive a server restart.

    Returns:
        Number of discussions cleaned up.
    """
    cleaned = 0
    if not _STATE_DIR.exists():
        return cleaned

    for path in _STATE_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("status") == DiscussionStatus.RUNNING:
                data["status"] = DiscussionStatus.FAILED
                data["error"] = "服务器重启，讨论中断"
                data["completed_at"] = datetime.utcnow().isoformat()
                path.write_text(
                    json.dumps(data, ensure_ascii=False), encoding="utf-8"
                )
                logger.info("Cleaned up stale discussion: %s", data.get("id"))
                cleaned += 1
        except Exception as e:
            logger.warning("Failed to clean up %s: %s", path, e)

    # Also clear the in-memory current discussion
    global _current_discussion
    with _current_discussion_lock:
        if _current_discussion and _current_discussion.status == DiscussionStatus.RUNNING:
            _current_discussion = None

    return cleaned


def set_current_discussion(discussion: DiscussionState | None) -> None:
    """Set the current global discussion.

    Args:
        discussion: The discussion to set as current, or None to clear.
    """
    global _current_discussion
    with _current_discussion_lock:
        _current_discussion = discussion


def _validate_discussion_id(discussion_id: str) -> bool:
    """Validate discussion_id is a safe filename (UUID or alphanumeric with hyphens)."""
    import re
    return bool(re.match(r'^[a-zA-Z0-9_-]+$', discussion_id))


def _state_path(discussion_id: str) -> Path:
    if not _validate_discussion_id(discussion_id):
        raise ValueError(f"Invalid discussion_id: {discussion_id}")
    path = _STATE_DIR / f"{discussion_id}.json"
    # Ensure resolved path is still under _STATE_DIR
    if not path.resolve().is_relative_to(_STATE_DIR.resolve()):
        raise ValueError(f"Invalid discussion_id: {discussion_id}")
    return path


def _persist_discussion_state(discussion: DiscussionState) -> None:
    try:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        _state_path(discussion.id).write_text(
            json.dumps(discussion.model_dump(), ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as e:
        logger.warning("Failed to persist discussion state %s: %s", discussion.id, e)


def _load_discussion_state(discussion_id: str) -> DiscussionState | None:
    path = _state_path(discussion_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return DiscussionState(**data)
    except Exception:
        return None


def get_discussion_state(discussion_id: str) -> DiscussionState | None:
    with _state_lock:
        discussion = _discussions.get(discussion_id)
        if discussion is not None:
            return discussion
        discussion = _load_discussion_state(discussion_id)
        if discussion is not None:
            _discussions[discussion_id] = discussion
        return discussion


def save_discussion_state(discussion: DiscussionState) -> None:
    with _state_lock:
        _discussions[discussion.id] = discussion
        _persist_discussion_state(discussion)


def _get_llm_from_config() -> Any | None:
    """Get LLM instance from admin config store.

    Also sets OPENAI_API_KEY environment variable for CrewAI compatibility.

    Returns:
        LLM instance if configured, None otherwise.
    """
    try:
        from src.admin.config_store import ConfigStore

        store = ConfigStore()
        api_key = store.get_raw("llm", "openai_api_key")

        if not api_key:
            logger.warning("No OpenAI API key configured in admin store")
            return None

        base_url = store.get_raw("llm", "openai_base_url")
        model = store.get_raw("llm", "openai_model") or "gpt-4"

        # Set environment variables for CrewAI/LiteLLM compatibility
        # CrewAI internally checks for these even when LLM is provided
        os.environ["OPENAI_API_KEY"] = api_key
        if base_url:
            # Set all possible environment variable names for base URL
            os.environ["OPENAI_API_BASE"] = base_url
            os.environ["OPENAI_BASE_URL"] = base_url

        # Set model name in environment for CrewAI
        os.environ["OPENAI_MODEL_NAME"] = model

        # Use langchain's ChatOpenAI which is compatible with CrewAI
        from langchain_openai import ChatOpenAI

        llm_kwargs: dict[str, Any] = {
            "model": model,
            "api_key": api_key,
        }
        if base_url:
            llm_kwargs["base_url"] = base_url

        return ChatOpenAI(**llm_kwargs)
    except ImportError as e:
        logger.error("Error importing ChatOpenAI: %s", e)
        return None
    except Exception as e:
        logger.error("Error creating LLM from config: %s", e)
        return None


def _auto_organize_docs(discussion_id: str) -> None:
    """Auto-organize discussion results into design documents.

    Called after discussion completes. Failures are logged but do not
    affect the discussion state.
    """
    from src.agents.doc_organizer import DocOrganizer

    stored = _discussion_memory.load(discussion_id)
    if stored is None or not stored.messages:
        logger.info("Skipping auto-organize for %s: no messages found", discussion_id)
        return

    llm = _get_llm_from_config()
    if llm is None:
        logger.warning("Skipping auto-organize for %s: LLM not configured", discussion_id)
        return

    organizer = DocOrganizer(llm=llm)
    result = organizer.run_organize(stored)
    logger.info(
        "Auto-organized %s: %d documents generated",
        discussion_id,
        len(result.files),
    )


def _run_discussion_sync(discussion_id: str) -> None:
    """Run a discussion synchronously (for background task)."""
    logger.info("Starting discussion %s in background thread", discussion_id)
    discussion = get_discussion_state(discussion_id)
    if discussion is None:
        logger.error("Discussion %s not found, aborting", discussion_id)
        return

    try:
        if discussion.started_at is None:
            discussion.status = DiscussionStatus.RUNNING
            discussion.started_at = datetime.utcnow().isoformat()
            save_discussion_state(discussion)

        # Get LLM from admin config store
        llm = _get_llm_from_config()
        if llm is None:
            raise RuntimeError("LLM not configured. Please configure OpenAI API key in admin panel.")

        logger.info("Discussion %s: LLM configured, creating DiscussionCrew", discussion_id)
        crew = DiscussionCrew(discussion_id=discussion_id, llm=llm)
        logger.info("Discussion %s: Starting crew.run()", discussion_id)
        result = crew.run(
            topic=discussion.topic,
            rounds=discussion.rounds,
            verbose=False,
            attachment=discussion.attachment.content if discussion.attachment else None,
            auto_pause_interval=discussion.auto_pause_interval,
        )

        discussion.result = result
        discussion.status = DiscussionStatus.COMPLETED
        discussion.completed_at = datetime.utcnow().isoformat()
        save_discussion_state(discussion)

        # Update global discussion state if this is the current discussion
        current = get_current_discussion()
        if current and current.id == discussion_id:
            set_current_discussion(discussion)

        # Auto-organize discussion into design documents
        try:
            _auto_organize_docs(discussion_id)
        except Exception as org_err:
            logger.warning("Auto-organize failed for %s: %s", discussion_id, org_err)

    except Exception as e:
        logger.error("Discussion %s failed: %s", discussion_id, e)
        discussion.status = DiscussionStatus.FAILED
        discussion.error = str(e)
        discussion.completed_at = datetime.utcnow().isoformat()
        save_discussion_state(discussion)

        # Broadcast failure to WebSocket clients
        try:
            error_event = create_error_event(
                discussion_id=discussion_id,
                content=str(e),
            )
            broadcast_sync(error_event.to_dict(), discussion_id=discussion_id)
            status_event = create_status_event(
                discussion_id=discussion_id,
                agent_id="discussion",
                agent_role="discussion",
                status=AgentStatus.IDLE,
                content="discussion_failed",
            )
            broadcast_sync(status_event.to_dict(), discussion_id=discussion_id)
        except Exception:
            logger.debug("Failed to broadcast discussion failure event")

        # Update global discussion state if this is the current discussion
        current = get_current_discussion()
        if current and current.id == discussion_id:
            set_current_discussion(discussion)


async def _run_discussion_async(discussion_id: str) -> None:
    """Run discussion in a dedicated thread pool to avoid blocking the event loop."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(_DISCUSSION_EXECUTOR, _run_discussion_sync, discussion_id)


@router.get("", response_model=DiscussionListResponse)
async def list_discussions(
    page: int = 1,
    limit: int = 20,
) -> DiscussionListResponse:
    """List all discussions with pagination.

    Returns a paginated list of discussions sorted by creation time (newest first).
    """
    offset = (page - 1) * limit

    # First, try to get from discussion memory (persistent storage)
    memory_discussions = _discussion_memory.list_all(offset=offset, limit=limit + 1)

    items = []
    for disc in memory_discussions[:limit]:
        items.append(
            DiscussionSummaryItem(
                id=disc.id,
                project_id=disc.project_id,
                topic=disc.topic,
                summary=disc.summary,
                message_count=len(disc.messages),
                created_at=disc.created_at.isoformat(),
                updated_at=disc.updated_at.isoformat(),
            )
        )

    # If memory has no results, also check in-memory state
    if not items:
        state_items = []
        with _state_lock:
            for disc_id, disc in _discussions.items():
                state_items.append(
                    DiscussionSummaryItem(
                        id=disc.id,
                        project_id="default",
                        topic=disc.topic,
                        summary=disc.result[:200] if disc.result else None,
                        message_count=0,
                        created_at=disc.created_at,
                        updated_at=disc.completed_at or disc.started_at or disc.created_at,
                    )
                )
        # Sort by created_at descending
        state_items.sort(key=lambda x: x.created_at, reverse=True)
        items = state_items[offset : offset + limit]

    has_more = len(memory_discussions) > limit or (not memory_discussions and len(items) == limit)

    return DiscussionListResponse(items=items, hasMore=has_more)


# ==============================================================================
# Global Discussion API (single active discussion for all users)
# ==============================================================================


@router.get("/current", response_model=GetDiscussionResponse | None)
async def get_current_discussion_api() -> GetDiscussionResponse | None:
    """Get the current global active discussion.

    Returns the current discussion if one exists, or None if no discussion is active.
    """
    discussion = get_current_discussion()
    if discussion is None:
        return None

    return GetDiscussionResponse(
        id=discussion.id,
        topic=discussion.topic,
        rounds=discussion.rounds,
        status=discussion.status,
        created_at=discussion.created_at,
        started_at=discussion.started_at,
        completed_at=discussion.completed_at,
        result=discussion.result,
        error=discussion.error,
        attachment=discussion.attachment,
        continued_from=discussion.continued_from,
        is_continuation=discussion.continued_from is not None,
    )


@router.post("/current", response_model=CreateCurrentDiscussionResponse)
async def create_current_discussion(
    request: CreateCurrentDiscussionRequest,
) -> CreateCurrentDiscussionResponse:
    """Create a new global discussion (replacing the current one).

    If a discussion is already running, returns it instead of creating a new one.
    The discussion is automatically started after creation.
    """
    with _current_discussion_lock:
        current = get_current_discussion()
        if current and current.status == DiscussionStatus.RUNNING:
            # Check if the discussion is stale (running for too long)
            is_stale = False
            if current.started_at:
                try:
                    started = datetime.fromisoformat(current.started_at)
                    elapsed = (datetime.utcnow() - started).total_seconds()
                    if elapsed > 1800:  # 30 minutes
                        is_stale = True
                except (ValueError, TypeError):
                    is_stale = True

            if is_stale:
                logger.warning(
                    "Marking stale discussion %s as failed (started_at=%s)",
                    current.id, current.started_at,
                )
                current.status = DiscussionStatus.FAILED
                current.error = "讨论超时，已自动标记为失败"
                current.completed_at = datetime.utcnow().isoformat()
                save_discussion_state(current)
                set_current_discussion(None)
            else:
                # Return the existing running discussion
                return CreateCurrentDiscussionResponse(
                    id=current.id,
                    topic=current.topic,
                    rounds=current.rounds,
                    status=current.status,
                    created_at=current.created_at,
                    message="讨论已在进行中，已自动加入",
                )

        # Create new discussion
        discussion_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        discussion = DiscussionState(
            id=discussion_id,
            topic=request.topic,
            rounds=request.rounds,
            auto_pause_interval=request.auto_pause_interval,
            status=DiscussionStatus.RUNNING,
            created_at=now,
            started_at=now,
            attachment=request.attachment,
        )

        # Save to both global state and persistent storage
        set_current_discussion(discussion)
        save_discussion_state(discussion)

    # Run in background (outside the lock)
    asyncio.create_task(_run_discussion_async(discussion_id))

    return CreateCurrentDiscussionResponse(
        id=discussion_id,
        topic=request.topic,
        rounds=request.rounds,
        status=DiscussionStatus.RUNNING,
        created_at=now,
        message=None,
    )


@router.post("/current/join", response_model=JoinDiscussionResponse)
async def join_current_discussion() -> JoinDiscussionResponse:
    """Join the current global discussion and get historical messages.

    Returns the current discussion state and all historical messages.
    If no discussion is active, returns empty data.
    """
    discussion = get_current_discussion()
    if discussion is None:
        return JoinDiscussionResponse(discussion=None, messages=[])

    # Load historical messages from memory
    stored = _discussion_memory.load(discussion.id)
    messages: list[MessageResponse] = []
    if stored and stored.messages:
        messages = [
            MessageResponse(
                id=msg.id,
                agent_id=msg.agent_id,
                agent_role=msg.agent_role,
                content=msg.content,
                timestamp=msg.timestamp.isoformat(),
            )
            for msg in stored.messages
        ]

    return JoinDiscussionResponse(
        discussion=GetDiscussionResponse(
            id=discussion.id,
            topic=discussion.topic,
            rounds=discussion.rounds,
            status=discussion.status,
            created_at=discussion.created_at,
            started_at=discussion.started_at,
            completed_at=discussion.completed_at,
            result=discussion.result,
            error=discussion.error,
            attachment=discussion.attachment,
            continued_from=discussion.continued_from,
            is_continuation=discussion.continued_from is not None,
        ),
        messages=messages,
    )


# ==============================================================================
# Original Discussion API (per-discussion operations)
# ==============================================================================


@router.post("", response_model=CreateDiscussionResponse)
async def create_discussion(request: CreateDiscussionRequest) -> CreateDiscussionResponse:
    """Create a new discussion.

    This creates a discussion in PENDING state. Call /start to begin the discussion.
    """
    discussion_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    discussion = DiscussionState(
        id=discussion_id,
        topic=request.topic,
        rounds=request.rounds,
        auto_pause_interval=request.auto_pause_interval,
        status=DiscussionStatus.PENDING,
        created_at=now,
        attachment=request.attachment,
    )
    save_discussion_state(discussion)

    return CreateDiscussionResponse(
        id=discussion_id,
        topic=request.topic,
        rounds=request.rounds,
        status=DiscussionStatus.PENDING,
        created_at=now,
    )


@router.get("/{discussion_id}", response_model=GetDiscussionResponse)
async def get_discussion(discussion_id: str) -> GetDiscussionResponse:
    """Get the status and result of a discussion."""
    discussion = get_discussion_state(discussion_id)
    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    return GetDiscussionResponse(
        id=discussion.id,
        topic=discussion.topic,
        rounds=discussion.rounds,
        status=discussion.status,
        created_at=discussion.created_at,
        started_at=discussion.started_at,
        completed_at=discussion.completed_at,
        result=discussion.result,
        error=discussion.error,
        attachment=discussion.attachment,
        continued_from=discussion.continued_from,
        is_continuation=discussion.continued_from is not None,
    )


@router.post("/{discussion_id}/start", response_model=StartDiscussionResponse)
async def start_discussion(
    discussion_id: str,
) -> StartDiscussionResponse:
    """Start a discussion.

    The discussion will run in the background. Poll GET /discussions/{id}
    to check the status and get the result.
    """
    discussion = get_discussion_state(discussion_id)
    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    if discussion.status != DiscussionStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Discussion cannot be started: current status is {discussion.status}",
        )

    # Mark as running before enqueuing to avoid duplicate starts.
    discussion.status = DiscussionStatus.RUNNING
    discussion.started_at = datetime.utcnow().isoformat()
    save_discussion_state(discussion)

    # Run in background
    asyncio.create_task(_run_discussion_async(discussion_id))

    return StartDiscussionResponse(
        id=discussion_id,
        status=DiscussionStatus.RUNNING,
        message="Discussion started. Poll GET /api/discussions/{id} for status.",
    )


def _generate_summary_sync(discussion_id: str, discussion: DiscussionState) -> SummaryResponse:
    """Generate a summary for a discussion synchronously.

    Args:
        discussion_id: The discussion ID.
        discussion: The discussion state.

    Returns:
        Generated SummaryResponse.
    """
    # Try to load discussion from memory first
    stored_discussion = _discussion_memory.load(discussion_id)

    if stored_discussion and stored_discussion.messages:
        # Use stored messages
        messages = stored_discussion.messages
    else:
        # Create mock messages from result if available
        messages = []
        if discussion.result:
            messages = [
                Message(
                    id="result",
                    agent_id="discussion",
                    agent_role="Discussion",
                    content=discussion.result,
                    timestamp=datetime.now(),
                )
            ]

    # Create a Discussion object for the summarizer
    disc = Discussion(
        id=discussion_id,
        project_id="default",
        topic=discussion.topic,
        messages=messages,
        created_at=datetime.fromisoformat(discussion.created_at.replace("Z", "+00:00"))
        if discussion.created_at
        else datetime.now(),
    )

    # Use summarizer to generate summary
    summarizer = Summarizer()
    task = summarizer.create_summary_task(disc)

    # Run the summarization
    crew = Crew(
        agents=[summarizer.build_agent()],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )

    result = crew.kickoff()
    raw_summary = str(result)

    # Parse the summary
    parsed = summarizer.parse_summary(raw_summary, disc)

    now = datetime.utcnow().isoformat()

    return SummaryResponse(
        discussion_id=discussion_id,
        topic=discussion.topic,
        summary=raw_summary,
        key_points=parsed.key_points,
        agreements=parsed.agreements,
        disagreements=parsed.disagreements,
        open_questions=parsed.open_questions,
        next_steps=parsed.next_steps,
        generated_at=now,
    )


@router.post("/{discussion_id}/summarize", response_model=SummaryResponse)
async def summarize_discussion(
    discussion_id: str,
    request: SummarizeRequest | None = None,
) -> SummaryResponse:
    """Generate a summary for a completed discussion.

    The discussion must be in COMPLETED state. Summaries are cached
    and can be regenerated with the regenerate flag.
    """
    discussion = get_discussion_state(discussion_id)
    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    if discussion.status != DiscussionStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Discussion cannot be summarized: current status is {discussion.status}",
        )

    # Check for cached summary
    regenerate = request.regenerate if request else False
    if not regenerate and discussion_id in _summaries:
        return _summaries[discussion_id]

    # Generate summary in executor to avoid blocking event loop
    import asyncio
    loop = asyncio.get_event_loop()
    summary = await loop.run_in_executor(
        None, _generate_summary_sync, discussion_id, discussion
    )
    _summaries[discussion_id] = summary

    # Also save to discussion memory
    stored_discussion = _discussion_memory.load(discussion_id)
    if stored_discussion:
        stored_discussion.summary = summary.summary
        _discussion_memory.save(stored_discussion)

    return summary


def _build_continuation_context(
    original: DiscussionState,
    stored: Discussion,
    follow_up: str,
    max_messages_per_agent: int = 2,
) -> str:
    """构建继续讨论的上下文。

    Args:
        original: 原讨论状态
        stored: 存储的讨论数据
        follow_up: 用户的追加问题/方向
        max_messages_per_agent: 每个角色保留的最近消息数量

    Returns:
        格式化的上下文字符串
    """
    context_parts = [
        "## 前序讨论上下文",
        "",
        f"### 原始话题: {original.topic}",
        "",
    ]

    # 添加摘要
    if stored.summary:
        context_parts.extend([
            "### 讨论总结",
            stored.summary[:2000],  # 限制长度
            "",
        ])

    # 提取每个角色的最后几条消息
    if stored.messages:
        context_parts.append("### 关键讨论内容")
        agent_messages: dict[str, list[str]] = {}
        for msg in stored.messages:
            if msg.agent_role not in agent_messages:
                agent_messages[msg.agent_role] = []
            agent_messages[msg.agent_role].append(msg.content[:500])

        for role, contents in agent_messages.items():
            # 取最后 N 条
            recent = contents[-max_messages_per_agent:]
            for content in recent:
                context_parts.append(f"**{role}**: {content}...")
        context_parts.append("")

    # 添加继续讨论部分
    context_parts.extend([
        "---",
        "",
        "## 继续讨论",
        "",
    ])
    if follow_up:
        context_parts.extend([
            "用户希望在以上讨论基础上，继续探讨以下问题：",
            "",
            f"**{follow_up}**",
        ])
    else:
        context_parts.append("用户希望在以上讨论基础上，继续深入探讨原话题。")

    return "\n".join(context_parts)


@router.post("/{discussion_id}/continue", response_model=ContinueDiscussionResponse)
async def continue_discussion(
    discussion_id: str,
    request: ContinueDiscussionRequest,
) -> ContinueDiscussionResponse:
    """Continue a completed discussion with a follow-up topic.

    Creates a new discussion that builds upon the original discussion's context.
    The new discussion will include the previous discussion's summary and decisions
    as context for the agents.
    """
    # Check if original discussion exists and is completed
    original = get_discussion_state(discussion_id)
    if original is None:
        raise HTTPException(status_code=404, detail="Original discussion not found")

    if original.status != DiscussionStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Can only continue completed discussions. Current status: {original.status}",
        )

    # Load the original discussion from memory to get full context
    stored_discussion = _discussion_memory.load(discussion_id)
    if stored_discussion is None:
        # Fall back to just using the result
        stored_discussion = Discussion(
            id=discussion_id,
            project_id="default",
            topic=original.topic,
            messages=[],
            summary=original.result,
            created_at=datetime.now(),
        )

    # 使用独立函数构建上下文
    combined_context = _build_continuation_context(
        original=original,
        stored=stored_discussion,
        follow_up=request.follow_up,
        max_messages_per_agent=2,
    )

    # Create new discussion with context
    new_discussion_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    if request.follow_up:
        combined_topic = f"[继续] {original.topic} - {request.follow_up[:50]}"
    else:
        combined_topic = f"[继续] {original.topic}"

    # Create attachment with context
    attachment = AttachmentInfo(
        filename="previous_discussion_context.md",
        content=combined_context,
    )

    new_discussion = DiscussionState(
        id=new_discussion_id,
        topic=combined_topic,
        rounds=request.rounds,
        status=DiscussionStatus.PENDING,
        created_at=now,
        attachment=attachment,
        continued_from=discussion_id,  # 记录原讨论 ID
    )
    save_discussion_state(new_discussion)

    # Auto-start the new discussion
    new_discussion.status = DiscussionStatus.RUNNING
    new_discussion.started_at = now
    save_discussion_state(new_discussion)

    # Run in background
    asyncio.create_task(_run_discussion_async(new_discussion_id))

    return ContinueDiscussionResponse(
        new_discussion_id=new_discussion_id,
        original_discussion_id=discussion_id,
        topic=combined_topic,
        status=DiscussionStatus.RUNNING,
        message="继续讨论已开始，新讨论将基于之前的上下文进行。",
    )


@router.get("/{discussion_id}/messages", response_model=DiscussionMessagesResponse)
async def get_discussion_messages(discussion_id: str) -> DiscussionMessagesResponse:
    """Get all messages for a discussion.

    Returns the discussion with all its messages for playback.
    """
    # First, try to load from persistent memory
    stored_discussion = _discussion_memory.load(discussion_id)

    if stored_discussion:
        return DiscussionMessagesResponse(
            discussion=DiscussionSummaryItem(
                id=stored_discussion.id,
                project_id=stored_discussion.project_id,
                topic=stored_discussion.topic,
                summary=stored_discussion.summary,
                message_count=len(stored_discussion.messages),
                created_at=stored_discussion.created_at.isoformat(),
                updated_at=stored_discussion.updated_at.isoformat(),
            ),
            messages=[
                MessageResponse(
                    id=msg.id,
                    agent_id=msg.agent_id,
                    agent_role=msg.agent_role,
                    content=msg.content,
                    timestamp=msg.timestamp.isoformat(),
                )
                for msg in stored_discussion.messages
            ],
        )

    # Fall back to in-memory state
    discussion = get_discussion_state(discussion_id)
    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    # For in-memory state, we don't have individual messages
    return DiscussionMessagesResponse(
        discussion=DiscussionSummaryItem(
            id=discussion.id,
            project_id="default",
            topic=discussion.topic,
            summary=discussion.result[:200] if discussion.result else None,
            message_count=1 if discussion.result else 0,
            created_at=discussion.created_at,
            updated_at=discussion.completed_at or discussion.started_at or discussion.created_at,
        ),
        messages=[
            MessageResponse(
                id="result",
                agent_id="discussion",
                agent_role="Discussion",
                content=discussion.result or "",
                timestamp=discussion.completed_at or discussion.created_at,
            )
        ]
        if discussion.result
        else [],
    )


@router.get("/{discussion_id}/summary", response_model=SummaryResponse)
async def get_discussion_summary(discussion_id: str) -> SummaryResponse:
    """Get the summary of a discussion.

    Returns the cached summary if available. Call POST /summarize first
    to generate a summary.
    """
    discussion = get_discussion_state(discussion_id)
    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    if discussion_id not in _summaries:
        # Try to load from memory
        stored_discussion = _discussion_memory.load(discussion_id)
        if stored_discussion and stored_discussion.summary:
            # Create response from stored summary
            return SummaryResponse(
                discussion_id=discussion_id,
                topic=discussion.topic,
                summary=stored_discussion.summary,
                key_points=[],
                agreements=[],
                disagreements=[],
                open_questions=[],
                next_steps=[],
                generated_at=stored_discussion.updated_at.isoformat()
                if stored_discussion.updated_at
                else datetime.utcnow().isoformat(),
            )
        raise HTTPException(
            status_code=404,
            detail="Summary not found. Call POST /api/discussions/{id}/summarize first.",
        )

    return _summaries[discussion_id]


# ==============================================================================
# Discussion Chain API
# ==============================================================================


class DiscussionChainItem(BaseModel):
    """讨论链中的单个讨论项。"""

    id: str
    topic: str
    summary: str | None = None
    status: DiscussionStatus
    created_at: str
    is_origin: bool = False  # 是否是链的起点


class DiscussionChainResponse(BaseModel):
    """讨论链响应。"""

    chain: list[DiscussionChainItem]  # 从最早到最新
    current_index: int  # 当前讨论在链中的位置


@router.get("/{discussion_id}/chain", response_model=DiscussionChainResponse)
async def get_discussion_chain(discussion_id: str) -> DiscussionChainResponse:
    """获取讨论链（原讨论 → 续前讨论 → ...）。

    返回从最早的原始讨论到当前讨论的完整链。
    """
    # 首先检查讨论是否存在
    current = get_discussion_state(discussion_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    chain: list[DiscussionChainItem] = []
    visited: set[str] = set()

    # 向前追溯到原始讨论
    trace_id: str | None = discussion_id
    while trace_id and trace_id not in visited:
        visited.add(trace_id)
        disc = get_discussion_state(trace_id)
        if disc is None:
            break

        # 尝试获取摘要
        stored = _discussion_memory.load(trace_id)
        summary = stored.summary if stored else None

        chain.insert(
            0,
            DiscussionChainItem(
                id=disc.id,
                topic=disc.topic,
                summary=summary,
                status=disc.status,
                created_at=disc.created_at,
                is_origin=disc.continued_from is None,
            ),
        )
        trace_id = disc.continued_from

    # 计算当前讨论在链中的位置
    current_index = 0
    for i, item in enumerate(chain):
        if item.id == discussion_id:
            current_index = i
            break

    return DiscussionChainResponse(chain=chain, current_index=current_index)


# ==============================================================================
# Agenda API Models
# ==============================================================================


class AgendaItemResponse(BaseModel):
    """Response model for a single agenda item."""

    id: str
    title: str
    description: str | None
    status: str
    summary: str | None
    summary_details: dict[str, Any] | None = None
    started_at: str | None = None
    completed_at: str | None = None


class AgendaResponse(BaseModel):
    """Response model for the full agenda."""

    items: list[AgendaItemResponse]
    current_index: int


class AddAgendaItemRequest(BaseModel):
    """Request body for adding a new agenda item."""

    title: str = Field(..., min_length=1, max_length=100, description="议题标题")
    description: str | None = Field(default=None, max_length=500, description="议题描述")


class AddAgendaItemResponse(BaseModel):
    """Response for adding a new agenda item."""

    item: AgendaItemResponse
    message: str


class AgendaItemSummaryResponse(BaseModel):
    """Response for getting an agenda item summary."""

    item_id: str
    title: str
    summary: str | None
    summary_details: dict[str, Any] | None = None


# In-memory storage for agendas (keyed by discussion_id)
_discussion_agendas: dict[str, Agenda] = {}
_agenda_lock = threading.Lock()


def get_discussion_agenda(discussion_id: str) -> Agenda | None:
    """Get the agenda for a discussion.

    Args:
        discussion_id: The discussion ID.

    Returns:
        The Agenda or None if not found.
    """
    with _agenda_lock:
        return _discussion_agendas.get(discussion_id)


def set_discussion_agenda(discussion_id: str, agenda: Agenda) -> None:
    """Set the agenda for a discussion.

    Args:
        discussion_id: The discussion ID.
        agenda: The Agenda to store.
    """
    with _agenda_lock:
        _discussion_agendas[discussion_id] = agenda


def _agenda_item_to_response(item: AgendaItem) -> AgendaItemResponse:
    """Convert an AgendaItem to its response model."""
    return AgendaItemResponse(
        id=item.id,
        title=item.title,
        description=item.description,
        status=item.status.value,
        summary=item.summary,
        summary_details=item.summary_details.model_dump() if item.summary_details else None,
        started_at=item.started_at.isoformat() if item.started_at else None,
        completed_at=item.completed_at.isoformat() if item.completed_at else None,
    )


# ==============================================================================
# Agenda API Endpoints
# ==============================================================================


@router.get("/current/agenda", response_model=AgendaResponse | None)
async def get_current_agenda() -> AgendaResponse | None:
    """获取当前讨论的议程。

    Returns:
        当前讨论的议程，如果没有活跃讨论则返回 None。
    """
    discussion = get_current_discussion()
    if discussion is None:
        raise HTTPException(status_code=404, detail="无活跃讨论")

    agenda = get_discussion_agenda(discussion.id)
    if agenda is None:
        # Return empty agenda if not initialized
        return AgendaResponse(items=[], current_index=0)

    return AgendaResponse(
        items=[_agenda_item_to_response(item) for item in agenda.items],
        current_index=agenda.current_index,
    )


@router.post("/current/agenda/items", response_model=AddAgendaItemResponse)
async def add_agenda_item(request: AddAgendaItemRequest) -> AddAgendaItemResponse:
    """添加新议题（主策划动态添加）。

    Args:
        request: 包含议题标题和描述的请求体。

    Returns:
        新添加的议题信息。
    """
    discussion = get_current_discussion()
    if discussion is None:
        raise HTTPException(status_code=404, detail="无活跃讨论")

    agenda = get_discussion_agenda(discussion.id)
    if agenda is None:
        # Initialize agenda if not exists
        agenda = Agenda()
        set_discussion_agenda(discussion.id, agenda)

    item = agenda.add_item(title=request.title, description=request.description)
    set_discussion_agenda(discussion.id, agenda)

    return AddAgendaItemResponse(
        item=_agenda_item_to_response(item),
        message=f"已添加议题: {item.title}",
    )


@router.post("/current/agenda/items/{item_id}/skip", response_model=AgendaItemResponse)
async def skip_agenda_item(item_id: str) -> AgendaItemResponse:
    """跳过某个议题。

    Args:
        item_id: 要跳过的议题 ID。

    Returns:
        被跳过的议题信息。
    """
    discussion = get_current_discussion()
    if discussion is None:
        raise HTTPException(status_code=404, detail="无活跃讨论")

    agenda = get_discussion_agenda(discussion.id)
    if agenda is None:
        raise HTTPException(status_code=404, detail="议程未初始化")

    item = agenda.skip_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="议题未找到或无法跳过")

    set_discussion_agenda(discussion.id, agenda)
    return _agenda_item_to_response(item)


@router.get("/current/agenda/items/{item_id}/summary", response_model=AgendaItemSummaryResponse)
async def get_agenda_item_summary(item_id: str) -> AgendaItemSummaryResponse:
    """获取议题小结。

    Args:
        item_id: 议题 ID。

    Returns:
        议题的小结内容。
    """
    discussion = get_current_discussion()
    if discussion is None:
        raise HTTPException(status_code=404, detail="无活跃讨论")

    agenda = get_discussion_agenda(discussion.id)
    if agenda is None:
        raise HTTPException(status_code=404, detail="议程未初始化")

    item = agenda.get_item_by_id(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="议题未找到")

    if item.status != AgendaItemStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="议题尚未完成，无法获取小结")

    return AgendaItemSummaryResponse(
        item_id=item.id,
        title=item.title,
        summary=item.summary,
        summary_details=item.summary_details.model_dump() if item.summary_details else None,
    )
