"""Design documents API routes - organized discussion outputs."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.agents.doc_organizer import DocOrganizer
from src.api.routes.discussion import (
    DiscussionStatus,
    _discussion_memory,
    get_discussion_state,
)
from src.memory.base import Discussion, Message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/discussions", tags=["design-docs"])

_ORGANIZE_EXECUTOR = ThreadPoolExecutor(max_workers=2)


# ============================================================
# Response Models
# ============================================================


class DesignDocItem(BaseModel):
    """Single design document info."""

    filename: str
    title: str
    size: int
    created_at: str


class DesignDocsListResponse(BaseModel):
    """Response for listing design documents."""

    discussion_id: str
    topic: str
    files: list[DesignDocItem] = Field(default_factory=list)
    created_at: str | None = None


class DesignDocContentResponse(BaseModel):
    """Response for a single design document's content."""

    filename: str
    title: str
    content: str


class OrganizeResponse(BaseModel):
    """Response for triggering document organization."""

    discussion_id: str
    status: str
    file_count: int
    files: list[DesignDocItem] = Field(default_factory=list)
    message: str


# ============================================================
# Helper functions
# ============================================================


def _get_llm() -> Any | None:
    """Get LLM from admin config (reuse discussion route's helper)."""
    from src.api.routes.discussion import _get_llm_from_config
    return _get_llm_from_config()


def _load_discussion_for_organize(discussion_id: str) -> Discussion:
    """Load a discussion with messages for organizing.

    Raises HTTPException if not found or not completed.
    """
    state = get_discussion_state(discussion_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    if state.status not in (DiscussionStatus.COMPLETED, DiscussionStatus.FAILED):
        raise HTTPException(
            status_code=400,
            detail=f"只能整理已完成的讨论 (当前状态: {state.status.value})",
        )

    # Load full discussion with messages
    stored = _discussion_memory.load(discussion_id)
    if stored and stored.messages:
        return stored

    # Fallback: create from state result
    from datetime import datetime

    messages = []
    if state.result:
        messages = [
            Message(
                id="result",
                agent_id="discussion",
                agent_role="Discussion",
                content=state.result,
                timestamp=datetime.now(),
            )
        ]

    return Discussion(
        id=discussion_id,
        project_id="default",
        topic=state.topic,
        messages=messages,
        summary=state.result,
        created_at=datetime.fromisoformat(state.created_at) if state.created_at else datetime.now(),
    )


def _run_organize_sync(discussion_id: str) -> OrganizeResponse:
    """Run document organization synchronously (for executor)."""
    discussion = _load_discussion_for_organize(discussion_id)

    llm = _get_llm()
    if llm is None:
        raise HTTPException(status_code=500, detail="LLM 未配置")

    organizer = DocOrganizer(llm=llm)
    result = organizer.run_organize(discussion)

    return OrganizeResponse(
        discussion_id=discussion_id,
        status="completed",
        file_count=len(result.files),
        files=[
            DesignDocItem(
                filename=f.filename,
                title=f.title,
                size=len(f.content.encode("utf-8")),
                created_at=result.created_at.isoformat(),
            )
            for f in result.files
        ],
        message=f"已生成 {len(result.files)} 个策划文档",
    )


# ============================================================
# API Endpoints
# ============================================================


@router.post("/{discussion_id}/organize", response_model=OrganizeResponse)
async def organize_discussion(discussion_id: str) -> OrganizeResponse:
    """Trigger document organization for a completed discussion.

    Uses LLM to analyze the discussion and generate structured design documents.
    This runs in a thread pool to avoid blocking the event loop.
    """
    # Validate discussion exists and is completed (fast check before executor)
    state = get_discussion_state(discussion_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Discussion not found")
    if state.status not in (DiscussionStatus.COMPLETED, DiscussionStatus.FAILED):
        raise HTTPException(
            status_code=400,
            detail=f"只能整理已完成的讨论 (当前状态: {state.status.value})",
        )

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(_ORGANIZE_EXECUTOR, _run_organize_sync, discussion_id)
    return result


@router.get("/{discussion_id}/design-docs", response_model=DesignDocsListResponse)
async def list_design_docs(discussion_id: str) -> DesignDocsListResponse:
    """List all organized design documents for a discussion."""
    state = get_discussion_state(discussion_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    organizer = DocOrganizer()
    index = organizer.load_index("default", discussion_id)

    if index is None:
        return DesignDocsListResponse(
            discussion_id=discussion_id,
            topic=state.topic,
            files=[],
            created_at=None,
        )

    return DesignDocsListResponse(
        discussion_id=discussion_id,
        topic=index.get("topic", state.topic),
        files=[
            DesignDocItem(
                filename=f["filename"],
                title=f["title"],
                size=f.get("size", 0),
                created_at=f.get("created_at", ""),
            )
            for f in index.get("files", [])
        ],
        created_at=index.get("created_at"),
    )


@router.get("/{discussion_id}/design-docs/{filename}", response_model=DesignDocContentResponse)
async def get_design_doc(discussion_id: str, filename: str) -> DesignDocContentResponse:
    """Get the content of a single design document."""
    state = get_discussion_state(discussion_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    organizer = DocOrganizer()

    # Get title from index
    index = organizer.load_index("default", discussion_id)
    title = filename
    if index:
        for f in index.get("files", []):
            if f["filename"] == filename:
                title = f.get("title", filename)
                break

    content = organizer.load_document("default", discussion_id, filename)
    if content is None:
        raise HTTPException(status_code=404, detail="Document not found")

    return DesignDocContentResponse(
        filename=filename,
        title=title,
        content=content,
    )
