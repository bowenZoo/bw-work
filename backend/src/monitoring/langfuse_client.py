"""Langfuse client for observability and tracing."""

import logging
from typing import Any

from langfuse import Langfuse, observe

from src.config.settings import settings

logger = logging.getLogger(__name__)

# Global Langfuse client instance
_langfuse_client: Langfuse | None = None


def init_langfuse() -> Langfuse | None:
    """Initialize the Langfuse client.

    Returns:
        Langfuse client instance if configured, None otherwise.
    """
    global _langfuse_client

    if _langfuse_client is not None:
        return _langfuse_client

    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        logger.warning(
            "Langfuse not configured. Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY "
            "environment variables to enable tracing."
        )
        return None

    try:
        _langfuse_client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        logger.info("Langfuse client initialized successfully")
        return _langfuse_client
    except Exception as e:
        logger.error(f"Failed to initialize Langfuse: {e}")
        return None


def get_langfuse_client() -> Langfuse | None:
    """Get the global Langfuse client.

    Returns:
        Langfuse client instance if initialized, None otherwise.
    """
    return _langfuse_client


def get_langfuse_handler(
    session_id: str | None = None,
    user_id: str | None = None,
    trace_name: str = "discussion",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Get Langfuse configuration for tracing.

    In Langfuse v3, instead of a callback handler, we use the observe decorator
    or manual tracing. This function returns configuration that can be used
    with the Langfuse client.

    Args:
        session_id: Optional session identifier for grouping traces.
        user_id: Optional user identifier.
        trace_name: Name for the trace (default: "discussion").
        metadata: Optional metadata to attach to the trace.

    Returns:
        Dictionary with Langfuse configuration if configured, None otherwise.
    """
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        logger.debug("Langfuse not configured, returning None")
        return None

    config = {
        "session_id": session_id,
        "user_id": user_id,
        "trace_name": trace_name,
        "metadata": metadata or {},
    }
    return config


def create_trace(
    name: str,
    session_id: str | None = None,
    user_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Any | None:
    """Create a new Langfuse trace root span.

    Args:
        name: Name for the trace/span.
        session_id: Optional session identifier (typically discussion_id).
        user_id: Optional user identifier.
        metadata: Optional metadata to attach.

    Returns:
        Langfuse span object if client is initialized, None otherwise.
        Caller is responsible for ending the span.
    """
    client = init_langfuse()
    if client is None:
        return None

    try:
        if not hasattr(client, "start_span"):
            logger.warning("Langfuse client missing start_span; tracing disabled.")
            return None

        span = client.start_span(name=name, metadata=metadata or {})
        span.update_trace(
            name=name,
            session_id=session_id,
            user_id=user_id,
            metadata=metadata or {},
        )
        return span
    except Exception as e:
        logger.error(f"Failed to create trace: {e}")
        return None


def record_agent_step(
    trace_span: Any,
    agent_role: str,
    step_type: str,
    input_data: dict[str, Any] | None = None,
    output_data: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Any | None:
    """Record an agent execution step.

    Args:
        trace_span: The parent trace span.
        agent_role: The agent's role name.
        step_type: Type of step (e.g., "thinking", "speaking", "decision").
        input_data: Optional input data for the step.
        output_data: Optional output data from the step.
        metadata: Optional additional metadata.

    Returns:
        Child span if created, None otherwise.
    """
    if trace_span is None:
        return None

    try:
        step_name = f"{agent_role}:{step_type}"
        child_span = trace_span.start_span(
            name=step_name,
            input=input_data or {},
            metadata={
                "agent_role": agent_role,
                "step_type": step_type,
                **(metadata or {}),
            },
        )
        if output_data:
            child_span.update(output=output_data)
        child_span.end()
        return child_span
    except Exception as e:
        logger.debug(f"Failed to record agent step: {e}")
        return None


def record_decision_point(
    trace_span: Any,
    agent_role: str,
    decision: str,
    reasoning: str,
    alternatives: list[str] | None = None,
) -> Any | None:
    """Record a decision point in the discussion.

    Args:
        trace_span: The parent trace span.
        agent_role: The agent making the decision.
        decision: The decision made.
        reasoning: The reasoning behind the decision.
        alternatives: Optional list of alternatives considered.

    Returns:
        Child span if created, None otherwise.
    """
    if trace_span is None:
        return None

    try:
        child_span = trace_span.start_span(
            name=f"{agent_role}:decision",
            input={"reasoning": reasoning, "alternatives": alternatives or []},
            metadata={
                "agent_role": agent_role,
                "step_type": "decision",
            },
        )
        child_span.update(output=decision)
        child_span.end()
        return child_span
    except Exception as e:
        logger.debug(f"Failed to record decision point: {e}")
        return None


def get_session_cost(session_id: str) -> dict[str, Any] | None:
    """Get token statistics for a session from Langfuse.

    Args:
        session_id: The session ID (typically discussion_id).

    Returns:
        Dictionary with token statistics, or None if not available.
    """
    client = get_langfuse_client()
    if client is None:
        return None

    try:
        # Langfuse API to get session data
        # Note: This is a simplified implementation. The actual Langfuse API
        # may require different methods depending on the version.

        # Try to fetch traces for this session
        # In Langfuse v3, we need to use the API directly
        traces = client.fetch_traces(session_id=session_id)

        if not traces or not hasattr(traces, "data"):
            return {
                "discussion_id": session_id,
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "model_breakdown": {},
                "source": "langfuse",
                "status": "no_data",
            }

        # Aggregate token counts
        total_tokens = 0
        prompt_tokens = 0
        completion_tokens = 0
        model_breakdown: dict[str, int] = {}

        for trace in traces.data:
            if hasattr(trace, "observations"):
                for obs in trace.observations:
                    if hasattr(obs, "usage") and obs.usage:
                        usage = obs.usage
                        total = getattr(usage, "total", 0) or 0
                        prompt = getattr(usage, "input", 0) or 0
                        completion = getattr(usage, "output", 0) or 0

                        total_tokens += total
                        prompt_tokens += prompt
                        completion_tokens += completion

                        model = getattr(obs, "model", "unknown")
                        model_breakdown[model] = model_breakdown.get(model, 0) + total

        return {
            "discussion_id": session_id,
            "total_tokens": total_tokens,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "model_breakdown": model_breakdown,
            "source": "langfuse",
        }
    except Exception as e:
        logger.error(f"Failed to get session cost: {e}")
        return {
            "discussion_id": session_id,
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "model_breakdown": {},
            "source": "langfuse",
            "error": str(e),
        }


def flush_langfuse() -> None:
    """Flush any pending Langfuse events.

    Call this before shutting down to ensure all events are sent.
    """
    global _langfuse_client

    if _langfuse_client is not None:
        try:
            _langfuse_client.flush()
            logger.debug("Langfuse events flushed")
        except Exception as e:
            logger.error(f"Failed to flush Langfuse: {e}")


def shutdown_langfuse() -> None:
    """Shutdown the Langfuse client.

    Call this on application shutdown.
    """
    global _langfuse_client

    if _langfuse_client is not None:
        try:
            _langfuse_client.flush()
            _langfuse_client.shutdown()
            _langfuse_client = None
            logger.info("Langfuse client shutdown")
        except Exception as e:
            logger.error(f"Failed to shutdown Langfuse: {e}")


# Re-export the observe decorator for convenience
__all__ = [
    "init_langfuse",
    "get_langfuse_client",
    "get_langfuse_handler",
    "create_trace",
    "record_agent_step",
    "record_decision_point",
    "get_session_cost",
    "flush_langfuse",
    "shutdown_langfuse",
    "observe",
]
