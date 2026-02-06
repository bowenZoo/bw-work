"""FastAPI application entry point."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.routes import (
    discussion_router,
    document_router,
    image_router,
    intervention_router,
    memory_router,
    monitoring_router,
    project_router,
)
from src.api.websocket import connection_manager, websocket_router
from src.api.websocket.manager import global_connection_manager, set_event_loop
from src.config.settings import settings, reload_config
from src.monitoring.langfuse_client import init_langfuse, shutdown_langfuse
from src.admin.routes import admin_router
from src.admin.database import AdminDatabase
from src.admin.audit_log import AuditLogger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Startup - Load config from admin store first
    reload_config()  # Load all config from ConfigStore before initializing services
    init_langfuse()
    # Set event loop for sync-to-async bridging
    set_event_loop(asyncio.get_running_loop())
    # Start WebSocket connection sweep tasks
    connection_manager.start_sweep_task()
    global_connection_manager.start_sweep_task()
    # Initialize admin database
    admin_db = AdminDatabase()
    admin_db.init_db()
    admin_db.setup_initial_admin()
    # Cleanup old audit logs (configurable, default 90 days)
    audit_logger = AuditLogger(admin_db)
    audit_logger.cleanup_old_logs()
    # Cleanup expired refresh tokens
    admin_db.cleanup_expired_tokens()
    yield
    # Shutdown
    connection_manager.stop_sweep_task()
    global_connection_manager.stop_sweep_task()
    shutdown_langfuse()


app = FastAPI(
    title=settings.app_name,
    description="AI Game Design Team Backend - Multi-agent discussion system",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allowed_methods,
    allow_headers=settings.cors_allowed_headers,
)


class AdminSecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers for admin routes."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Add security headers for admin routes
        if request.url.path.startswith("/api/admin"):
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "font-src 'self'; "
                "connect-src 'self'"
            )
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        return response


app.add_middleware(AdminSecurityHeadersMiddleware)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


# Include routers
app.include_router(discussion_router)
app.include_router(document_router)
app.include_router(image_router)
app.include_router(intervention_router)
app.include_router(memory_router)
app.include_router(monitoring_router)
app.include_router(project_router)
app.include_router(websocket_router)
app.include_router(admin_router)
