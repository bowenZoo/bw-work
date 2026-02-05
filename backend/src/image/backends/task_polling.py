"""Task polling image generation backend.

This backend supports image generation services that use an async
task-based approach: submit a request, poll for status, fetch result.
"""

import asyncio
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


class TaskPollingBackend(ImageBackend):
    """Backend for task-based async image generation APIs.

    This backend works with services that:
    1. Accept a generation request and return a task_id
    2. Provide a status endpoint to check task progress
    3. Provide a result endpoint to download the completed image

    The polling logic is configurable through the provider config.

    Configuration options:
        api_base: Base URL for the API (required)
        api_key: API key for authentication
        api_key_env: Environment variable name for the API key
        submit_path: Path for submitting generation requests (default: /api/generate)
        status_path: Path for checking task status, {task_id} placeholder (default: /api/tasks/{task_id})
        result_path: Path for fetching results, {task_id} placeholder (default: /api/tasks/{task_id}/result)
        poll_interval_sec: Seconds between status polls (default: 2)
        poll_timeout_sec: Maximum seconds to poll before timeout (default: 120)
        auth_header: Header name for authentication (default: Authorization)
        auth_prefix: Prefix for auth value (default: Bearer)
        task_id_field: Field name in submit response containing task_id (default: task_id)
        status_field: Field name in status response containing status (default: status)
        status_completed: Value indicating task completion (default: completed)
        status_failed: Value indicating task failure (default: failed)
        error_field: Field name for error messages (default: error)
        image_field: Field name for image data in result (default: image)
        image_url_field: Field name for image URL in result (default: url)
    """

    DEFAULT_POLL_INTERVAL = 2
    DEFAULT_POLL_TIMEOUT = 120
    DEFAULT_REQUEST_TIMEOUT = 30.0

    def __init__(self, provider_id: str, config: dict[str, Any]) -> None:
        """Initialize the task polling backend.

        Args:
            provider_id: Unique identifier for this provider.
            config: Configuration dictionary.
        """
        super().__init__(provider_id, config)

        self.api_base = config.get("api_base", "").rstrip("/")
        self.api_key = config.get("api_key", "")

        # Paths
        self.submit_path = config.get("submit_path", "/api/generate")
        self.status_path = config.get("status_path", "/api/tasks/{task_id}")
        self.result_path = config.get("result_path", "/api/tasks/{task_id}/result")

        # Polling settings
        self.poll_interval_sec = config.get("poll_interval_sec", self.DEFAULT_POLL_INTERVAL)
        self.poll_timeout_sec = config.get("poll_timeout_sec", self.DEFAULT_POLL_TIMEOUT)
        self.request_timeout = config.get("request_timeout", self.DEFAULT_REQUEST_TIMEOUT)

        # Authentication
        self.auth_header = config.get("auth_header", "Authorization")
        self.auth_prefix = config.get("auth_prefix", "Bearer")
        self.extra_headers = config.get("extra_headers", {})

        # Response field mappings
        self.task_id_field = config.get("task_id_field", "task_id")
        self.status_field = config.get("status_field", "status")
        self.status_completed = config.get("status_completed", "completed")
        self.status_failed = config.get("status_failed", "failed")
        self.status_processing = config.get("status_processing", "processing")
        self.error_field = config.get("error_field", "error")
        self.image_field = config.get("image_field", "image")
        self.image_url_field = config.get("image_url_field", "url")
        self.progress_field = config.get("progress_field", "progress")

        # Request body field mappings
        self.prompt_field = config.get("prompt_field", "prompt")
        self.extra_params = config.get("extra_params", {})

        if not self.api_base:
            logger.warning(
                f"Task polling backend '{provider_id}' initialized without api_base"
            )

    @property
    def supports_sync(self) -> bool:
        """Task polling backends support sync through internal polling."""
        return True

    @property
    def supports_async(self) -> bool:
        """Task polling backends support async operations."""
        return True

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

        headers.update(self.extra_headers)
        return headers

    def _build_url(self, path: str, task_id: str | None = None) -> str:
        """Build full URL for an API path.

        Args:
            path: API path with optional {task_id} placeholder.
            task_id: Task ID to substitute in path.

        Returns:
            Full URL.
        """
        if task_id:
            path = path.replace("{task_id}", task_id)
        return f"{self.api_base}{path}"

    async def _submit_task(
        self, prompt: str, params: dict[str, Any]
    ) -> tuple[str | None, str | None]:
        """Submit a generation task.

        Args:
            prompt: The image generation prompt.
            params: Additional parameters.

        Returns:
            Tuple of (task_id, error_message).
        """
        url = self._build_url(self.submit_path)
        headers = self._build_headers()

        body = {
            self.prompt_field: prompt,
            **self.extra_params,
            **params,
        }

        try:
            async with httpx.AsyncClient(timeout=self.request_timeout) as client:
                response = await client.post(url, json=body, headers=headers)

                if response.status_code not in (200, 201, 202):
                    error_msg = f"Submit failed with status {response.status_code}"
                    try:
                        error_data = response.json()
                        if self.error_field in error_data:
                            error_msg = str(error_data[self.error_field])
                    except Exception:
                        error_msg = f"Submit failed: {response.text}"
                    return None, error_msg

                data = response.json()
                task_id = data.get(self.task_id_field)

                if not task_id:
                    return None, f"No {self.task_id_field} in response"

                return task_id, None

        except httpx.TimeoutException:
            return None, "Submit request timed out"
        except httpx.RequestError as e:
            return None, f"Submit request error: {str(e)}"
        except Exception as e:
            return None, f"Submit unexpected error: {str(e)}"

    async def check_status(self, task_id: str) -> TaskStatus:
        """Check the status of an async generation task.

        Args:
            task_id: The task ID returned from generate().

        Returns:
            TaskStatus with current status information.
        """
        url = self._build_url(self.status_path, task_id)
        headers = self._build_headers()

        try:
            async with httpx.AsyncClient(timeout=self.request_timeout) as client:
                response = await client.get(url, headers=headers)

                if response.status_code != 200:
                    return TaskStatus(
                        task_id=task_id,
                        status=TaskStatusEnum.FAILED,
                        error=f"Status check failed with code {response.status_code}",
                    )

                data = response.json()
                status_value = data.get(self.status_field, "")
                progress = data.get(self.progress_field)
                error = data.get(self.error_field)

                # Map status value to enum
                if status_value == self.status_completed:
                    status = TaskStatusEnum.COMPLETED
                elif status_value == self.status_failed:
                    status = TaskStatusEnum.FAILED
                elif status_value == self.status_processing:
                    status = TaskStatusEnum.PROCESSING
                else:
                    status = TaskStatusEnum.PENDING

                # Some APIs include the result URL in status response
                result_url = data.get(self.image_url_field)

                return TaskStatus(
                    task_id=task_id,
                    status=status,
                    progress=progress,
                    error=error,
                    result_url=result_url,
                    metadata=data,
                )

        except httpx.TimeoutException:
            return TaskStatus(
                task_id=task_id,
                status=TaskStatusEnum.FAILED,
                error="Status check timed out",
            )
        except httpx.RequestError as e:
            return TaskStatus(
                task_id=task_id,
                status=TaskStatusEnum.FAILED,
                error=f"Status check request error: {str(e)}",
            )
        except Exception as e:
            return TaskStatus(
                task_id=task_id,
                status=TaskStatusEnum.FAILED,
                error=f"Status check unexpected error: {str(e)}",
            )

    async def fetch_result(self, task_id: str) -> ImageResult:
        """Fetch the completed result for an async task.

        Args:
            task_id: The task ID returned from generate().

        Returns:
            ImageResult with the completed image data.

        Raises:
            ValueError: If the task is not completed.
        """
        url = self._build_url(self.result_path, task_id)
        headers = self._build_headers()

        try:
            async with httpx.AsyncClient(timeout=self.request_timeout) as client:
                response = await client.get(url, headers=headers)

                if response.status_code != 200:
                    return ImageResult(
                        success=False,
                        task_id=task_id,
                        provider_id=self.provider_id,
                        error=f"Fetch result failed with code {response.status_code}",
                    )

                # Check content type to determine response format
                content_type = response.headers.get("content-type", "")

                # If response is direct image data
                if content_type.startswith("image/"):
                    format_type = "png"
                    if "jpeg" in content_type or "jpg" in content_type:
                        format_type = "jpg"
                    elif "webp" in content_type:
                        format_type = "webp"

                    return ImageResult(
                        success=True,
                        image_data=response.content,
                        task_id=task_id,
                        format=format_type,
                        provider_id=self.provider_id,
                    )

                # If response is JSON
                data = response.json()

                # Check for base64 image data
                if self.image_field in data:
                    image_data = data[self.image_field]
                    # Decode if base64
                    if isinstance(image_data, str):
                        image_data = base64.b64decode(image_data)
                    return ImageResult(
                        success=True,
                        image_data=image_data,
                        task_id=task_id,
                        format="png",
                        provider_id=self.provider_id,
                        metadata=data,
                    )

                # Check for image URL
                if self.image_url_field in data:
                    return ImageResult(
                        success=True,
                        image_url=data[self.image_url_field],
                        task_id=task_id,
                        provider_id=self.provider_id,
                        metadata=data,
                    )

                return ImageResult(
                    success=False,
                    task_id=task_id,
                    provider_id=self.provider_id,
                    error="No image data in result response",
                )

        except httpx.TimeoutException:
            return ImageResult(
                success=False,
                task_id=task_id,
                provider_id=self.provider_id,
                error="Fetch result timed out",
            )
        except httpx.RequestError as e:
            return ImageResult(
                success=False,
                task_id=task_id,
                provider_id=self.provider_id,
                error=f"Fetch result request error: {str(e)}",
            )
        except Exception as e:
            return ImageResult(
                success=False,
                task_id=task_id,
                provider_id=self.provider_id,
                error=f"Fetch result unexpected error: {str(e)}",
            )

    async def _poll_until_complete(self, task_id: str) -> TaskStatus:
        """Poll task status until completion or timeout.

        Args:
            task_id: The task ID to poll.

        Returns:
            Final TaskStatus.
        """
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time
            if elapsed > self.poll_timeout_sec:
                return TaskStatus(
                    task_id=task_id,
                    status=TaskStatusEnum.FAILED,
                    error=f"Polling timed out after {self.poll_timeout_sec} seconds",
                )

            status = await self.check_status(task_id)

            if status.status in (TaskStatusEnum.COMPLETED, TaskStatusEnum.FAILED):
                return status

            await asyncio.sleep(self.poll_interval_sec)

    async def generate(self, prompt: str, params: dict[str, Any]) -> ImageResult:
        """Generate an image using the task polling API.

        This method:
        1. Submits a generation task
        2. Polls for completion
        3. Fetches and returns the result

        For non-blocking usage, call with wait=False in params to get
        the task_id immediately without waiting for completion.

        Args:
            prompt: The image generation prompt.
            params: Additional parameters. Set wait=False for async.

        Returns:
            ImageResult with the generated image data or task_id.
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

        # Submit the task
        task_id, error = await self._submit_task(prompt, params)
        if error:
            return ImageResult(
                success=False,
                prompt=prompt,
                provider_id=self.provider_id,
                error=error,
            )

        # If wait=False, return immediately with task_id
        wait = params.get("wait", True)
        if not wait:
            return ImageResult(
                success=True,
                task_id=task_id,
                prompt=prompt,
                provider_id=self.provider_id,
            )

        # Poll until complete
        final_status = await self._poll_until_complete(task_id)

        if final_status.status == TaskStatusEnum.FAILED:
            return ImageResult(
                success=False,
                task_id=task_id,
                prompt=prompt,
                provider_id=self.provider_id,
                error=final_status.error or "Task failed",
            )

        # Fetch the result
        result = await self.fetch_result(task_id)
        result.prompt = prompt
        result.generation_time_ms = int((time.time() - start_time) * 1000)

        return result
