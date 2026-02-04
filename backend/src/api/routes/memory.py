"""Memory API routes.

Provides endpoints for:
- Discussion history
- Decision records
- Semantic search
"""

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.memory.decision_tracker import DecisionTracker
from src.memory.discussion_memory import DiscussionMemory
from src.memory.vector_store import VectorStore

router = APIRouter(prefix="/api", tags=["memory"])

# Initialize memory instances
_discussion_memory = DiscussionMemory()
_decision_tracker = DecisionTracker()
_vector_store = VectorStore(collection_name="discussions")


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
    summary: Optional[str] = None
    message_count: int
    created_at: str
    updated_at: str


class DiscussionDetailResponse(BaseModel):
    """Response model for discussion detail."""

    id: str
    project_id: str
    topic: str
    summary: Optional[str] = None
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
    title: Optional[str] = None
    content: str
    score: float
    source_type: str  # "discussion" or "decision"
    metadata: dict[str, Any] = Field(default_factory=dict)


class PaginatedResponse(BaseModel):
    """Generic paginated response."""

    items: list[Any]
    total: int
    offset: int
    limit: int


# === Discussion Endpoints ===


@router.get("/discussions", response_model=list[DiscussionSummaryResponse])
async def list_discussions(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(20, ge=1, le=100, description="Pagination limit"),
) -> list[DiscussionSummaryResponse]:
    """Get list of discussion history.

    Returns a paginated list of discussions, optionally filtered by project.
    """
    if project_id:
        discussions = _discussion_memory.list_by_project(
            project_id=project_id,
            offset=offset,
            limit=limit,
        )
    else:
        discussions = _discussion_memory.list_all(offset=offset, limit=limit)

    return [
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


@router.get("/discussions/{discussion_id}/messages", response_model=list[MessageResponse])
async def get_discussion_messages(
    discussion_id: str,
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=200, description="Pagination limit"),
) -> list[MessageResponse]:
    """Get messages from a discussion.

    Returns a paginated list of messages from the specified discussion.
    """
    discussion = _discussion_memory.load(discussion_id)

    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    messages = discussion.messages[offset : offset + limit]

    return [
        MessageResponse(
            id=m.id,
            agent_id=m.agent_id,
            agent_role=m.agent_role,
            content=m.content,
            timestamp=m.timestamp.isoformat(),
        )
        for m in messages
    ]


# === Decision Endpoints ===


@router.get("/decisions", response_model=list[DecisionResponse])
async def list_decisions(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    discussion_id: Optional[str] = Query(None, description="Filter by discussion ID"),
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
    project_id: Optional[str] = Query(None, description="Project ID to narrow search"),
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
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
) -> list[SearchResultResponse]:
    """Semantic search across discussions and decisions.

    Uses vector similarity search when available, falls back to keyword search.
    """
    results = []

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
