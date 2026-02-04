"""API route definitions."""

from src.api.routes.discussion import router as discussion_router
from src.api.routes.memory import router as memory_router

__all__ = ["discussion_router", "memory_router"]
