"""API route definitions."""

from src.api.routes.checkpoint import router as checkpoint_router
from src.api.routes.design_docs import router as design_docs_router
from src.api.routes.discussion import cleanup_stale_discussions, restore_latest_discussion, router as discussion_router
from src.api.routes.document import router as document_router
from src.api.routes.image import router as image_router
from src.api.routes.intervention import router as intervention_router
from src.api.routes.memory import router as memory_router
from src.api.routes.monitoring import router as monitoring_router
from src.api.routes.project import router as project_router

__all__ = [
    "checkpoint_router",
    "cleanup_stale_discussions",
    "restore_latest_discussion",
    "design_docs_router",
    "discussion_router",
    "document_router",
    "image_router",
    "intervention_router",
    "memory_router",
    "monitoring_router",
    "project_router",
]
