"""Integration tests for the image generation system."""

import asyncio
import base64
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.image.backends.base import ImageResult, TaskStatus, TaskStatusEnum
from src.image.prompt_engineer import PromptEngineer
from src.image.providers import ProviderRegistry
from src.image.service import ImageService
from src.image.storage import ImageMetadata, ImageStorage
from src.image.style_manager import StyleManager


class TestImageServiceIntegration:
    """Integration tests for ImageService with mocked backends."""

    @pytest.fixture
    def temp_storage_dir(self):
        """Create a temporary directory for storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def style_manager(self):
        """Create a style manager with test config."""
        config = {
            "styles": {
                "test_style": {
                    "name": "Test Style",
                    "description": "A test style",
                    "prompt_prefix": "test prefix,",
                    "prompt_suffix": "test suffix",
                    "recommended_backends": ["test_backend"],
                    "default_params": {"size": "512x512"},
                }
            },
            "default_style": "test_style",
        }
        return StyleManager(config_dict=config)

    @pytest.fixture
    def provider_registry(self):
        """Create a provider registry with mocked backend."""
        config = {
            "providers": {
                "test_backend": {
                    "backend": "openai",
                    "api_key": "test-key",
                    "api_base": "https://test.api.com/v1",
                    "model": "test-model",
                }
            },
            "default_provider": "test_backend",
        }
        return ProviderRegistry(config_dict=config)

    @pytest.fixture
    def storage(self, temp_storage_dir):
        """Create a storage instance with temp directory."""
        return ImageStorage(base_path=temp_storage_dir)

    @pytest.fixture
    def prompt_engineer(self):
        """Create a prompt engineer."""
        return PromptEngineer(enable_llm_enhancement=False)

    @pytest.fixture
    def image_service(
        self, provider_registry, style_manager, prompt_engineer, storage
    ):
        """Create an image service with all components."""
        return ImageService(
            provider_registry=provider_registry,
            style_manager=style_manager,
            prompt_engineer=prompt_engineer,
            storage=storage,
        )

    @pytest.mark.asyncio
    async def test_full_generation_flow_sync(self, image_service, temp_storage_dir):
        """Test complete image generation flow with sync backend."""
        test_image_data = b"fake image data"
        test_image_b64 = base64.b64encode(test_image_data).decode()

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

            result = await image_service.generate(
                description="A test character",
                project_id="test_project",
                style_id="test_style",
            )

            assert result.success is True
            assert result.image_id is not None
            assert result.image_url is not None
            assert "test_project" in result.image_url
            assert result.enhanced_prompt is not None
            assert "test prefix," in result.enhanced_prompt

            # Verify image was stored
            storage = image_service.storage
            stored_metadata = await storage.get_image_metadata(
                "test_project", result.image_id
            )
            assert stored_metadata is not None
            assert stored_metadata.prompt == "A test character"

            # Verify image file exists
            image_path = await storage.get_image_path("test_project", result.image_id)
            assert image_path is not None
            assert image_path.exists()

    @pytest.mark.asyncio
    async def test_generation_with_websocket_broadcast(
        self, provider_registry, style_manager, prompt_engineer, storage
    ):
        """Test that WebSocket events are broadcast during generation."""
        broadcast_calls = []

        def mock_broadcast(event_type: str, data: dict):
            broadcast_calls.append({"type": event_type, "data": data})

        service = ImageService(
            provider_registry=provider_registry,
            style_manager=style_manager,
            prompt_engineer=prompt_engineer,
            storage=storage,
            websocket_broadcast=mock_broadcast,
        )

        test_image_b64 = base64.b64encode(b"test").decode()
        mock_response_data = {"data": [{"b64_json": test_image_b64}]}

        with patch("src.image.backends.openai.httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await service.generate(
                description="test",
                project_id="test_project",
                style_id="test_style",
            )

            assert result.success is True

            # Verify WebSocket events were broadcast
            event_types = [c["type"] for c in broadcast_calls]
            assert "image_generation_start" in event_types
            assert "image_generation_complete" in event_types

    @pytest.mark.asyncio
    async def test_generation_failure_handling(self, image_service):
        """Test error handling when generation fails."""
        with patch("src.image.backends.openai.httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.json.return_value = {"error": {"message": "Invalid prompt"}}

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await image_service.generate(
                description="test",
                project_id="test_project",
                style_id="test_style",
            )

            assert result.success is False
            assert result.error is not None
            assert "Invalid prompt" in result.error

    @pytest.mark.asyncio
    async def test_generation_retry_on_failure(self, image_service):
        """Test that generation retries on transient failures."""
        call_count = 0
        test_image_b64 = base64.b64encode(b"test").decode()

        def make_response():
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()
            if call_count < 2:
                # First call fails
                mock_response.status_code = 500
                mock_response.json.return_value = {"error": "Server error"}
            else:
                # Second call succeeds
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "data": [{"b64_json": test_image_b64}]
                }
            return mock_response

        with patch("src.image.backends.openai.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.side_effect = lambda *args, **kwargs: make_response()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await image_service.generate(
                description="test",
                project_id="test_project",
                style_id="test_style",
            )

            assert result.success is True
            assert call_count == 2  # Verify retry happened

    @pytest.mark.asyncio
    async def test_status_check(self, image_service, temp_storage_dir):
        """Test checking status of a generation request."""
        test_image_b64 = base64.b64encode(b"test").decode()
        mock_response_data = {"data": [{"b64_json": test_image_b64}]}

        with patch("src.image.backends.openai.httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Generate an image
            gen_result = await image_service.generate(
                description="test",
                project_id="test_project",
                style_id="test_style",
            )

            # Check status
            status_result = await image_service.get_status(
                "test_project", gen_result.image_id
            )

            assert status_result.success is True
            assert status_result.image_id == gen_result.image_id
            assert status_result.image_url is not None


class TestImageStorageIntegration:
    """Integration tests for ImageStorage."""

    @pytest.fixture
    def temp_storage_dir(self):
        """Create a temporary directory for storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def storage(self, temp_storage_dir):
        """Create a storage instance."""
        return ImageStorage(base_path=temp_storage_dir)

    @pytest.mark.asyncio
    async def test_save_and_retrieve_image(self, storage):
        """Test saving and retrieving an image."""
        test_image = b"PNG test image data"
        metadata = ImageMetadata(
            id="test_img",
            filename="test_img.png",
            prompt="A test image",
            style="concept_character",
            provider_id="test_provider",
            width=512,
            height=512,
        )

        image_id = await storage.save_image(
            project_id="test_project",
            image_data=test_image,
            metadata=metadata,
        )

        assert image_id is not None

        # Retrieve
        retrieved_data = await storage.get_image_data("test_project", image_id)
        assert retrieved_data == test_image

        retrieved_metadata = await storage.get_image_metadata("test_project", image_id)
        assert retrieved_metadata is not None
        assert retrieved_metadata.prompt == "A test image"
        assert retrieved_metadata.width == 512

    @pytest.mark.asyncio
    async def test_list_images(self, storage):
        """Test listing project images."""
        # Save multiple images
        for i in range(3):
            metadata = ImageMetadata(
                id=f"img_{i}",
                filename=f"img_{i}.png",
                prompt=f"Image {i}",
                style="test_style",
                provider_id="test",
                width=256,
                height=256,
            )
            await storage.save_image(
                project_id="test_project",
                image_data=b"test",
                metadata=metadata,
                image_id=f"img_{i}",
            )

        images = await storage.list_images("test_project")
        assert len(images) == 3

    @pytest.mark.asyncio
    async def test_delete_image(self, storage):
        """Test deleting an image."""
        metadata = ImageMetadata(
            id="to_delete",
            filename="to_delete.png",
            prompt="Delete me",
            style="test",
            provider_id="test",
            width=256,
            height=256,
        )
        await storage.save_image(
            project_id="test_project",
            image_data=b"test",
            metadata=metadata,
            image_id="to_delete",
        )

        # Verify exists
        data = await storage.get_image_data("test_project", "to_delete")
        assert data is not None

        # Delete
        deleted = await storage.delete_image("test_project", "to_delete")
        assert deleted is True

        # Verify deleted
        data = await storage.get_image_data("test_project", "to_delete")
        assert data is None

    @pytest.mark.asyncio
    async def test_request_status_tracking(self, storage):
        """Test tracking request status."""
        await storage.update_request_status(
            project_id="test_project",
            image_id="req_001",
            status="pending",
            provider_id="test_provider",
        )

        status = await storage.get_request_status("test_project", "req_001")
        assert status is not None
        assert status.status == "pending"
        assert status.provider_id == "test_provider"

        # Update status
        await storage.update_request_status(
            project_id="test_project",
            image_id="req_001",
            status="completed",
        )

        status = await storage.get_request_status("test_project", "req_001")
        assert status.status == "completed"


