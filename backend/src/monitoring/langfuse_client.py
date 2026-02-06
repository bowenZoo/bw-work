"""Langfuse client for observability and tracing."""

import logging
from contextlib import contextmanager, nullcontext
from typing import Any, Iterator

try:
    from langfuse import Langfuse, observe, propagate_attributes
except ImportError:  # pragma: no cover - fallback for older SDKs
    from langfuse import Langfuse, observe

    def propagate_attributes(**_kwargs):  # type: ignore[override]
        return nullcontext()

from src.config.settings import settings

logger = logging.getLogger(__name__)

# Global Langfuse client instance
_langfuse_client: Langfuse | None = None


def _get_langfuse_config_from_store() -> tuple[str | None, str | None, str | None, bool]:
    """Get Langfuse config from admin config store.

    Returns:
        Tuple of (public_key, secret_key, host, enabled).
    """
    try:
        from src.admin.config_store import ConfigStore
        store = ConfigStore()
        public_key = store.get_raw("langfuse", "public_key")
        secret_key = store.get_raw("langfuse", "secret_key")
        host = store.get_raw("langfuse", "host") or "https://cloud.langfuse.com"
        enabled = store.get_raw("langfuse", "enabled") == "true"
        logger.debug(f"Langfuse config from store: host={host}, enabled={enabled}, has_keys={bool(public_key and secret_key)}")
        return public_key, secret_key, host, enabled
    except Exception as e:
        logger.debug(f"Failed to get Langfuse config from store: {e}")
        return None, None, None, False


def init_langfuse() -> Langfuse | None:
    """Initialize the Langfuse client.

    Returns:
        Langfuse client instance if configured, None otherwise.
    """
    global _langfuse_client

    if _langfuse_client is not None:
        return _langfuse_client

    # Try to get config from admin store first
    public_key, secret_key, host, enabled = _get_langfuse_config_from_store()

    # Fall back to environment variables / settings if not in store
    if not public_key:
        public_key = settings.langfuse_public_key
    if not secret_key:
        secret_key = settings.langfuse_secret_key
    if not host:
        host = settings.langfuse_host

    if not public_key or not secret_key:
        logger.warning(
            "Langfuse not configured. Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY "
            "environment variables to enable tracing."
        )
        return None

    # Check if enabled in admin store (if configured there)
    if not enabled and _get_langfuse_config_from_store()[0]:
        # Config exists in store but is disabled
        logger.info("Langfuse is configured but disabled in admin settings")
        return None

    try:
        logger.info(f"Initializing Langfuse client with host={host}")
        _langfuse_client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )
        logger.info("Langfuse client initialized successfully")
        return _langfuse_client
    except Exception as e:
        logger.error(f"Failed to initialize Langfuse: {e}")
        return None


def get_langfuse_client() -> Langfuse | None:
    """Get the global Langfuse client.

    Automatically initializes the client if not already initialized.

    Returns:
        Langfuse client instance if configured, None otherwise.
    """
    global _langfuse_client
    if _langfuse_client is None:
        init_langfuse()
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

    if hasattr(client, "start_span"):
        try:
            span = client.start_span(name=name, metadata=metadata or {})
            if hasattr(span, "update_trace"):
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

    logger.warning(
        "create_trace is deprecated for the current Langfuse SDK; "
        "use start_trace_context() instead."
    )
    return None


def _stringify_metadata(metadata: dict[str, Any] | None) -> dict[str, str]:
    """Ensure metadata values are strings for Langfuse propagation."""
    if not metadata:
        return {}
    output: dict[str, str] = {}
    for key, value in metadata.items():
        if value is None:
            continue
        text = value if isinstance(value, str) else str(value)
        if len(text) > 200:
            text = text[:197] + "..."
        output[str(key)] = text
    return output


