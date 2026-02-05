"""Discussion API routes."""
import uuid
from datetime import datetime
from enum import Enum

from crewai import Crew, Process
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from src.agents import Summarizer
from src.crew.discussion_crew import DiscussionCrew
from src.memory.base import Discussion, Message
from src.memory.discussion_memory import DiscussionMemory

router = APIRouter(prefix="/api/discussions", tags=["discussions"])

# Memory storage for summaries
_discussion_memory = DiscussionMemory(data_dir="data/projects")


class DiscussionStatus(str, Enum):
    """Status of a discussion."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class CreateDiscussionRequest(BaseModel):
    """Request body for creating a discussion."""

    topic: str = Field(..., min_length=1, description="The discussion topic")
    rounds: int = Field(default=3, ge=1, le=10, description="Number of discussion rounds")


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


# NOTE: In-memory storage is per-process and resets on restart.
# This is a temporary scaffold until persistent storage is added.
_discussions: dict[str, DiscussionState] = {}

# Store generated summaries
_summaries: dict[str, SummaryResponse] = {}


def _run_discussion_sync(discussion_id: str) -> None:
    """Run a discussion synchronously (for background task)."""
    discussion = _discussions.get(discussion_id)
    if discussion is None:
        return

    try:
        if discussion.started_at is None:
            # Defensive: allow direct invocation without /start setting status.
            discussion.status = DiscussionStatus.RUNNING
            discussion.started_at = datetime.utcnow().isoformat()

        crew = DiscussionCrew(discussion_id=discussion_id)
        result = crew.run(
            topic=discussion.topic,
            rounds=discussion.rounds,
            verbose=False,
        )

        discussion.result = result
        discussion.status = DiscussionStatus.COMPLETED
        discussion.completed_at = datetime.utcnow().isoformat()
    except Exception as e:
        discussion.status = DiscussionStatus.FAILED
        discussion.error = str(e)
        discussion.completed_at = datetime.utcnow().isoformat()


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
    )
    _discussions[discussion_id] = discussion

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
    discussion = _discussions.get(discussion_id)
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
    background_tasks: BackgroundTasks,
) -> StartDiscussionResponse:
    """Start a discussion.

    The discussion will run in the background. Poll GET /discussions/{id}
    to check the status and get the result.
    """
    discussion = _discussions.get(discussion_id)
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

    # Run in background
    background_tasks.add_task(_run_discussion_sync, discussion_id)

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
    discussion = _discussions.get(discussion_id)
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


@router.get("/{discussion_id}/summary", response_model=SummaryResponse)
async def get_discussion_summary(discussion_id: str) -> SummaryResponse:
    """Get the summary of a discussion.

    Returns the cached summary if available. Call POST /summarize first
    to generate a summary.
    """
    discussion = _discussions.get(discussion_id)
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
