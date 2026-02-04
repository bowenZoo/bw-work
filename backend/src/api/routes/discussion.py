"""Discussion API routes."""
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from src.crew.discussion_crew import DiscussionCrew

router = APIRouter(prefix="/api/discussions", tags=["discussions"])


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


# NOTE: In-memory storage is per-process and resets on restart.
# This is a temporary scaffold until persistent storage is added.
_discussions: dict[str, DiscussionState] = {}


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
