"""Image API routes for image generation and management."""

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.image.service import GenerationResult, ImageService, get_image_service
from src.image.storage import ImageStorage
from src.image.style_manager import StyleManager, get_style_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/images", tags=["images"])


# Request/Response models
class GenerateImageRequest(BaseModel):
    """Request body for image generation."""

    description: str = Field(..., description="Text description of the image to generate")
    style_id: str = Field(default="concept_character", description="Style template ID")
    project_id: str = Field(..., description="Project ID for storage")
    discussion_id: str | None = Field(default=None, description="Optional discussion ID")
    provider_id: str | None = Field(default=None, description="Optional provider ID")
    wait: bool = Field(default=True, description="Whether to wait for completion")


class GenerationResponse(BaseModel):
    """Response for image generation request."""

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

    @classmethod
    def from_result(cls, result: GenerationResult) -> "GenerationResponse":
        """Create from GenerationResult."""
        return cls(
            success=result.success,
            image_id=result.image_id,
            image_url=result.image_url,
            prompt=result.prompt,
            enhanced_prompt=result.enhanced_prompt,
            style_id=result.style_id,
            provider_id=result.provider_id,
            width=result.width,
            height=result.height,
            generation_time_ms=result.generation_time_ms,
            error=result.error,
            is_async=result.is_async,
            task_id=result.task_id,
        )


class ImageMetadataResponse(BaseModel):
    """Response for image metadata."""

    id: str
    filename: str
    prompt: str
    style: str
    provider_id: str
    width: int
    height: int
    created_at: str
    discussion_id: str | None = None
    agent: str = ""
    generation_time_ms: int = 0


class StyleResponse(BaseModel):
    """Response for a style template."""

    id: str
    name: str
    description: str
    recommended_backends: list[str]
    default_params: dict[str, Any]


class StyleListResponse(BaseModel):
    """Response for listing styles."""

    styles: list[StyleResponse]
    default_style: str


# Dependency injection
def get_image_service_dep() -> ImageService:
    """Get the image service dependency."""
    return get_image_service()


def get_style_manager_dep() -> StyleManager:
    """Get the style manager dependency."""
    return get_style_manager()


def get_storage_dep() -> ImageStorage:
    """Get the storage dependency."""
    return get_image_service().storage


# Routes
@router.post("/generate", response_model=GenerationResponse)
async def generate_image(
    request: GenerateImageRequest,
    background_tasks: BackgroundTasks,
) -> GenerationResponse:
    """Request image generation.

    Args:
        request: The generation request parameters.
        background_tasks: FastAPI background tasks.

    Returns:
        GenerationResponse with the result or async task info.
    """
    service = get_image_service_dep()

    try:
        result = await service.generate(
            description=request.description,
            project_id=request.project_id,
            style_id=request.style_id,
            provider_id=request.provider_id,
            discussion_id=request.discussion_id,
            wait=request.wait,
        )

        return GenerationResponse.from_result(result)

    except Exception as e:
        logger.exception("Image generation failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{request_id}", response_model=GenerationResponse)
async def get_generation_status(
    request_id: str,
    project_id: str,
) -> GenerationResponse:
    """Get the status of an image generation request.

    Args:
        request_id: The image/request ID.
        project_id: The project ID.

    Returns:
        GenerationResponse with current status.
    """
    service = get_image_service_dep()

    try:
        result = await service.get_status(project_id, request_id)
        return GenerationResponse.from_result(result)
    except Exception as e:
        logger.exception("Failed to get generation status")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}", response_model=list[ImageMetadataResponse])
async def list_project_images(
    project_id: str,
) -> list[ImageMetadataResponse]:
    """List all images for a project.

    Args:
        project_id: The project ID.

    Returns:
        List of image metadata.
    """
    storage = get_storage_dep()

    try:
        images = await storage.list_images(project_id)
        return [
            ImageMetadataResponse(
                id=img.id,
                filename=img.filename,
                prompt=img.prompt,
                style=img.style,
                provider_id=img.provider_id,
                width=img.width,
                height=img.height,
                created_at=img.created_at,
                discussion_id=img.discussion_id,
                agent=img.agent,
                generation_time_ms=img.generation_time_ms,
            )
            for img in images
        ]
    except Exception as e:
        logger.exception("Failed to list project images")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/{image_id}")
async def get_image(
    project_id: str,
    image_id: str,
) -> Response:
    """Get an image file.

    Args:
        project_id: The project ID.
        image_id: The image ID.

    Returns:
        The image file.
    """
    storage = get_storage_dep()

    try:
        image_path = await storage.get_image_path(project_id, image_id)
        if image_path is None:
            raise HTTPException(status_code=404, detail="Image not found")

        # Determine content type from extension
        suffix = image_path.suffix.lower()
        content_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }
        content_type = content_types.get(suffix, "image/png")

        return FileResponse(
            path=image_path,
            media_type=content_type,
            filename=image_path.name,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get image")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/{image_id}/metadata", response_model=ImageMetadataResponse)
async def get_image_metadata(
    project_id: str,
    image_id: str,
) -> ImageMetadataResponse:
    """Get metadata for an image.

    Args:
        project_id: The project ID.
        image_id: The image ID.

    Returns:
        Image metadata.
    """
    storage = get_storage_dep()

    try:
        metadata = await storage.get_image_metadata(project_id, image_id)
        if metadata is None:
            raise HTTPException(status_code=404, detail="Image not found")

        return ImageMetadataResponse(
            id=metadata.id,
            filename=metadata.filename,
            prompt=metadata.prompt,
            style=metadata.style,
            provider_id=metadata.provider_id,
            width=metadata.width,
            height=metadata.height,
            created_at=metadata.created_at,
            discussion_id=metadata.discussion_id,
            agent=metadata.agent,
            generation_time_ms=metadata.generation_time_ms,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get image metadata")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/{project_id}/{image_id}")
async def delete_image(
    project_id: str,
    image_id: str,
) -> dict[str, bool]:
    """Delete an image.

    Args:
        project_id: The project ID.
        image_id: The image ID.

    Returns:
        Success status.
    """
    storage = get_storage_dep()

    try:
        deleted = await storage.delete_image(project_id, image_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Image not found")
        return {"deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to delete image")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/styles", response_model=StyleListResponse)
async def list_styles() -> StyleListResponse:
    """List available image generation styles.

    Returns:
        List of available styles.
    """
    style_manager = get_style_manager_dep()

    try:
        styles = style_manager.get_all_styles()
        return StyleListResponse(
            styles=[
                StyleResponse(
                    id=s.id,
                    name=s.name,
                    description=s.description,
                    recommended_backends=s.recommended_backends,
                    default_params=s.default_params,
                )
                for s in styles
            ],
            default_style=style_manager.default_style,
        )
    except Exception as e:
        logger.exception("Failed to list styles")
        raise HTTPException(status_code=500, detail=str(e))
