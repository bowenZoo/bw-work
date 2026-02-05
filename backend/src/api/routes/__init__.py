"""API route definitions."""

from src.api.routes.discussion import router as discussion_router
from src.api.routes.document import router as document_router
from src.api.routes.image import router as image_router
from src.api.routes.intervention import router as intervention_router
from src.api.routes.memory import router as memory_router
from src.api.routes.monitoring import router as monitoring_router

__all__ = [
    "discussion_router",
    "document_router",
    "image_router",
    "intervention_router",
    "memory_router",
    "monitoring_router",
]
