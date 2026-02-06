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
from src.crew.discussion_crew import DiscussionCrew
from src.memory.base import Discussion, Message
from src.memory.discussion_memory import DiscussionMemory

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
    rounds: int = Field(default=3, ge=1, le=10, description="Number of discussion rounds")
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
    status: DiscussionStatus
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    result: str | None = None
    error: str | None = None
    attachment: AttachmentInfo | None = None


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

    follow_up: str = Field(..., min_length=1, description="Follow-up topic or question to continue discussing")
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


def _state_path(discussion_id: str) -> Path:
    return _STATE_DIR / f"{discussion_id}.json"


def _persist_discussion_state(discussion: DiscussionState) -> None:
    try:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        _state_path(discussion.id).write_text(
            json.dumps(discussion.model_dump(), ensure_ascii=True),
            encoding="utf-8",
        )
    except Exception:
        # Persistence failures should not block API flow
        pass


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


def _run_discussion_sync(discussion_id: str) -> None:
    """Run a discussion synchronously (for background task)."""
    discussion = get_discussion_state(discussion_id)
    if discussion is None:
        return

    try:
        if discussion.started_at is None:
            # Defensive: allow direct invocation without /start setting status.
            discussion.status = DiscussionStatus.RUNNING
            discussion.started_at = datetime.utcnow().isoformat()
            save_discussion_state(discussion)

        # Get LLM from admin config store
        llm = _get_llm_from_config()
        if llm is None:
            raise RuntimeError("LLM not configured. Please configure OpenAI API key in admin panel.")

        crew = DiscussionCrew(discussion_id=discussion_id, llm=llm)
        result = crew.run(
            topic=discussion.topic,
            rounds=discussion.rounds,
            verbose=False,
            attachment=discussion.attachment.content if discussion.attachment else None,
        )

        discussion.result = result
        discussion.status = DiscussionStatus.COMPLETED
        discussion.completed_at = datetime.utcnow().isoformat()
        save_discussion_state(discussion)
    except Exception as e:
        discussion.status = DiscussionStatus.FAILED
        discussion.error = str(e)
        discussion.completed_at = datetime.utcnow().isoformat()
        save_discussion_state(discussion)


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

    # Generate summary
    summary = _generate_summary_sync(discussion_id, discussion)
    _summaries[discussion_id] = summary

    # Also save to discussion memory
    stored_discussion = _discussion_memory.load(discussion_id)
    if stored_discussion:
        stored_discussion.summary = summary.summary
        _discussion_memory.save(stored_discussion)

    return summary


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

    # Build context from original discussion
    context_parts = [
        f"## 前序讨论上下文",
        f"",
        f"### 原始话题: {original.topic}",
        f"",
    ]

    # Add summary if available
    if stored_discussion.summary:
        context_parts.extend([
            "### 讨论总结",
            stored_discussion.summary[:2000],  # Limit context size
            "",
        ])

    # Add key messages (last few messages from each agent)
    if stored_discussion.messages:
        context_parts.append("### 关键讨论内容")
        agent_last_messages: dict[str, str] = {}
        for msg in stored_discussion.messages:
            agent_last_messages[msg.agent_role] = msg.content[:500]

        for role, content in agent_last_messages.items():
            context_parts.append(f"**{role}**: {content}...")
        context_parts.append("")

    context_parts.extend([
        "---",
        "",
        f"## 继续讨论",
        f"",
        f"用户希望在以上讨论基础上，继续探讨以下问题：",
        f"",
        f"**{request.follow_up}**",
    ])

    combined_context = "\n".join(context_parts)

    # Create new discussion with context
    new_discussion_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    combined_topic = f"[继续] {original.topic} - {request.follow_up[:50]}"

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
