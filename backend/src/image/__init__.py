"""Image generation module for AI Game Design Team.

This module provides image generation capabilities including:
- Multiple backend support (OpenAI, OpenAI-compatible, task polling)
- Style template management
- Prompt engineering
- Image storage management
"""

from src.image.backends.base import (
    ImageBackend,
    ImageResult,
    TaskStatus,
    TaskStatusEnum,
)
from src.image.prompt_engineer import EnhancedPrompt, PromptEngineer
from src.image.providers import (
    ProviderNotFoundError,
    ProviderRegistry,
    get_provider_registry,
)
from src.image.service import GenerationResult, ImageService, get_image_service
from src.image.storage import ImageMetadata, ImageRequest, ImageStorage
from src.image.style_manager import Style, StyleManager, StyleNotFoundError, get_style_manager

__all__ = [
    # Backends
    "ImageBackend",
    "ImageResult",
    "TaskStatus",
    "TaskStatusEnum",
    # Service
    "ImageService",
    "GenerationResult",
    "get_image_service",
    # Storage
    "ImageStorage",
    "ImageMetadata",
    "ImageRequest",
    # Providers
    "ProviderRegistry",
    "ProviderNotFoundError",
    "get_provider_registry",
    # Styles
    "StyleManager",
    "Style",
    "StyleNotFoundError",
    "get_style_manager",
    # Prompt Engineering
    "PromptEngineer",
    "EnhancedPrompt",
]
