"""
Admin API routes.
"""

from fastapi import APIRouter

from .auth import router as auth_router
from .config import router as config_router
from .logs import router as logs_router
from .data import router as data_router

# Create main admin router
admin_router = APIRouter(prefix="/api/admin", tags=["admin"])

# Include sub-routers
admin_router.include_router(auth_router)
admin_router.include_router(config_router)
admin_router.include_router(logs_router)
admin_router.include_router(data_router)

__all__ = ["admin_router"]
