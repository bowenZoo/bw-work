"""Base classes for image generation backends."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TaskStatusEnum(str, Enum):
    """Status of an async image generation task."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskStatus:
    """Status information for an async image generation task.

    Attributes:
        task_id: The unique identifier for the task.
        status: Current status of the task.
        progress: Optional progress percentage (0-100).
        error: Error message if the task failed.
        result_url: URL to fetch the result when completed.
        metadata: Additional status metadata from the backend.
    """

    task_id: str
    status: TaskStatusEnum
    progress: int | None = None
    error: str | None = None
    result_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImageResult:
    """Result of an image generation request.

    Attributes:
        success: Whether the generation was successful.
        image_data: Raw image data bytes (if available).
        image_url: URL to the generated image (if available).
        task_id: Task ID for async backends (if async).
        width: Width of the generated image.
        height: Height of the generated image.
        format: Image format (e.g., 'png', 'jpg').
        prompt: The prompt used for generation.
        revised_prompt: The revised/enhanced prompt (if backend modified it).
        generation_time_ms: Time taken to generate in milliseconds.
        provider_id: ID of the provider that generated the image.
        error: Error message if generation failed.
        metadata: Additional metadata from the backend.
        created_at: Timestamp when the result was created.
    """

    success: bool
    image_data: bytes | None = None
    image_url: str | None = None
    task_id: str | None = None
    width: int | None = None
    height: int | None = None
    format: str = "png"
    prompt: str = ""
    revised_prompt: str | None = None
    generation_time_ms: int | None = None
    provider_id: str = ""
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_async(self) -> bool:
        """Check if this result is from an async generation (has task_id)."""
        return self.task_id is not None and self.image_data is None


class ImageBackend(ABC):
    """Abstract base class for image generation backends.

    All image generation backends must implement this interface.
    Backends can support synchronous generation, asynchronous generation
    (via task polling), or both.
    """

    def __init__(self, provider_id: str, config: dict[str, Any]) -> None:
        """Initialize the backend with provider configuration.

        Args:
            provider_id: Unique identifier for this provider instance.
            config: Provider configuration dictionary.
        """
        self.provider_id = provider_id
        self.config = config

    @abstractmethod
    async def generate(self, prompt: str, params: dict[str, Any]) -> ImageResult:
        """Generate an image from a prompt.

        For sync backends, this returns the completed result directly.
        For async backends, this submits the task and returns a result
        with task_id set for later polling.

        Args:
            prompt: The image generation prompt.
            params: Additional parameters (size, quality, style, etc.).

        Returns:
            ImageResult with either the image data or task_id for polling.
        """
        pass

    @abstractmethod
    async def check_status(self, task_id: str) -> TaskStatus:
        """Check the status of an async generation task.

        For sync backends, this should raise NotImplementedError.
        For async backends, this polls the task status.

        Args:
            task_id: The task ID returned from generate().

        Returns:
            TaskStatus with current status information.

        Raises:
            NotImplementedError: If the backend only supports sync generation.
        """
        pass

    @abstractmethod
    async def fetch_result(self, task_id: str) -> ImageResult:
        """Fetch the completed result for an async task.

        For sync backends, this should raise NotImplementedError.
        For async backends, this downloads the completed image.

        Args:
            task_id: The task ID returned from generate().

        Returns:
            ImageResult with the completed image data.

        Raises:
            NotImplementedError: If the backend only supports sync generation.
            ValueError: If the task is not completed.
        """
        pass

    @property
    @abstractmethod
    def supports_sync(self) -> bool:
        """Check if this backend supports synchronous generation.

        Returns:
            True if the backend can return results immediately.
        """
        pass

    @property
    @abstractmethod
    def supports_async(self) -> bool:
        """Check if this backend supports asynchronous generation.

        Returns:
            True if the backend uses task polling for generation.
        """
        pass

    @property
    def name(self) -> str:
        """Get the human-readable name of this backend."""
        return self.__class__.__name__

    def __repr__(self) -> str:
        """Return string representation of the backend."""
        return f"<{self.name}(provider_id='{self.provider_id}')>"
