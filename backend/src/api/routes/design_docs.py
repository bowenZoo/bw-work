"""Design documents API routes - organized discussion outputs."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
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


def _get_realtime_docs_dir(discussion_id: str, project_id: str = "default") -> Path | None:
    """Get the real-time docs directory for a discussion (created by DocWriter)."""
    docs_dir = Path("data/projects") / project_id / discussion_id / "docs"
    if docs_dir.exists() and any(docs_dir.glob("*.md")):
        return docs_dir
    return None


def _list_realtime_docs(docs_dir: Path) -> list[DesignDocItem]:
    """List .md files from a real-time docs directory."""
    import re
    from datetime import datetime

    result = []
    for path in sorted(docs_dir.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        title_match = re.match(r"^#\s+(.+)", content)
        title = title_match.group(1) if title_match else path.stem
        stat = path.stat()
        result.append(DesignDocItem(
            filename=path.name,
            title=title,
            size=len(content.encode("utf-8")),
            created_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
        ))
    return result


@router.get("/{discussion_id}/design-docs", response_model=DesignDocsListResponse)
async def list_design_docs(discussion_id: str) -> DesignDocsListResponse:
    """List all organized design documents for a discussion.

    Checks real-time docs directory first (from DocWriter during document-centric mode),
    then falls back to DocOrganizer index.
    """
    state = get_discussion_state(discussion_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    # Try real-time docs first
    rt_dir = _get_realtime_docs_dir(discussion_id)
    if rt_dir:
        files = _list_realtime_docs(rt_dir)
        if files:
            return DesignDocsListResponse(
                discussion_id=discussion_id,
                topic=state.topic,
                files=files,
                created_at=files[0].created_at if files else None,
            )

    # Fallback to DocOrganizer
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


@router.get("/{discussion_id}/design-docs/{filename:path}", response_model=DesignDocContentResponse)
async def get_design_doc(discussion_id: str, filename: str) -> DesignDocContentResponse:
    """Get the content of a single design document.

    Checks real-time docs directory first, then falls back to DocOrganizer.
    """
    import re

    state = get_discussion_state(discussion_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    # Sanitize filename to prevent path traversal
    safe_filename = Path(filename).name

    # Try real-time docs first
    rt_dir = _get_realtime_docs_dir(discussion_id)
    if rt_dir:
        filepath = rt_dir / safe_filename
        if filepath.exists() and filepath.resolve().is_relative_to(rt_dir.resolve()):
            content = filepath.read_text(encoding="utf-8")
            title_match = re.match(r"^#\s+(.+)", content)
            title = title_match.group(1) if title_match else filepath.stem
            return DesignDocContentResponse(
                filename=safe_filename,
                title=title,
                content=content,
            )

    # Fallback to DocOrganizer
    organizer = DocOrganizer()

    index = organizer.load_index("default", discussion_id)
    title = safe_filename
    if index:
        for f in index.get("files", []):
            if f["filename"] == safe_filename:
                title = f.get("title", safe_filename)
                break

    content = organizer.load_document("default", discussion_id, safe_filename)
    if content is None:
        raise HTTPException(status_code=404, detail="Document not found")

    return DesignDocContentResponse(
        filename=safe_filename,
        title=title,
        content=content,
    )


# ============================================================
# Document-centric API Endpoints
# ============================================================


class FocusSectionRequest(BaseModel):
    """Request to focus on a specific section."""

    section_id: str = Field(..., description="Section ID to focus on (e.g., 's1')")


class DocPlanResponse(BaseModel):
    """Response for doc plan."""

    discussion_id: str
    doc_plan: dict | None = None


@router.get("/{discussion_id}/doc-plan", response_model=DocPlanResponse)
async def get_doc_plan(discussion_id: str) -> DocPlanResponse:
    """Get the document plan for a discussion."""
    state = get_discussion_state(discussion_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    # Load from discussion memory
    stored = _discussion_memory.load(discussion_id)
    doc_plan = stored.doc_plan if stored else None

    return DocPlanResponse(
        discussion_id=discussion_id,
        doc_plan=doc_plan,
    )


@router.post("/{discussion_id}/focus-section")
async def focus_section(discussion_id: str, request: FocusSectionRequest):
    """User requests to jump to a specific section for discussion.

    Injects a focus: message into the discussion state so the next
    round picks up the specified section.
    """
    from src.crew.discussion_crew import add_injected_message

    state = get_discussion_state(discussion_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    if state.status not in (DiscussionStatus.RUNNING,):
        raise HTTPException(status_code=400, detail="讨论未在运行中")

    add_injected_message(discussion_id, {
        "role": "user",
        "content": f"focus:{request.section_id}",
        "source": "intervention",
    })

    return {"status": "ok", "message": f"已请求跳转到章节 {request.section_id}"}