@contextmanager
def start_trace_context(
    name: str,
    session_id: str | None = None,
    user_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Iterator[Any | None]:
    """Start a Langfuse trace as the current observation context.

    Uses the official start_as_current_observation + propagate_attributes flow.
    """
    client = init_langfuse()
    if client is None or not hasattr(client, "start_as_current_observation"):
        yield None
        return

    try:
        with client.start_as_current_observation(as_type="span", name=name) as span:
            if metadata:
                span.update(metadata=metadata)

            with propagate_attributes(
                session_id=session_id,
                user_id=user_id,
                trace_name=name,
                metadata=_stringify_metadata(metadata),
            ):
                yield span
    except Exception as exc:
        logger.error("Failed to start trace context: %s", exc)
        yield None


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
        if hasattr(trace_span, "start_span"):
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

        client = get_langfuse_client()
        if client is None or not hasattr(client, "start_as_current_observation"):
            return None

        with client.start_as_current_observation(as_type="span", name=step_name) as child_span:
            child_span.update(
                input=input_data or {},
                output=output_data,
                metadata={
                    "agent_role": agent_role,
                    "step_type": step_type,
                    **(metadata or {}),
                },
            )
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
        span_name = f"{agent_role}:decision"
        if hasattr(trace_span, "start_span"):
            child_span = trace_span.start_span(
                name=span_name,
                input={"reasoning": reasoning, "alternatives": alternatives or []},
                metadata={
                    "agent_role": agent_role,
                    "step_type": "decision",
                },
            )
            child_span.update(output=decision)
            child_span.end()
            return child_span

        client = get_langfuse_client()
        if client is None or not hasattr(client, "start_as_current_observation"):
            return None

        with client.start_as_current_observation(as_type="span", name=span_name) as child_span:
            child_span.update(
                input={"reasoning": reasoning, "alternatives": alternatives or []},
                output=decision,
                metadata={
                    "agent_role": agent_role,
                    "step_type": "decision",
                },
            )
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
        return {
            "discussion_id": session_id,
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "model_breakdown": {},
            "source": "langfuse",
            "error": "Langfuse 未配置或未启用",
        }

    try:
        if not hasattr(client, "api"):
            raise RuntimeError("Langfuse client missing api interface")

        traces_response = client.api.trace.list(session_id=session_id, limit=100)
        trace_items = getattr(traces_response, "data", traces_response) or []

        if not trace_items:
            return {
                "discussion_id": session_id,
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "model_breakdown": {},
                "source": "langfuse",
                "status": "no_data",
            }

        total_tokens = 0
        prompt_tokens = 0
        completion_tokens = 0
        model_breakdown: dict[str, int] = {}

        for trace in trace_items:
            trace_id = getattr(trace, "id", None) or trace.get("id")
            if not trace_id:
                continue

            observations_response = client.api.observations.get_many(
                trace_id=trace_id,
                type="GENERATION",
                limit=100,
            )
            observations = getattr(observations_response, "data", observations_response) or []

            for obs in observations:
                usage = getattr(obs, "usage", None) or obs.get("usage")
                if not usage:
                    continue

                total = getattr(usage, "total", None)
                if total is None and isinstance(usage, dict):
                    total = usage.get("total", 0)
                prompt = getattr(usage, "input", None)
                if prompt is None and isinstance(usage, dict):
                    prompt = usage.get("input", 0)
                completion = getattr(usage, "output", None)
                if completion is None and isinstance(usage, dict):
                    completion = usage.get("output", 0)

                total = total or 0
                prompt = prompt or 0
                completion = completion or 0

                total_tokens += total
                prompt_tokens += prompt
                completion_tokens += completion

                model = getattr(obs, "model", None) or obs.get("model") or "unknown"
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
        error_msg = str(e)
        logger.error(f"Failed to get session cost: {error_msg}")

        # Provide more helpful error messages
        if "401" in error_msg or "Invalid credentials" in error_msg:
            error_msg = "Langfuse 凭证无效，请检查密钥是否与所选区域（US/EU/默认）匹配"
        elif "connection" in error_msg.lower() or "timeout" in error_msg.lower():
            error_msg = "无法连接到 Langfuse 服务器"

        return {
            "discussion_id": session_id,
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "model_breakdown": {},
            "source": "langfuse",
            "error": error_msg,
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
    "start_trace_context",
    "record_agent_step",
    "record_decision_point",
    "get_session_cost",
    "flush_langfuse",
    "shutdown_langfuse",
    "observe",
]
