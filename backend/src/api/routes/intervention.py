"""Intervention API routes for human-in-the-loop functionality."""

import logging
from datetime import datetime
from enum import Enum

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.api.routes.discussion import DiscussionStatus, get_discussion_state
from src.api.websocket.events import create_message_event
from src.api.websocket.manager import global_connection_manager
from src.crew.discussion_crew import (
    DiscussionState,
    add_injected_message,
    get_discussion_state as get_crew_state,
    set_discussion_state as set_crew_state,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/discussions", tags=["intervention"])


class InterventionStatus(str, Enum):
    """Status of an intervention operation."""

    SUCCESS = "success"
    FAILED = "failed"


class PauseResponse(BaseModel):
    """Response for pausing a discussion."""

    id: str
    status: str
    message: str
    paused_at: str


class InjectMessageRequest(BaseModel):
    """Request body for injecting a user message."""

    content: str = Field(..., min_length=1, description="The user's message to inject")


class InjectMessageResponse(BaseModel):
    """Response for injecting a message."""

    id: str
    status: InterventionStatus
    message: str
    injected_at: str


class ResumeResponse(BaseModel):
    """Response for resuming a discussion."""

    id: str
    status: str
    message: str
    resumed_at: str


@router.post("/{discussion_id}/pause", response_model=PauseResponse)
async def pause_discussion(discussion_id: str) -> PauseResponse:
    """Pause a running discussion.

    The discussion must be in RUNNING state. Once paused, users can
    inject messages before resuming. The pause takes effect at the next
    agent turn boundary.
    """
    discussion = get_discussion_state(discussion_id)
    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    if discussion.status != DiscussionStatus.RUNNING:
        raise HTTPException(
            status_code=400,
            detail=f"Discussion cannot be paused: current status is {discussion.status}",
        )

    # Get current crew state
    state_info = get_crew_state(discussion_id)
    if state_info is not None and state_info["state"] == DiscussionState.PAUSED:
        raise HTTPException(
            status_code=400,
            detail="Discussion is already paused",
        )

    now = datetime.utcnow().isoformat()

    # Request pause through the crew's state management
    set_crew_state(discussion_id, DiscussionState.PAUSED)

    return PauseResponse(
        id=discussion_id,
        status="paused",
        message="Pause requested. Discussion will pause at the next agent turn boundary.",
        paused_at=now,
    )


@router.post("/{discussion_id}/inject", response_model=InjectMessageResponse)
async def inject_message(
    discussion_id: str,
    request: InjectMessageRequest,
) -> InjectMessageResponse:
    """Inject a user message into a paused discussion.

    The injected message will be included as context when the discussion
    resumes, allowing human input to guide the agents' responses.
    """
    discussion = get_discussion_state(discussion_id)
    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    state_info = get_crew_state(discussion_id)
    if state_info is None or state_info["state"] != DiscussionState.PAUSED:
        raise HTTPException(
            status_code=400,
            detail="Discussion is not paused. Call /pause first.",
        )

    now = datetime.utcnow().isoformat()

    # Create injected message following the spec format
    injected_message = {
        "role": "user",
        "content": request.content,
        "source": "intervention",
        "timestamp": now,
        "save_to_memory": True,
    }

    add_injected_message(discussion_id, injected_message)

    # Broadcast user message to WebSocket so it appears in chat
    try:
        event = create_message_event(
            discussion_id=discussion_id,
            agent_id="user",
            agent_role="用户",
            content=request.content,
        )
        import asyncio
        asyncio.ensure_future(
            global_connection_manager.broadcast(event.to_dict())
        )
    except Exception as exc:
        logger.debug("Failed to broadcast user message: %s", exc)

    # Get updated count
    state_info = get_crew_state(discussion_id)
    msg_count = len(state_info.get("injected_messages", [])) if state_info else 1

    return InjectMessageResponse(
        id=discussion_id,
        status=InterventionStatus.SUCCESS,
        message=f"Message injected. {msg_count} message(s) queued.",
        injected_at=now,
    )


@router.post("/{discussion_id}/resume", response_model=ResumeResponse)
async def resume_discussion(discussion_id: str) -> ResumeResponse:
    """Resume a paused discussion.

    If messages were injected while paused, they will be incorporated
    into the discussion context when agents continue.
    """
    discussion = get_discussion_state(discussion_id)
    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    state_info = get_crew_state(discussion_id)
    if state_info is None or state_info["state"] != DiscussionState.PAUSED:
        raise HTTPException(
            status_code=400,
            detail="Discussion is not paused.",
        )

    now = datetime.utcnow().isoformat()

    # Get injected messages count for response
    injected_count = len(state_info.get("injected_messages", []))

    # Resume the discussion through the crew's state management
    set_crew_state(discussion_id, DiscussionState.RUNNING)

    return ResumeResponse(
        id=discussion_id,
        status="running",
        message=f"Discussion resumed with {injected_count} injected message(s).",
        resumed_at=now,
    )


@router.get("/{discussion_id}/intervention-status")
async def get_intervention_status(discussion_id: str) -> dict:
    """Get the intervention status of a discussion.

    Returns information about whether the discussion is paused and
    any queued injected messages.
    """
    discussion = get_discussion_state(discussion_id)
    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    state_info = get_crew_state(discussion_id)

    is_paused = state_info is not None and state_info["state"] == DiscussionState.PAUSED

    return {
        "discussion_id": discussion_id,
        "is_paused": is_paused,
        "crew_state": state_info["state"].value if state_info else None,
        "injected_messages_count": len(state_info.get("injected_messages", [])) if state_info else 0,
        "discussion_status": discussion.status,
    }
