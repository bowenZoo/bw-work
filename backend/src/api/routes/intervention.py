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
from src.memory.discussion_memory import DiscussionMemory

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

    if discussion.status not in (DiscussionStatus.RUNNING, DiscussionStatus.WAITING_DECISION):
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
            agent_role="制作人",
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


# ------------------------------------------------------------------
# DYN-5.1: Agenda & Doc-Plan manipulation endpoints
# ------------------------------------------------------------------


class AgendaPriorityRequest(BaseModel):
    """Request body for adjusting agenda item priority."""

    priority: int = Field(ge=-1, le=1, description="Priority: -1=low, 0=normal, 1=high")


class DocRestructureRequest(BaseModel):
    """Request body for manual doc-plan restructure."""

    operation: str = Field(..., description="Operation: add_section | add_file")
    params: dict = Field(..., description="Operation parameters")


def _get_crew_instance(discussion_id: str):
    """Get the DiscussionCrew instance for a running discussion.

    Returns the crew and its agenda/doc_plan if available.
    """
    from src.api.routes.discussion import _running_crews
    crew = _running_crews.get(discussion_id)
    return crew


@router.post("/{discussion_id}/agenda/items/{item_id}/complete")
async def complete_agenda_item(discussion_id: str, item_id: str) -> dict:
    """Manually mark an agenda item as completed."""
    discussion = get_discussion_state(discussion_id)
    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    crew = _get_crew_instance(discussion_id)
    if crew is None:
        raise HTTPException(status_code=400, detail="Discussion crew not available")

    agenda = crew.get_agenda()
    if agenda is None:
        raise HTTPException(status_code=400, detail="No agenda available for this discussion")

    item = agenda.get_item_by_id(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Agenda item {item_id} not found")

    from src.models.agenda import AgendaItemStatus
    if item.status == AgendaItemStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Item is already completed")

    item.complete("手动标记完结")
    return {
        "discussion_id": discussion_id,
        "item_id": item_id,
        "status": "completed",
        "message": f"议题「{item.title}」已标记完结",
    }


@router.post("/{discussion_id}/agenda/items/{item_id}/priority")
async def set_agenda_item_priority(
    discussion_id: str,
    item_id: str,
    request: AgendaPriorityRequest,
) -> dict:
    """Adjust agenda item priority."""
    discussion = get_discussion_state(discussion_id)
    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    crew = _get_crew_instance(discussion_id)
    if crew is None:
        raise HTTPException(status_code=400, detail="Discussion crew not available")

    agenda = crew.get_agenda()
    if agenda is None:
        raise HTTPException(status_code=400, detail="No agenda available for this discussion")

    item = agenda.get_item_by_id(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Agenda item {item_id} not found")

    item.priority = request.priority
    priority_label = {-1: "low", 0: "normal", 1: "high"}.get(request.priority, "unknown")
    return {
        "discussion_id": discussion_id,
        "item_id": item_id,
        "priority": request.priority,
        "message": f"议题「{item.title}」优先级已调整为 {priority_label}",
    }


@router.post("/{discussion_id}/doc-plan/restructure")
async def restructure_doc_plan(
    discussion_id: str,
    request: DocRestructureRequest,
) -> dict:
    """Manually restructure the document plan.

    Supported operations:
    - add_section: params={file_index, after_section_id, title, description}
    - add_file: params={filename, title, sections: [{title, description}]}
    """
    from src.models.doc_plan import SectionPlan, FilePlan

    discussion = get_discussion_state(discussion_id)
    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    crew = _get_crew_instance(discussion_id)
    if crew is None:
        raise HTTPException(status_code=400, detail="Discussion crew not available")

    doc_plan = crew._doc_plan
    if doc_plan is None:
        raise HTTPException(status_code=400, detail="No doc plan available for this discussion")

    operation = request.operation
    params = request.params

    if operation == "add_section":
        file_index = params.get("file_index", 0)
        after_sid = params.get("after_section_id")
        title = params.get("title", "新章节")
        description = params.get("description", "")

        # Generate section ID
        max_id = max(
            (int(s.id.lstrip("s")) for f in doc_plan.files for s in f.sections
             if s.id.startswith("s") and s.id[1:].isdigit()),
            default=0,
        )
        new_sid = f"s{max_id + 1}"
        new_section = SectionPlan(id=new_sid, title=title, description=description)

        if not doc_plan.add_section(file_index, new_section, after_sid):
            raise HTTPException(status_code=400, detail="Failed to add section")

        # Update file if doc_writer available
        if crew._doc_writer and file_index < len(doc_plan.files):
            crew._doc_writer.add_section_marker(
                doc_plan.files[file_index].filename,
                new_sid, title, description,
                after_section_id=after_sid,
            )

        return {
            "discussion_id": discussion_id,
            "operation": "add_section",
            "section_id": new_sid,
            "message": f"新增章节「{title}」(ID: {new_sid})",
        }

    elif operation == "add_file":
        filename = params.get("filename", "新文件.md")
        file_title = params.get("title", "新文件")
        sections_data = params.get("sections", [])

        max_id = max(
            (int(s.id.lstrip("s")) for f in doc_plan.files for s in f.sections
             if s.id.startswith("s") and s.id[1:].isdigit()),
            default=0,
        )
        new_sections = []
        for s_data in sections_data:
            max_id += 1
            new_sections.append(SectionPlan(
                id=f"s{max_id}",
                title=s_data.get("title", "章节"),
                description=s_data.get("description", ""),
            ))

        new_fp = FilePlan(filename=filename, title=file_title, sections=new_sections)
        if not doc_plan.add_file(new_fp):
            raise HTTPException(status_code=400, detail=f"Filename conflict: {filename}")
        if crew._doc_writer:
            crew._doc_writer.create_new_file(new_fp)

        return {
            "discussion_id": discussion_id,
            "operation": "add_file",
            "filename": filename,
            "sections": [s.id for s in new_sections],
            "message": f"新增文件「{filename}」({len(new_sections)} 个章节)",
        }

    else:
        raise HTTPException(status_code=400, detail=f"Unknown operation: {operation}")
