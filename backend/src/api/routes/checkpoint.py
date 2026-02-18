"""Checkpoint API routes for decision management and producer messaging."""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.api.routes.discussion import DiscussionStatus, get_discussion_state
from src.api.websocket.events import create_message_event
from src.api.websocket.manager import broadcast_sync
from src.memory.discussion_memory import DiscussionMemory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/discussions", tags=["checkpoint"])

_discussion_memory = DiscussionMemory()


def _get_crew_instance(discussion_id: str):
    """Get the DiscussionCrew instance for a running discussion."""
    from src.api.routes.discussion import _running_crews
    return _running_crews.get(discussion_id)


# ------------------------------------------------------------------
# Checkpoint respond API
# ------------------------------------------------------------------


class CheckpointRespondRequest(BaseModel):
    """Request body for responding to a DECISION checkpoint."""

    option_id: str | None = Field(default=None, description="Selected option ID (A/B/C/D)")
    free_input: str | None = Field(default=None, description="Free text input")


class CheckpointRespondResponse(BaseModel):
    """Response for checkpoint respond."""

    checkpoint_id: str
    status: str
    message: str


@router.post("/{discussion_id}/checkpoint/{checkpoint_id}/respond", response_model=CheckpointRespondResponse)
async def respond_to_checkpoint(
    discussion_id: str,
    checkpoint_id: str,
    request: CheckpointRespondRequest,
) -> CheckpointRespondResponse:
    """Respond to a DECISION checkpoint.

    The discussion must be in WAITING_DECISION state. After responding,
    the lead planner will announce the decision and resume discussion.
    """
    discussion = get_discussion_state(discussion_id)
    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    if discussion.status != DiscussionStatus.WAITING_DECISION:
        raise HTTPException(
            status_code=400,
            detail=f"Discussion is not waiting for a decision: status is {discussion.status}",
        )

    if not request.option_id and not request.free_input:
        raise HTTPException(status_code=400, detail="Must provide option_id or free_input")

    crew = _get_crew_instance(discussion_id)
    if crew is None:
        raise HTTPException(status_code=400, detail="Discussion crew not available")

    success = crew.respond_to_checkpoint(
        checkpoint_id=checkpoint_id,
        option_id=request.option_id,
        free_input=request.free_input,
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Checkpoint {checkpoint_id} not found or not pending",
        )

    return CheckpointRespondResponse(
        checkpoint_id=checkpoint_id,
        status="responded",
        message="决策已记录，主策划将宣布并继续讨论",
    )


# ------------------------------------------------------------------
# Get checkpoints API
# ------------------------------------------------------------------


@router.get("/{discussion_id}/checkpoints")
async def get_checkpoints(discussion_id: str) -> dict:
    """Get all checkpoints for a discussion.

    Returns checkpoints from persisted discussion data, ordered by creation time (newest first).
    """
    discussion = get_discussion_state(discussion_id)
    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    # Try to get from running crew first (has latest data)
    crew = _get_crew_instance(discussion_id)
    if crew and crew._current_discussion:
        checkpoints = list(crew._current_discussion.checkpoints)
    else:
        # Fall back to persisted data
        stored = _discussion_memory.load(discussion_id)
        if stored:
            checkpoints = list(stored.checkpoints)
        else:
            checkpoints = []

    # Newest first
    checkpoints.reverse()

    return {"checkpoints": checkpoints}


# ------------------------------------------------------------------
# Producer message API
# ------------------------------------------------------------------


class ProducerMessageRequest(BaseModel):
    """Request body for sending a producer message."""

    content: str = Field(..., min_length=1, description="Producer message content")


class ProducerMessageResponse(BaseModel):
    """Response for producer message."""

    status: str
    message: str


@router.post("/{discussion_id}/producer-message", response_model=ProducerMessageResponse)
async def send_producer_message(
    discussion_id: str,
    request: ProducerMessageRequest,
) -> ProducerMessageResponse:
    """Send a producer message during a discussion.

    Single-step replacement for the pause/inject/resume flow.
    The message is queued and processed by the lead planner at the next round boundary.
    """
    discussion = get_discussion_state(discussion_id)
    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    if discussion.status not in (DiscussionStatus.RUNNING, DiscussionStatus.WAITING_DECISION):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot send message: discussion status is {discussion.status}",
        )

    crew = _get_crew_instance(discussion_id)
    if crew is None:
        raise HTTPException(status_code=400, detail="Discussion crew not available")

    crew.add_producer_message(request.content)

    # Broadcast the producer message to WebSocket so it appears in chat immediately
    try:
        event = create_message_event(
            discussion_id=discussion_id,
            agent_id="producer",
            agent_role="制作人",
            content=request.content,
        )
        broadcast_sync(event.to_dict(), discussion_id=discussion_id)
    except Exception as exc:
        logger.debug("Failed to broadcast producer message: %s", exc)

    return ProducerMessageResponse(
        status="received",
        message="消息已收到，主策划将在当前发言结束后处理",
    )
