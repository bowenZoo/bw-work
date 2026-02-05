"""Tests for image generation backends."""

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.image.backends.base import ImageResult, TaskStatus, TaskStatusEnum
from src.image.backends.openai import OpenAiBackend
from src.image.backends.openai_compatible import OpenAiCompatibleBackend


class TestOpenAiBackend:
    """Tests for the OpenAI Images backend."""

    @pytest.fixture
    def backend(self):
        """Create a test backend instance."""
        config = {
            "api_key": "test-api-key",
            "model": "gpt-image-1",
            "default_size": "1024x1024",
            "default_quality": "standard",
        }
        return OpenAiBackend(provider_id="test_openai", config=config)

    @pytest.fixture
    def backend_no_key(self):
        """Create a backend instance without API key."""
        config = {}
        return OpenAiBackend(provider_id="test_openai_no_key", config=config)

    def test_supports_sync(self, backend):
        """Test that backend supports sync generation."""
        assert backend.supports_sync is True

    def test_supports_async(self, backend):
        """Test that backend does not support async generation."""
        assert backend.supports_async is False

    def test_parse_size(self, backend):
        """Test size string parsing."""
        assert backend._parse_size("1024x1024") == (1024, 1024)
        assert backend._parse_size("1024x1792") == (1024, 1792)
        assert backend._parse_size("invalid") == (1024, 1024)

    def test_validate_params_defaults(self, backend):
        """Test parameter validation with defaults."""
        params = backend._validate_params({})
        assert params["size"] == "1024x1024"
        assert params["quality"] == "standard"
        assert params["n"] == 1
        assert params["response_format"] == "b64_json"

    def test_validate_params_custom(self, backend):
        """Test parameter validation with custom values."""
        params = backend._validate_params({
            "size": "1024x1792",
            "quality": "hd",
        })
        assert params["size"] == "1024x1792"
        assert params["quality"] == "hd"

    def test_validate_params_invalid_size(self, backend):
        """Test parameter validation with invalid size falls back to default."""
        params = backend._validate_params({"size": "2048x2048"})
        assert params["size"] == "1024x1024"

    def test_validate_params_invalid_quality(self, backend):
        """Test parameter validation with invalid quality falls back to default."""
        params = backend._validate_params({"quality": "ultra"})
        assert params["quality"] == "standard"

    @pytest.mark.asyncio
    async def test_generate_no_api_key(self, backend_no_key):
        """Test generate fails gracefully without API key."""
        result = await backend_no_key.generate("test prompt", {})
        assert result.success is False
        assert "API key not configured" in result.error

    @pytest.mark.asyncio
    async def test_generate_success_b64_json(self, backend):
        """Test successful generation with b64_json response."""
        # Create a simple 1x1 PNG image as base64
        test_image_b64 = base64.b64encode(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f"
            b"\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        ).decode()

        mock_response_data = {
            "data": [
                {
                    "b64_json": test_image_b64,
                    "revised_prompt": "enhanced test prompt",
                }
            ]
        }

        with patch("src.image.backends.openai.httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await backend.generate("test prompt", {})

            assert result.success is True
            assert result.image_data is not None
            assert result.width == 1024
            assert result.height == 1024
            assert result.format == "png"
            assert result.prompt == "test prompt"
            assert result.revised_prompt == "enhanced test prompt"
            assert result.provider_id == "test_openai"
            assert result.generation_time_ms is not None

    @pytest.mark.asyncio
    async def test_generate_success_url_response(self, backend):
        """Test successful generation with URL response."""
        mock_response_data = {
            "data": [
                {
                    "url": "https://example.com/image.png",
                    "revised_prompt": "enhanced test prompt",
                }
            ]
        }

        with patch("src.image.backends.openai.httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await backend.generate(
                "test prompt",
                {"response_format": "url"},
            )

            assert result.success is True
            assert result.image_url == "https://example.com/image.png"

    @pytest.mark.asyncio
    async def test_generate_api_error(self, backend):
        """Test handling of API errors."""
        with patch("src.image.backends.openai.httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.json.return_value = {
                "error": {"message": "Invalid prompt"}
            }

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await backend.generate("test prompt", {})

            assert result.success is False
            assert "Invalid prompt" in result.error

    @pytest.mark.asyncio
    async def test_generate_empty_response(self, backend):
        """Test handling of empty response data."""
        mock_response_data = {"data": []}

        with patch("src.image.backends.openai.httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await backend.generate("test prompt", {})

            assert result.success is False
            assert "No image data" in result.error

    @pytest.mark.asyncio
    async def test_generate_timeout(self, backend):
        """Test handling of request timeout."""
        import httpx

        with patch("src.image.backends.openai.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.TimeoutException("Connection timeout")
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await backend.generate("test prompt", {})

            assert result.success is False
            assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_check_status_not_supported(self, backend):
        """Test that check_status raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            await backend.check_status("task_123")

    @pytest.mark.asyncio
    async def test_fetch_result_not_supported(self, backend):
        """Test that fetch_result raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            await backend.fetch_result("task_123")

    def test_repr(self, backend):
        """Test string representation."""
        assert "OpenAiBackend" in repr(backend)
        assert "test_openai" in repr(backend)

    def test_name(self, backend):
        """Test backend name property."""
        assert backend.name == "OpenAiBackend"


class TestImageResult:
    """Tests for the ImageResult dataclass."""

    def test_is_async_with_task_id(self):
        """Test is_async when task_id is set but no image data."""
        result = ImageResult(
            success=True,
            task_id="task_123",
            prompt="test",
        )
        assert result.is_async is True

    def test_is_async_with_image_data(self):
        """Test is_async when both task_id and image_data are set."""
        result = ImageResult(
            success=True,
            task_id="task_123",
            image_data=b"test",
            prompt="test",
        )
        assert result.is_async is False

    def test_is_async_no_task_id(self):
        """Test is_async when no task_id."""
        result = ImageResult(
            success=True,
            image_data=b"test",
            prompt="test",
        )
        assert result.is_async is False


class TestTaskStatus:
    """Tests for the TaskStatus dataclass."""

    def test_task_status_pending(self):
        """Test creating a pending task status."""
        status = TaskStatus(
            task_id="task_123",
            status=TaskStatusEnum.PENDING,
        )
        assert status.task_id == "task_123"
        assert status.status == TaskStatusEnum.PENDING
        assert status.progress is None
        assert status.error is None

    def test_task_status_completed(self):
        """Test creating a completed task status."""
        status = TaskStatus(
            task_id="task_123",
            status=TaskStatusEnum.COMPLETED,
            progress=100,
            result_url="https://example.com/result",
        )
        assert status.status == TaskStatusEnum.COMPLETED
        assert status.progress == 100
        assert status.result_url == "https://example.com/result"

    def test_task_status_failed(self):
        """Test creating a failed task status."""
        status = TaskStatus(
            task_id="task_123",
            status=TaskStatusEnum.FAILED,
            error="Generation failed",
        )
        assert status.status == TaskStatusEnum.FAILED
        assert status.error == "Generation failed"


class TestOpenAiCompatibleBackend:
    """Tests for the OpenAI-compatible backend."""

    @pytest.fixture
    def backend(self):
        """Create a test backend instance."""
        config = {
            "api_base": "https://api.example.com/v1",
            "api_key": "test-api-key",
            "model": "test-model",
            "default_size": "1024x1024",
            "extra_params": {"style": "vivid"},
        }
        return OpenAiCompatibleBackend(provider_id="test_compatible", config=config)

    @pytest.fixture
    def backend_no_config(self):
        """Create a backend instance without configuration."""
        config = {}
        return OpenAiCompatibleBackend(provider_id="test_no_config", config=config)

    def test_supports_sync(self, backend):
        """Test that backend supports sync generation."""
        assert backend.supports_sync is True

    def test_supports_async(self, backend):
        """Test that backend does not support async generation."""
        assert backend.supports_async is False

    def test_build_headers_with_api_key(self, backend):
        """Test header building with API key."""
        headers = backend._build_headers()
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test-api-key"
        assert headers["Content-Type"] == "application/json"

    def test_build_headers_custom_auth(self):
        """Test header building with custom auth configuration."""
        config = {
            "api_base": "https://api.example.com/v1",
            "api_key": "my-token",
            "auth_header": "X-API-Key",
            "auth_prefix": "",
        }
        backend = OpenAiCompatibleBackend(provider_id="custom_auth", config=config)
        headers = backend._build_headers()
        assert "X-API-Key" in headers
        assert headers["X-API-Key"] == "my-token"

    def test_build_request_body(self, backend):
        """Test request body building."""
        body = backend._build_request_body("test prompt", {"quality": "hd"})
        assert body["prompt"] == "test prompt"
        assert body["model"] == "test-model"
        assert body["size"] == "1024x1024"
        assert body["quality"] == "hd"
        assert body["style"] == "vivid"  # From extra_params
        assert body["n"] == 1
        assert body["response_format"] == "b64_json"

    @pytest.mark.asyncio
    async def test_generate_no_api_base(self, backend_no_config):
        """Test generate fails gracefully without api_base."""
        result = await backend_no_config.generate("test prompt", {})
        assert result.success is False
        assert "API base URL not configured" in result.error

    @pytest.mark.asyncio
    async def test_generate_no_api_key(self):
        """Test generate fails gracefully without API key."""
        config = {"api_base": "https://api.example.com/v1"}
        backend = OpenAiCompatibleBackend(provider_id="no_key", config=config)
        result = await backend.generate("test prompt", {})
        assert result.success is False
        assert "API key not configured" in result.error

    @pytest.mark.asyncio
    async def test_generate_success(self, backend):
        """Test successful generation."""
        test_image_b64 = base64.b64encode(b"test image data").decode()
        mock_response_data = {
            "data": [
                {
                    "b64_json": test_image_b64,
                    "revised_prompt": "enhanced prompt",
                }
            ]
        }

        with patch("src.image.backends.openai_compatible.httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await backend.generate("test prompt", {})

            assert result.success is True
            assert result.image_data == b"test image data"
            assert result.provider_id == "test_compatible"
            assert result.metadata["model"] == "test-model"

    @pytest.mark.asyncio
    async def test_generate_api_error(self, backend):
        """Test handling of API errors."""
        with patch("src.image.backends.openai_compatible.httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.json.return_value = {"error": "Internal server error"}

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await backend.generate("test prompt", {})

            assert result.success is False
            assert "Internal server error" in result.error

    @pytest.mark.asyncio
    async def test_check_status_not_supported(self, backend):
        """Test that check_status raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            await backend.check_status("task_123")

    @pytest.mark.asyncio
    async def test_fetch_result_not_supported(self, backend):
        """Test that fetch_result raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            await backend.fetch_result("task_123")
