"""Memory API routes.

Provides endpoints for:
- Discussion history
- Decision records
- Semantic search
"""

import logging
from collections.abc import Iterable
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.memory.base import Decision, Discussion
from src.memory.decision_tracker import DecisionTracker
from src.memory.discussion_memory import DiscussionMemory
from src.memory.vector_store import VectorStore

router = APIRouter(prefix="/api", tags=["memory"])

# Logger
logger = logging.getLogger(__name__)

# Initialize memory instances
_discussion_memory = DiscussionMemory()
_decision_tracker = DecisionTracker()
_vector_store = VectorStore(collection_name="discussions")
_indexed_discussions: set[str] = set()
_indexed_decisions: set[str] = set()


# === Response Models ===


class MessageResponse(BaseModel):
    """Response model for a message."""

    id: str
    agent_id: str
    agent_role: str
    content: str
    timestamp: str


class DiscussionSummaryResponse(BaseModel):
    """Response model for discussion list item."""

    id: str
    project_id: str
    topic: str
    summary: str | None = None
    message_count: int
    created_at: str
    updated_at: str


class DiscussionDetailResponse(BaseModel):
    """Response model for discussion detail."""

    id: str
    project_id: str
    topic: str
    summary: str | None = None
    messages: list[MessageResponse]
    created_at: str
    updated_at: str


class DecisionResponse(BaseModel):
    """Response model for a decision."""

    id: str
    discussion_id: str
    title: str
    description: str
    rationale: str
    made_by: str
    created_at: str


class SearchResultResponse(BaseModel):
    """Response model for search result."""

    id: str
    title: str | None = None
    content: str
    score: float
    source_type: str  # "discussion" or "decision"
    metadata: dict[str, Any] = Field(default_factory=dict)


class DiscussionListResponse(BaseModel):
    """Response model for discussion list with pagination."""

    items: list[DiscussionSummaryResponse]
    hasMore: bool


class DiscussionMessagesResponse(BaseModel):
    """Response model for discussion messages endpoint."""

    discussion: DiscussionSummaryResponse
    messages: list[MessageResponse]


def _discussion_to_text(discussion: Discussion) -> str:
    """Build a searchable text representation for a discussion."""
    parts = [discussion.topic]
    if discussion.summary:
        parts.append(discussion.summary)
    for msg in discussion.messages:
        parts.append(f"{msg.agent_role}: {msg.content}")
    return "\n".join(p for p in parts if p)


def _decision_to_text(decision: Decision) -> str:
    """Build a searchable text representation for a decision."""
    return "\n".join(
        [
            decision.title,
            decision.description,
            decision.rationale,
        ]
    )


def _iter_discussions(project_id: str | None, batch_size: int = 200) -> Iterable[Discussion]:
    """Iterate through discussions with pagination."""
    offset = 0
    while True:
        if project_id:
            batch = _discussion_memory.list_by_project(
                project_id=project_id,
                offset=offset,
                limit=batch_size,
            )
        else:
            batch = _discussion_memory.list_all(offset=offset, limit=batch_size)

        if not batch:
            break

        for discussion in batch:
            yield discussion

        if len(batch) < batch_size:
            break

        offset += batch_size


def _iter_decisions(project_id: str | None, batch_size: int = 200) -> Iterable[Decision]:
    """Iterate through decisions with pagination."""
    offset = 0
    while True:
        batch = _decision_tracker.list_all(
            project_id=project_id,
            offset=offset,
            limit=batch_size,
        )

        if not batch:
            break

        for decision in batch:
            yield decision

        if len(batch) < batch_size:
            break

        offset += batch_size