class TestStyleManagerIntegration:
    """Integration tests for StyleManager with config loading."""

    def test_load_from_yaml(self, tmp_path):
        """Test loading styles from YAML file."""
        yaml_content = """
styles:
  custom_style:
    name: Custom Style
    description: A custom test style
    prompt_prefix: "custom prefix,"
    prompt_suffix: "custom suffix"
    recommended_backends:
      - backend_a
    default_params:
      size: "1024x1024"
default_style: custom_style
"""
        config_path = tmp_path / "styles.yaml"
        config_path.write_text(yaml_content)

        manager = StyleManager(config_path=config_path)

        style = manager.get_style("custom_style")
        assert style.name == "Custom Style"
        assert "custom prefix," in style.prompt_prefix
        assert style.recommended_backends == ["backend_a"]

    def test_get_recommended_backend(self):
        """Test getting recommended backend for a style."""
        config = {
            "styles": {
                "style_a": {
                    "name": "Style A",
                    "recommended_backends": ["backend_1", "backend_2"],
                },
                "style_b": {
                    "name": "Style B",
                    "recommended_backends": ["backend_3"],
                },
            },
            "default_style": "style_a",
        }
        manager = StyleManager(config_dict=config)

        # Get first recommended
        backend = manager.get_recommended_backend("style_a")
        assert backend == "backend_1"

        # Get from available list
        backend = manager.get_recommended_backend(
            "style_a", available_backends=["backend_2", "backend_3"]
        )
        assert backend == "backend_2"

        # No match
        backend = manager.get_recommended_backend(
            "style_a", available_backends=["backend_3"]
        )
        assert backend is None


class TestPromptEngineerIntegration:
    """Integration tests for PromptEngineer with styles."""

    @pytest.mark.asyncio
    async def test_enhance_with_style(self):
        """Test prompt enhancement with style template."""
        engineer = PromptEngineer(enable_llm_enhancement=False)

        style_config = {
            "name": "Game Concept",
            "prompt_prefix": "game concept art,",
            "prompt_suffix": "detailed, professional quality",
            "negative_prompt": ["blurry", "amateur"],
        }

        result = await engineer.enhance(
            description="A fierce warrior with a sword",
            style=style_config,
            style_id="concept_character",
        )

        assert "game concept art," in result.enhanced
        assert "A fierce warrior with a sword" in result.enhanced
        assert "detailed, professional quality" in result.enhanced
        assert result.negative_prompt is not None
        assert "blurry" in result.negative_prompt
        assert result.style_id == "concept_character"
