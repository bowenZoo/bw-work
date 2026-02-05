"""FastAPI application entry point."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import (
    discussion_router,
    document_router,
    image_router,
    intervention_router,
    memory_router,
    monitoring_router,
)
from src.api.websocket import connection_manager, websocket_router
from src.api.websocket.manager import set_event_loop
from src.config.settings import settings
from src.monitoring.langfuse_client import init_langfuse, shutdown_langfuse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Startup
    init_langfuse()
    # Set event loop for sync-to-async bridging
    set_event_loop(asyncio.get_running_loop())
    # Start WebSocket connection sweep task
    connection_manager.start_sweep_task()
    yield
    # Shutdown
    connection_manager.stop_sweep_task()
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
app.include_router(websocket_router)