def _ensure_vector_index(project_id: str | None) -> None:
    """Ensure discussions and decisions are indexed in the vector store."""
    # Index discussions
    for discussion in _iter_discussions(project_id):
        if discussion.id in _indexed_discussions:
            continue
        doc_id = f"discussion:{discussion.id}"
        _vector_store.add(
            text=_discussion_to_text(discussion),
            metadata={
                "source_type": "discussion",
                "discussion_id": discussion.id,
                "title": discussion.topic,
                "project_id": discussion.project_id,
                "message_count": len(discussion.messages),
            },
            doc_id=doc_id,
        )
        _indexed_discussions.add(discussion.id)

    # Index decisions
    project_ids: list[str]
    if project_id:
        project_ids = [project_id]
    else:
        project_ids = [
            path.name for path in _decision_tracker.data_dir.iterdir() if path.is_dir()
        ]

    for pid in project_ids:
        for decision in _iter_decisions(pid):
            if decision.id in _indexed_decisions:
                continue
            doc_id = f"decision:{decision.id}"
            _vector_store.add(
                text=_decision_to_text(decision),
                metadata={
                    "source_type": "decision",
                    "decision_id": decision.id,
                    "title": decision.title,
                    "project_id": pid,
                    "discussion_id": decision.discussion_id,
                    "made_by": decision.made_by,
                },
                doc_id=doc_id,
            )
            _indexed_decisions.add(decision.id)


# === Discussion Endpoints ===


