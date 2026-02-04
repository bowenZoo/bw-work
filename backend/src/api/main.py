"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import discussion_router
from src.config.settings import settings
from src.monitoring.langfuse_client import init_langfuse, shutdown_langfuse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Startup
    init_langfuse()
    yield
    # Shutdown
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
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


# Include routers
app.include_router(discussion_router)
