"""Image generation service.

This is the main entry point for image generation, coordinating
prompt enhancement, backend selection, generation, and storage.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from src.image.backends.base import ImageResult
from src.image.prompt_engineer import PromptEngineer
from src.image.providers import ProviderRegistry, get_provider_registry
from src.image.storage import ImageMetadata, ImageStorage
from src.image.style_manager import StyleManager, get_style_manager

logger = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    """Result of an image generation request.

    Attributes:
        success: Whether the generation was successful.
        image_id: Unique identifier for the image.
        image_url: URL to access the image.
        prompt: The original prompt.
        enhanced_prompt: The enhanced prompt used for generation.
        style_id: Style template used.
        provider_id: Provider that generated the image.
        width: Image width in pixels.
        height: Image height in pixels.
        generation_time_ms: Time taken to generate.
        error: Error message if generation failed.
        is_async: Whether this is an async result (pending completion).
        task_id: Task ID for async generation.
    """

    success: bool
    image_id: str = ""
    image_url: str = ""
    prompt: str = ""
    enhanced_prompt: str = ""
    style_id: str = ""
    provider_id: str = ""
    width: int = 0
    height: int = 0
    generation_time_ms: int = 0
    error: str | None = None
    is_async: bool = False
    task_id: str | None = None


# Type for WebSocket broadcast callback
WebSocketBroadcastCallback = Callable[[str, dict[str, Any]], None]


class ImageService:
    """Main image generation service.

    Coordinates all components of image generation:
    - Prompt enhancement
    - Style application
    - Backend selection
    - Image generation
    - Storage and metadata
    - WebSocket notifications

    Usage:
        service = ImageService()
        result = await service.generate(
            description="A warrior character",
            style_id="concept_character",
            project_id="proj_001",
        )
    """

    MAX_RETRIES = 2

    def __init__(
        self,
        provider_registry: ProviderRegistry | None = None,
        style_manager: StyleManager | None = None,
        prompt_engineer: PromptEngineer | None = None,
        storage: ImageStorage | None = None,
        websocket_broadcast: WebSocketBroadcastCallback | None = None,
    ) -> None:
        """Initialize the image service.

        Args:
            provider_registry: Provider registry instance.
            style_manager: Style manager instance.
            prompt_engineer: Prompt engineer instance.
            storage: Image storage instance.
            websocket_broadcast: Callback for WebSocket broadcasts.
        """
        self.provider_registry = provider_registry or get_provider_registry()
        self.style_manager = style_manager or get_style_manager()
        self.prompt_engineer = prompt_engineer or PromptEngineer()
        self.storage = storage or ImageStorage()
        self.websocket_broadcast = websocket_broadcast

        # Background tasks for async generation
        self._background_tasks: set[asyncio.Task] = set()

    def _broadcast(self, event_type: str, data: dict[str, Any]) -> None:
        """Broadcast an event via WebSocket.

        Args:
            event_type: Type of event.
            data: Event data.
        """
        if self.websocket_broadcast:
            try:
                self.websocket_broadcast(event_type, data)
            except Exception as e:
                logger.warning(f"WebSocket broadcast failed: {e}")

    async def generate(
        self,
        description: str,
        project_id: str,
        style_id: str | None = None,
        provider_id: str | None = None,
        discussion_id: str | None = None,
        agent: str = "",
        params: dict[str, Any] | None = None,
        wait: bool = True,
    ) -> GenerationResult:
        """Generate an image from a description.

        Args:
            description: Text description of the image to generate.
            project_id: Project identifier for storage.
            style_id: Style template ID (uses default if not specified).
            provider_id: Provider ID (uses style recommendation if not specified).
            discussion_id: Optional discussion ID for context.
            agent: Agent that requested the generation.
            params: Additional generation parameters.
            wait: Whether to wait for completion (False for async).

        Returns:
            GenerationResult with the generated image info.
        """
        params = params or {}

        # Get style template
        try:
            style = self.style_manager.get_style(style_id)
            style_id = style.id
        except Exception as e:
            logger.warning(f"Failed to get style {style_id}: {e}, using default")
            style = self.style_manager.get_style()
            style_id = style.id

        # Determine provider
        if provider_id is None:
            # Try to get recommended backend for style
            available_providers = self.provider_registry.list_providers()
            provider_id = self.style_manager.get_recommended_backend(
                style_id, available_providers
            )
            if provider_id is None:
                provider_id = self.provider_registry.default_provider

        # Get backend
        try:
            backend = self.provider_registry.get_backend(provider_id)
        except Exception as e:
            logger.error(f"Failed to get backend {provider_id}: {e}")
            return GenerationResult(
                success=False,
                prompt=description,
                style_id=style_id,
                error=f"Backend not available: {e}",
            )

        # Enhance prompt
        enhanced = await self.prompt_engineer.enhance(
            description=description,
            style=style.get_prompt_config(),
            style_id=style_id,
        )

        # Generate image ID
        image_id = self.storage._generate_image_id()

        # Initialize request tracking
        await self.storage.update_request_status(
            project_id=project_id,
            image_id=image_id,
            status="pending",
            provider_id=provider_id,
        )

        # Broadcast start event
        self._broadcast("image_generation_start", {
            "request_id": image_id,
            "prompt": description,
            "style": style_id,
            "provider_id": provider_id,
        })

        # Merge style default params with provided params
        generation_params = {**style.default_params, **params}
        if not wait:
            generation_params["wait"] = False

        # Attempt generation with retries
        last_error: str | None = None
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                await self.storage.update_request_status(
                    project_id=project_id,
                    image_id=image_id,
                    status="processing",
                )

                result = await backend.generate(enhanced.enhanced, generation_params)

                if result.success:
                    return await self._handle_success(
                        result=result,
                        image_id=image_id,
                        project_id=project_id,
                        description=description,
                        enhanced_prompt=enhanced.enhanced,
                        style_id=style_id,
                        provider_id=provider_id,
                        discussion_id=discussion_id,
                        agent=agent,
                        wait=wait,
                    )

                last_error = result.error
                logger.warning(
                    f"Generation attempt {attempt + 1} failed: {result.error}"
                )

            except Exception as e:
                last_error = str(e)
                logger.exception(f"Generation attempt {attempt + 1} raised exception")

            # Wait before retry
            if attempt < self.MAX_RETRIES:
                await asyncio.sleep(1)

        # All retries failed
        await self.storage.update_request_status(
            project_id=project_id,
            image_id=image_id,
            status="failed",
            error=last_error,
        )

        self._broadcast("image_generation_error", {
            "request_id": image_id,
            "error": last_error or "Unknown error",
        })

        return GenerationResult(
            success=False,
            image_id=image_id,
            prompt=description,
            enhanced_prompt=enhanced.enhanced,
            style_id=style_id,
            provider_id=provider_id,
            error=last_error,
        )

    async def _handle_success(
        self,
        result: ImageResult,
        image_id: str,
        project_id: str,
        description: str,
        enhanced_prompt: str,
        style_id: str,
        provider_id: str,
        discussion_id: str | None,
        agent: str,
        wait: bool,
    ) -> GenerationResult:
        """Handle successful generation result.

        Args:
            result: Backend result.
            image_id: Image identifier.
            project_id: Project identifier.
            description: Original description.
            enhanced_prompt: Enhanced prompt.
            style_id: Style ID.
            provider_id: Provider ID.
            discussion_id: Discussion ID.
            agent: Requesting agent.
            wait: Whether we waited for completion.

        Returns:
            GenerationResult.
        """
        # If async result (has task_id but no image data)
        if result.is_async and result.task_id:
            await self.storage.update_request_status(
                project_id=project_id,
                image_id=image_id,
                status="processing",
                task_id=result.task_id,
            )

            # Start background task to poll and complete
            task = asyncio.create_task(
                self._complete_async_generation(
                    result=result,
                    image_id=image_id,
                    project_id=project_id,
                    description=description,
                    enhanced_prompt=enhanced_prompt,
                    style_id=style_id,
                    provider_id=provider_id,
                    discussion_id=discussion_id,
                    agent=agent,
                )
            )
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

            return GenerationResult(
                success=True,
                image_id=image_id,
                prompt=description,
                enhanced_prompt=enhanced_prompt,
                style_id=style_id,
                provider_id=provider_id,
                is_async=True,
                task_id=result.task_id,
            )

        # Sync result - save image
        if result.image_data:
            metadata = ImageMetadata(
                id=image_id,
                filename="",  # Will be set by storage
                prompt=description,
                style=style_id,
                provider_id=provider_id,
                width=result.width or 0,
                height=result.height or 0,
                created_at=datetime.utcnow().isoformat() + "Z",
                discussion_id=discussion_id,
                agent=agent,
                generation_time_ms=result.generation_time_ms or 0,
            )

            await self.storage.save_image(
                project_id=project_id,
                image_data=result.image_data,
                metadata=metadata,
                image_id=image_id,
                format=result.format,
            )

            await self.storage.update_request_status(
                project_id=project_id,
                image_id=image_id,
                status="completed",
            )

            image_url = self.storage.get_image_url(project_id, image_id)

            self._broadcast("image_generation_complete", {
                "request_id": image_id,
                "image_url": image_url,
                "metadata": {
                    "width": result.width,
                    "height": result.height,
                    "provider_id": provider_id,
                    "generation_time_ms": result.generation_time_ms,
                },
            })

            return GenerationResult(
                success=True,
                image_id=image_id,
                image_url=image_url,
                prompt=description,
                enhanced_prompt=enhanced_prompt,
                style_id=style_id,
                provider_id=provider_id,
                width=result.width or 0,
                height=result.height or 0,
                generation_time_ms=result.generation_time_ms or 0,
            )

        # URL result (no direct image data)
        if result.image_url:
            # TODO: Download and store the image from URL
            logger.warning(f"URL result not fully implemented: {result.image_url}")

            return GenerationResult(
                success=True,
                image_id=image_id,
                image_url=result.image_url,
                prompt=description,
                enhanced_prompt=enhanced_prompt,
                style_id=style_id,
                provider_id=provider_id,
                width=result.width or 0,
                height=result.height or 0,
                generation_time_ms=result.generation_time_ms or 0,
            )

        # Unexpected state
        return GenerationResult(
            success=False,
            image_id=image_id,
            prompt=description,
            enhanced_prompt=enhanced_prompt,
            style_id=style_id,
            provider_id=provider_id,
            error="No image data in successful result",
        )

    async def _complete_async_generation(
        self,
        result: ImageResult,
        image_id: str,
        project_id: str,
        description: str,
        enhanced_prompt: str,
        style_id: str,
        provider_id: str,
        discussion_id: str | None,
        agent: str,
    ) -> None:
        """Complete an async generation by polling and saving the result.

        Args:
            result: Initial async result with task_id.
            image_id: Image identifier.
            project_id: Project identifier.
            description: Original description.
            enhanced_prompt: Enhanced prompt.
            style_id: Style ID.
            provider_id: Provider ID.
            discussion_id: Discussion ID.
            agent: Requesting agent.
        """
        try:
            backend = self.provider_registry.get_backend(provider_id)

            # The backend should have already polled if wait=True,
            # but if we're handling a deferred async task, fetch the result
            final_result = await backend.fetch_result(result.task_id)

            if final_result.success and final_result.image_data:
                metadata = ImageMetadata(
                    id=image_id,
                    filename="",
                    prompt=description,
                    style=style_id,
                    provider_id=provider_id,
                    width=final_result.width or 0,
                    height=final_result.height or 0,
                    created_at=datetime.utcnow().isoformat() + "Z",
                    discussion_id=discussion_id,
                    agent=agent,
                    generation_time_ms=final_result.generation_time_ms or 0,
                )

                await self.storage.save_image(
                    project_id=project_id,
                    image_data=final_result.image_data,
                    metadata=metadata,
                    image_id=image_id,
                    format=final_result.format,
                )

                await self.storage.update_request_status(
                    project_id=project_id,
                    image_id=image_id,
                    status="completed",
                )

                image_url = self.storage.get_image_url(project_id, image_id)

                self._broadcast("image_generation_complete", {
                    "request_id": image_id,
                    "image_url": image_url,
                    "metadata": {
                        "width": final_result.width,
                        "height": final_result.height,
                        "provider_id": provider_id,
                        "generation_time_ms": final_result.generation_time_ms,
                    },
                })

            else:
                error = final_result.error or "Failed to fetch result"
                await self.storage.update_request_status(
                    project_id=project_id,
                    image_id=image_id,
                    status="failed",
                    error=error,
                )

                self._broadcast("image_generation_error", {
                    "request_id": image_id,
                    "error": error,
                })

        except Exception as e:
            logger.exception(f"Failed to complete async generation {image_id}")

            await self.storage.update_request_status(
                project_id=project_id,
                image_id=image_id,
                status="failed",
                error=str(e),
            )

            self._broadcast("image_generation_error", {
                "request_id": image_id,
                "error": str(e),
            })

    async def get_status(self, project_id: str, image_id: str) -> GenerationResult:
        """Get the status of an image generation request.

        Args:
            project_id: Project identifier.
            image_id: Image identifier.

        Returns:
            GenerationResult with current status.
        """
        request = await self.storage.get_request_status(project_id, image_id)
        if request is None:
            return GenerationResult(
                success=False,
                image_id=image_id,
                error="Request not found",
            )

        metadata = await self.storage.get_image_metadata(project_id, image_id)

        if request.status == "completed" and metadata:
            image_url = self.storage.get_image_url(project_id, image_id)
            return GenerationResult(
                success=True,
                image_id=image_id,
                image_url=image_url,
                prompt=metadata.prompt,
                style_id=metadata.style,
                provider_id=metadata.provider_id,
                width=metadata.width,
                height=metadata.height,
                generation_time_ms=metadata.generation_time_ms,
            )

        if request.status == "failed":
            return GenerationResult(
                success=False,
                image_id=image_id,
                error=request.error,
            )

        # Still processing
        return GenerationResult(
            success=True,
            image_id=image_id,
            is_async=True,
            task_id=request.task_id,
        )


# Global service instance
_service: ImageService | None = None


def get_image_service() -> ImageService:
    """Get the global image service instance.

    Returns:
        The global ImageService instance.
    """
    global _service
    if _service is None:
        _service = ImageService()
    return _service


def reset_image_service() -> None:
    """Reset the global image service.

    Useful for testing or when configuration changes.
    """
    global _service
    _service = None
