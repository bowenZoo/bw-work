"""OpenAI-compatible image generation backend.

This backend supports any image generation service that follows
the OpenAI Images API format, but may use different endpoints,
models, or additional parameters.
"""

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


class OpenAiCompatibleBackend(ImageBackend):
    """Backend for OpenAI-compatible image generation APIs.

    This backend works with services that follow the OpenAI Images API
    format but may have different base URLs, models, and parameters.
    Configuration is fully driven by the provider config.

    Configuration options:
        api_base: Base URL for the API (required)
        api_key_env: Environment variable name for the API key
        api_key: Direct API key (alternative to api_key_env)
        model: Model name to use
        extra_params: Additional parameters to include in requests
        extra_headers: Additional headers to include in requests
        default_size: Default image size
        timeout: Request timeout in seconds
    """

    DEFAULT_TIMEOUT = 120.0
    DEFAULT_SIZE = "1024x1024"

    def __init__(self, provider_id: str, config: dict[str, Any]) -> None:
        """Initialize the OpenAI-compatible backend.

        Args:
            provider_id: Unique identifier for this provider.
            config: Configuration dictionary.
        """
        super().__init__(provider_id, config)

        self.api_base = config.get("api_base", "").rstrip("/")
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "")
        self.extra_params = config.get("extra_params", {})
        self.extra_headers = config.get("extra_headers", {})
        self.default_size = config.get("default_size", self.DEFAULT_SIZE)
        self.timeout = config.get("timeout", self.DEFAULT_TIMEOUT)
        self.auth_header = config.get("auth_header", "Authorization")
        self.auth_prefix = config.get("auth_prefix", "Bearer")

        if not self.api_base:
            logger.warning(
                f"OpenAI-compatible backend '{provider_id}' initialized without api_base"
            )

        if not self.api_key:
            logger.warning(
                f"OpenAI-compatible backend '{provider_id}' initialized without API key"
            )

    @property
    def supports_sync(self) -> bool:
        """OpenAI-compatible APIs typically support synchronous generation."""
        return True

    @property
    def supports_async(self) -> bool:
        """OpenAI-compatible APIs typically do not use task polling."""
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

    def _build_headers(self) -> dict[str, str]:
        """Build request headers.

        Returns:
            Headers dictionary.
        """
        headers = {
            "Content-Type": "application/json",
        }

        if self.api_key:
            auth_value = f"{self.auth_prefix} {self.api_key}" if self.auth_prefix else self.api_key
            headers[self.auth_header] = auth_value

        # Add any extra headers from config
        headers.update(self.extra_headers)

        return headers

    def _build_request_body(self, prompt: str, params: dict[str, Any]) -> dict[str, Any]:
        """Build the request body for the API call.

        Args:
            prompt: The image generation prompt.
            params: Additional parameters.

        Returns:
            Request body dictionary.
        """
        body: dict[str, Any] = {
            "prompt": prompt,
        }

        # Add model if specified
        if self.model:
            body["model"] = self.model

        # Add size parameter
        size = params.get("size", self.default_size)
        body["size"] = size

        # Add quality if specified
        if "quality" in params:
            body["quality"] = params["quality"]

        # Number of images
        body["n"] = params.get("n", 1)

        # Response format
        body["response_format"] = params.get("response_format", "b64_json")

        # Add any extra params from config (can be overridden by params)
        for key, value in self.extra_params.items():
            if key not in body:
                body[key] = value

        # Add any additional params passed at request time
        for key, value in params.items():
            if key not in body:
                body[key] = value

        return body

    async def generate(self, prompt: str, params: dict[str, Any]) -> ImageResult:
        """Generate an image using the OpenAI-compatible API.

        Args:
            prompt: The image generation prompt.
            params: Additional parameters.

        Returns:
            ImageResult with the generated image data.
        """
        start_time = time.time()

        if not self.api_base:
            return ImageResult(
                success=False,
                prompt=prompt,
                provider_id=self.provider_id,
                error="API base URL not configured",
            )

        if not self.api_key:
            return ImageResult(
                success=False,
                prompt=prompt,
                provider_id=self.provider_id,
                error="API key not configured",
            )

        request_body = self._build_request_body(prompt, params)
        headers = self._build_headers()

        size = request_body.get("size", self.default_size)
        width, height = self._parse_size(size)

        endpoint = f"{self.api_base}/images/generations"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint,
                    json=request_body,
                    headers=headers,
                )

                if response.status_code != 200:
                    error_msg = f"API error: {response.status_code}"
                    try:
                        error_data = response.json()
                        if "error" in error_data:
                            if isinstance(error_data["error"], dict):
                                error_msg = error_data["error"].get("message", error_msg)
                            else:
                                error_msg = str(error_data["error"])
                    except Exception:
                        error_msg = f"API error: {response.text}"

                    logger.error(
                        f"OpenAI-compatible image generation failed: {error_msg}"
                    )
                    return ImageResult(
                        success=False,
                        prompt=prompt,
                        provider_id=self.provider_id,
                        error=error_msg,
                    )

                response_data = response.json()
                generation_time_ms = int((time.time() - start_time) * 1000)

                # Extract the image data - handle various response formats
                data = response_data.get("data", [])
                if not data:
                    # Some APIs might return the image directly at the top level
                    if "b64_json" in response_data or "url" in response_data:
                        data = [response_data]
                    else:
                        return ImageResult(
                            success=False,
                            prompt=prompt,
                            provider_id=self.provider_id,
                            error="No image data in response",
                        )

                image_info = data[0]

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
                        metadata={
                            "model": self.model,
                            "endpoint": endpoint,
                        },
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
                        metadata={
                            "model": self.model,
                            "endpoint": endpoint,
                        },
                    )

                return ImageResult(
                    success=False,
                    prompt=prompt,
                    provider_id=self.provider_id,
                    error="Unknown response format",
                )

        except httpx.TimeoutException:
            logger.error(
                f"OpenAI-compatible image generation timed out after {self.timeout}s"
            )
            return ImageResult(
                success=False,
                prompt=prompt,
                provider_id=self.provider_id,
                error=f"Request timed out after {self.timeout} seconds",
            )
        except httpx.RequestError as e:
            logger.error(f"OpenAI-compatible image generation request error: {e}")
            return ImageResult(
                success=False,
                prompt=prompt,
                provider_id=self.provider_id,
                error=f"Request error: {str(e)}",
            )
        except Exception as e:
            logger.exception("Unexpected error in OpenAI-compatible image generation")
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
        raise NotImplementedError(
            "OpenAI-compatible backend does not support async task polling"
        )

    async def fetch_result(self, task_id: str) -> ImageResult:
        """Not supported for sync-only backend.

        Raises:
            NotImplementedError: This backend does not support async operations.
        """
        raise NotImplementedError(
            "OpenAI-compatible backend does not support async task polling"
        )
