"""OpenAI Images API backend for image generation."""

import base64
import logging
import time
from typing import Any

import httpx

from src.image.backends.base import (
    ImageBackend,
    ImageResult,
    TaskStatus,
    TaskStatusEnum,
)

logger = logging.getLogger(__name__)


class OpenAiBackend(ImageBackend):
    """Backend for OpenAI's Images API.

    This backend supports synchronous image generation using OpenAI's
    gpt-image-1 (DALL-E) model. Results are returned immediately.

    Configuration options:
        api_base: Base URL for the API (default: https://api.openai.com/v1)
        api_key_env: Environment variable name for the API key
        model: Model to use (default: gpt-image-1)
        default_size: Default image size (default: 1024x1024)
        default_quality: Default quality setting (default: standard)
    """

    DEFAULT_API_BASE = "https://api.openai.com/v1"
    DEFAULT_MODEL = "gpt-image-1"
    DEFAULT_SIZE = "1024x1024"
    DEFAULT_QUALITY = "standard"
    DEFAULT_TIMEOUT = 120.0

    # Valid size options for OpenAI Images API
    VALID_SIZES = {"1024x1024", "1024x1792", "1792x1024", "512x512", "256x256"}
    VALID_QUALITIES = {"standard", "hd"}

    def __init__(self, provider_id: str, config: dict[str, Any]) -> None:
        """Initialize the OpenAI backend.

        Args:
            provider_id: Unique identifier for this provider.
            config: Configuration dictionary with api_base, api_key, model, etc.
        """
        super().__init__(provider_id, config)

        self.api_base = config.get("api_base", self.DEFAULT_API_BASE).rstrip("/")
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", self.DEFAULT_MODEL)
        self.default_size = config.get("default_size", self.DEFAULT_SIZE)
        self.default_quality = config.get("default_quality", self.DEFAULT_QUALITY)
        self.timeout = config.get("timeout", self.DEFAULT_TIMEOUT)

        if not self.api_key:
            logger.warning(
                f"OpenAI backend '{provider_id}' initialized without API key"
            )

    @property
    def supports_sync(self) -> bool:
        """OpenAI Images API supports synchronous generation."""
        return True

    @property
    def supports_async(self) -> bool:
        """OpenAI Images API does not use task polling."""
        return False

    def _parse_size(self, size: str) -> tuple[int, int]:
        """Parse size string to width and height.

        Args:
            size: Size string like '1024x1024'.

        Returns:
            Tuple of (width, height).
        """
        try:
            width, height = size.split("x")
            return int(width), int(height)
        except (ValueError, AttributeError):
            return 1024, 1024

    def _validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Validate and normalize generation parameters.

        Args:
            params: Raw parameters from the request.

        Returns:
            Validated parameters for the API call.
        """
        validated = {}

        # Size
        size = params.get("size", self.default_size)
        if size not in self.VALID_SIZES:
            logger.warning(
                f"Invalid size '{size}', using default '{self.default_size}'"
            )
            size = self.default_size
        validated["size"] = size

        # Quality
        quality = params.get("quality", self.default_quality)
        if quality not in self.VALID_QUALITIES:
            logger.warning(
                f"Invalid quality '{quality}', using default '{self.default_quality}'"
            )
            quality = self.default_quality
        validated["quality"] = quality

        # Number of images (always 1 for now)
        validated["n"] = 1

        # Response format (b64_json for direct data access)
        validated["response_format"] = params.get("response_format", "b64_json")

        return validated

    async def generate(self, prompt: str, params: dict[str, Any]) -> ImageResult:
        """Generate an image using OpenAI's Images API.

        Args:
            prompt: The image generation prompt.
            params: Additional parameters (size, quality, etc.).

        Returns:
            ImageResult with the generated image data.
        """
        start_time = time.time()

        if not self.api_key:
            return ImageResult(
                success=False,
                prompt=prompt,
                provider_id=self.provider_id,
                error="API key not configured",
            )

        validated_params = self._validate_params(params)
        width, height = self._parse_size(validated_params["size"])

        request_body = {
            "model": self.model,
            "prompt": prompt,
            **validated_params,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.api_base}/images/generations",
                    json=request_body,
                    headers=headers,
                )

                if response.status_code != 200:
                    error_msg = f"API error: {response.status_code}"
                    try:
                        error_data = response.json()
                        if "error" in error_data:
                            error_msg = error_data["error"].get("message", error_msg)
                    except Exception:
                        error_msg = f"API error: {response.text}"

                    logger.error(f"OpenAI image generation failed: {error_msg}")
                    return ImageResult(
                        success=False,
                        prompt=prompt,
                        provider_id=self.provider_id,
                        error=error_msg,
                    )

                response_data = response.json()
                generation_time_ms = int((time.time() - start_time) * 1000)

                # Extract the image data
                if "data" not in response_data or len(response_data["data"]) == 0:
                    return ImageResult(
                        success=False,
                        prompt=prompt,
                        provider_id=self.provider_id,
                        error="No image data in response",
                    )

                image_info = response_data["data"][0]

                # Handle b64_json response
                if "b64_json" in image_info:
                    image_data = base64.b64decode(image_info["b64_json"])
                    return ImageResult(
                        success=True,
                        image_data=image_data,
                        width=width,
                        height=height,
                        format="png",
                        prompt=prompt,
                        revised_prompt=image_info.get("revised_prompt"),
                        generation_time_ms=generation_time_ms,
                        provider_id=self.provider_id,
                        metadata={"model": self.model},
                    )

                # Handle URL response
                if "url" in image_info:
                    return ImageResult(
                        success=True,
                        image_url=image_info["url"],
                        width=width,
                        height=height,
                        format="png",
                        prompt=prompt,
                        revised_prompt=image_info.get("revised_prompt"),
                        generation_time_ms=generation_time_ms,
                        provider_id=self.provider_id,
                        metadata={"model": self.model},
                    )

                return ImageResult(
                    success=False,
                    prompt=prompt,
                    provider_id=self.provider_id,
                    error="Unknown response format",
                )

        except httpx.TimeoutException:
            logger.error(f"OpenAI image generation timed out after {self.timeout}s")
            return ImageResult(
                success=False,
                prompt=prompt,
                provider_id=self.provider_id,
                error=f"Request timed out after {self.timeout} seconds",
            )
        except httpx.RequestError as e:
            logger.error(f"OpenAI image generation request error: {e}")
            return ImageResult(
                success=False,
                prompt=prompt,
                provider_id=self.provider_id,
                error=f"Request error: {str(e)}",
            )
        except Exception as e:
            logger.exception("Unexpected error in OpenAI image generation")
            return ImageResult(
                success=False,
                prompt=prompt,
                provider_id=self.provider_id,
                error=f"Unexpected error: {str(e)}",
            )

    async def check_status(self, task_id: str) -> TaskStatus:
        """Not supported for sync-only backend.

        Raises:
            NotImplementedError: This backend does not support async operations.
        """
        raise NotImplementedError("OpenAI backend does not support async task polling")

    async def fetch_result(self, task_id: str) -> ImageResult:
        """Not supported for sync-only backend.

        Raises:
            NotImplementedError: This backend does not support async operations.
        """
        raise NotImplementedError("OpenAI backend does not support async task polling")
