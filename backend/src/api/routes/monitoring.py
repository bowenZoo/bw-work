"""Monitoring API routes for cost tracking and observability."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.api.routes.discussion import _discussions
from src.monitoring.langfuse_client import get_session_cost

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


class CostResponse(BaseModel):
    """Response containing cost/token statistics for a discussion."""

    discussion_id: str = Field(..., description="The discussion ID")
    total_tokens: int = Field(default=0, description="Total tokens used")
    prompt_tokens: int = Field(default=0, description="Prompt/input tokens")
    completion_tokens: int = Field(default=0, description="Completion/output tokens")
    model_breakdown: dict[str, int] = Field(
        default_factory=dict, description="Token usage by model"
    )
    source: str = Field(default="langfuse", description="Data source identifier")
    error: str | None = Field(default=None, description="Error message if any")


@router.get("/cost/{discussion_id}", response_model=CostResponse)
async def get_discussion_cost(discussion_id: str) -> CostResponse:
    """Get token usage statistics for a discussion.

    Returns token statistics from Langfuse for the given discussion.
    The discussion_id is used as the session_id in Langfuse.

    Note: Data may not be immediately available after a discussion ends
    due to Langfuse's asynchronous data processing.
    """
    # Verify discussion exists
    discussion = _discussions.get(discussion_id)
    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    # Get cost data from Langfuse
    cost_data = get_session_cost(discussion_id)

    if cost_data is None:
        return CostResponse(
            discussion_id=discussion_id,
            total_tokens=0,
            prompt_tokens=0,
            completion_tokens=0,
            model_breakdown={},
            source="langfuse",
            error="Langfuse not configured or unavailable",
        )

    return CostResponse(
        discussion_id=cost_data.get("discussion_id", discussion_id),
        total_tokens=cost_data.get("total_tokens", 0),
        prompt_tokens=cost_data.get("prompt_tokens", 0),
        completion_tokens=cost_data.get("completion_tokens", 0),
        model_breakdown=cost_data.get("model_breakdown", {}),
        source=cost_data.get("source", "langfuse"),
        error=cost_data.get("error"),
    )


@router.get("/health")
async def monitoring_health() -> dict:
    """Check monitoring system health.

    Returns the status of monitoring integrations.
    """
    from src.monitoring.langfuse_client import get_langfuse_client

    langfuse_status = "configured" if get_langfuse_client() is not None else "not_configured"

    return {
        "status": "ok",
        "langfuse": langfuse_status,
    }
