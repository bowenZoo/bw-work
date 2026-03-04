"""FastAPI application entry point."""

import asyncio
import logging
import os
from collections.abc import AsyncGenerator

# Disable CrewAI telemetry and interactive prompts to prevent blocking in thread pools
os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_TESTING"] = "true"
from contextlib import asynccontextmanager

from src.config.logging_config import setup_logging, cleanup_old_logs

# Set up file + console logging before anything else logs
_log_dir = os.environ.get("LOG_DIR", "logs")
_log_level = os.environ.get("LOG_LEVEL", "INFO")
setup_logging(log_dir=_log_dir, level=_log_level)

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.routes import (
    checkpoint_router,
    cleanup_stale_discussions,
    design_docs_router,
    discussion_router,
    document_router,
    image_router,
    intervention_router,
    memory_router,
    monitoring_router,
    project_router,
    restore_latest_discussion,
    auth_router,
    users_router,
)
from src.api.websocket import connection_manager, websocket_router
from src.api.websocket.manager import global_connection_manager, set_event_loop
from src.config.settings import settings, reload_config
from src.monitoring.langfuse_client import init_langfuse, shutdown_langfuse
from src.admin.routes import admin_router
from src.admin.database import AdminDatabase
from src.admin.audit_log import AuditLogger


logger = logging.getLogger(__name__)


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
    # Initialize user accounts admin
    admin_db.setup_initial_user_admin()
    # Cleanup old audit logs (configurable, default 90 days)
    audit_logger = AuditLogger(admin_db)
    audit_logger.cleanup_old_logs()
    # Cleanup expired refresh tokens
    admin_db.cleanup_expired_tokens()
    # Cleanup old log directories
    _keep_days = int(os.environ.get("LOG_KEEP_DAYS", "30"))
    removed = cleanup_old_logs(log_dir=_log_dir, keep_days=_keep_days)
    if removed:
        logger.info("Cleaned up %d old log director(ies)", removed)
    # Cleanup stale "running" discussions from previous server session
    cleaned = cleanup_stale_discussions()
    if cleaned:
        logger.info("Cleaned up %d stale discussion(s) on startup", cleaned)
    # Restore latest discussion so WebSocket sync can serve it to new clients
    restore_latest_discussion()
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
app.include_router(checkpoint_router)
app.include_router(design_docs_router)
app.include_router(discussion_router)
app.include_router(document_router)
app.include_router(image_router)
app.include_router(intervention_router)
app.include_router(memory_router)
app.include_router(monitoring_router)
app.include_router(project_router)
app.include_router(websocket_router)
app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(users_router)
