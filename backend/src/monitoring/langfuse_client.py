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
        session_id: Optional session identifier.
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
    "flush_langfuse",
    "shutdown_langfuse",
    "observe",
]