@router.get("/discussions", response_model=DiscussionListResponse)
async def list_discussions(
    project_id: str | None = Query(None, description="Filter by project ID"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
) -> DiscussionListResponse:
    """Get list of discussion history.

    Returns a paginated list of discussions sorted by created_at DESC,
    optionally filtered by project.
    """
    offset = (page - 1) * limit

    if project_id:
        discussions = _discussion_memory.list_by_project(
            project_id=project_id,
            offset=offset,
            limit=limit + 1,  # Fetch one extra to check hasMore
        )
    else:
        discussions = _discussion_memory.list_all(offset=offset, limit=limit + 1)

    # Check if there are more items
    has_more = len(discussions) > limit
    if has_more:
        discussions = discussions[:limit]

    items = [
        DiscussionSummaryResponse(
            id=d.id,
            project_id=d.project_id,
            topic=d.topic,
            summary=d.summary,
            message_count=len(d.messages),
            created_at=d.created_at.isoformat(),
            updated_at=d.updated_at.isoformat(),
        )
        for d in discussions
    ]

    return DiscussionListResponse(items=items, hasMore=has_more)


@router.get("/discussions/{discussion_id}", response_model=DiscussionDetailResponse)
async def get_discussion(discussion_id: str) -> DiscussionDetailResponse:
    """Get discussion detail by ID."""
    discussion = _discussion_memory.load(discussion_id)

    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    return DiscussionDetailResponse(
        id=discussion.id,
        project_id=discussion.project_id,
        topic=discussion.topic,
        summary=discussion.summary,
        messages=[
            MessageResponse(
                id=m.id,
                agent_id=m.agent_id,
                agent_role=m.agent_role,
                content=m.content,
                timestamp=m.timestamp.isoformat(),
            )
            for m in discussion.messages
        ],
        created_at=discussion.created_at.isoformat(),
        updated_at=discussion.updated_at.isoformat(),
    )


@router.get(
    "/discussions/{discussion_id}/messages", response_model=DiscussionMessagesResponse
)
async def get_discussion_messages(
    discussion_id: str,
) -> DiscussionMessagesResponse:
    """Get messages from a discussion.

    Returns discussion metadata and all messages sorted by created_at ASC
    (chronological order for playback).
    """
    discussion = _discussion_memory.load(discussion_id)

    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    # Messages are already stored in chronological order (created_at ASC)
    messages = [
        MessageResponse(
            id=m.id,
            agent_id=m.agent_id,
            agent_role=m.agent_role,
            content=m.content,
            timestamp=m.timestamp.isoformat(),
        )
        for m in discussion.messages
    ]

    discussion_meta = DiscussionSummaryResponse(
        id=discussion.id,
        project_id=discussion.project_id,
        topic=discussion.topic,
        summary=discussion.summary,
        message_count=len(discussion.messages),
        created_at=discussion.created_at.isoformat(),
        updated_at=discussion.updated_at.isoformat(),
    )

    return DiscussionMessagesResponse(discussion=discussion_meta, messages=messages)


# === Decision Endpoints ===


@router.get("/decisions", response_model=list[DecisionResponse])
async def list_decisions(
    project_id: str | None = Query(None, description="Filter by project ID"),
    discussion_id: str | None = Query(None, description="Filter by discussion ID"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(20, ge=1, le=100, description="Pagination limit"),
) -> list[DecisionResponse]:
    """Get list of decisions.

    Returns a paginated list of decisions, optionally filtered by project or discussion.
    """
    if discussion_id:
        decisions = _decision_tracker.list_by_discussion(
            discussion_id=discussion_id,
            project_id=project_id,
        )
    else:
        decisions = _decision_tracker.list_all(
            project_id=project_id,
            offset=offset,
            limit=limit,
        )

    return [
        DecisionResponse(
            id=d.id,
            discussion_id=d.discussion_id,
            title=d.title,
            description=d.description,
            rationale=d.rationale,
            made_by=d.made_by,
            created_at=d.created_at.isoformat(),
        )
        for d in decisions
    ]


@router.get("/decisions/{decision_id}", response_model=DecisionResponse)
async def get_decision(
    decision_id: str,
    project_id: str | None = Query(None, description="Project ID to narrow search"),
) -> DecisionResponse:
    """Get decision by ID."""
    decision = _decision_tracker.load(decision_id, project_id=project_id)

    if decision is None:
        raise HTTPException(status_code=404, detail="Decision not found")

    return DecisionResponse(
        id=decision.id,
        discussion_id=decision.discussion_id,
        title=decision.title,
        description=decision.description,
        rationale=decision.rationale,
        made_by=decision.made_by,
        created_at=decision.created_at.isoformat(),
    )


# === Search Endpoint ===


@router.get("/search", response_model=list[SearchResultResponse])
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results"),
    project_id: str | None = Query(None, description="Filter by project ID"),
) -> list[SearchResultResponse]:
    """Semantic search across discussions and decisions.

    Uses vector similarity search when available, falls back to keyword search.
    """
    results: list[SearchResultResponse] = []

    # Ensure vector index is up to date
    try:
        _ensure_vector_index(project_id)
        vector_results = _vector_store.search(
            query=q,
            limit=limit,
            filter_metadata={"project_id": project_id} if project_id else None,
        )

        if vector_results:
            for vr in vector_results:
                metadata = vr.get("metadata", {})
                source_type = metadata.get("source_type", "discussion")
                result_id = (
                    metadata.get("discussion_id")
                    or metadata.get("decision_id")
                    or vr.get("id", "")
                )
                title = metadata.get("title")
                results.append(
                    SearchResultResponse(
                        id=result_id,
                        title=title,
                        content=vr.get("text", ""),
                        score=vr.get("score", 0),
                        source_type=source_type,
                        metadata=metadata,
                    )
                )
            return results[:limit]
    except Exception as exc:
        logger.warning("Vector search unavailable, falling back to keyword search: %s", exc)

    # Search discussions
    discussions = _discussion_memory.search(query=q, limit=limit)
    for d in discussions:
        results.append(
            SearchResultResponse(
                id=d.id,
                title=d.topic,
                content=d.summary or "",
                score=0.8,  # Placeholder score for keyword search
                source_type="discussion",
                metadata={
                    "project_id": d.project_id,
                    "message_count": len(d.messages),
                },
            )
        )

    # Search decisions
    decisions = _decision_tracker.search(query=q, limit=limit, project_id=project_id)
    for d in decisions:
        results.append(
            SearchResultResponse(
                id=d.id,
                title=d.title,
                content=d.description,
                score=0.7,  # Placeholder score
                source_type="decision",
                metadata={
                    "discussion_id": d.discussion_id,
                    "made_by": d.made_by,
                },
            )
        )

    # Sort by score and limit
    results.sort(key=lambda x: x.score, reverse=True)
    return results[:limit]
