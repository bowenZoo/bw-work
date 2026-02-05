"""Image storage management for generated images.

This module handles saving, loading, and managing generated images
with support for local filesystem storage and metadata tracking.
"""

import fcntl
import json
import logging
import os
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ImageMetadata:
    """Metadata for a stored image.

    Attributes:
        id: Unique image identifier.
        filename: Filename in storage.
        prompt: Original generation prompt.
        style: Style ID used for generation.
        provider_id: Provider that generated the image.
        width: Image width in pixels.
        height: Image height in pixels.
        created_at: Timestamp of creation.
        discussion_id: Optional related discussion ID.
        agent: Agent that requested the generation.
        generation_time_ms: Time taken to generate.
    """

    id: str
    filename: str
    prompt: str
    style: str = ""
    provider_id: str = ""
    width: int = 0
    height: int = 0
    created_at: str = ""
    discussion_id: str | None = None
    agent: str = ""
    generation_time_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImageMetadata":
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ImageRequest:
    """Tracking information for an image generation request.

    Attributes:
        id: Request/image ID.
        provider_id: Provider used for generation.
        task_id: Async task ID (if applicable).
        status: Current status (pending/processing/completed/failed).
        error: Error message if failed.
        created_at: Request creation timestamp.
        updated_at: Last update timestamp.
    """

    id: str
    provider_id: str = ""
    task_id: str | None = None
    status: str = "pending"
    error: str | None = None
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImageRequest":
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class ImageStorage:
    """Storage manager for generated images.

    Handles local filesystem storage with JSON-based metadata tracking.
    Uses file locking and atomic writes for concurrency safety.

    Storage structure:
        {base_path}/{project_id}/images/
            img_001.png
            img_001_thumb.png (optional)
            metadata.json
            requests.json

    Usage:
        storage = ImageStorage(base_path="data/projects")
        image_id = await storage.save_image(
            project_id="proj_001",
            image_data=b"...",
            metadata=ImageMetadata(...)
        )
    """

    METADATA_FILE = "metadata.json"
    REQUESTS_FILE = "requests.json"
    IMAGES_DIR = "images"

    def __init__(self, base_path: str | Path = "data/projects") -> None:
        """Initialize the image storage.

        Args:
            base_path: Base directory for project storage.
        """
        self.base_path = Path(base_path)

    def _get_project_images_dir(self, project_id: str) -> Path:
        """Get the images directory for a project.

        Args:
            project_id: Project identifier.

        Returns:
            Path to the project's images directory.
        """
        return self.base_path / project_id / self.IMAGES_DIR

    def _ensure_project_dir(self, project_id: str) -> Path:
        """Ensure the project images directory exists.

        Args:
            project_id: Project identifier.

        Returns:
            Path to the project's images directory.
        """
        images_dir = self._get_project_images_dir(project_id)
        images_dir.mkdir(parents=True, exist_ok=True)
        return images_dir

    def _generate_image_id(self) -> str:
        """Generate a unique image ID.

        Returns:
            Unique image identifier.
        """
        return f"img_{uuid.uuid4().hex[:12]}"

    def _atomic_json_write(self, path: Path, data: dict[str, Any]) -> None:
        """Write JSON data atomically using temp file and rename.

        Args:
            path: Target file path.
            data: Data to write.
        """
        # Write to temp file in same directory
        temp_fd, temp_path = tempfile.mkstemp(
            dir=path.parent,
            prefix=".tmp_",
            suffix=".json",
        )
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            # Atomic rename
            os.rename(temp_path, path)
        except Exception:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    def _read_json_with_lock(self, path: Path) -> dict[str, Any]:
        """Read JSON file with shared lock.

        Args:
            path: Path to JSON file.

        Returns:
            Parsed JSON data or empty dict.
        """
        if not path.exists():
            return {}

        try:
            with open(path, "r", encoding="utf-8") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    return json.load(f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to read {path}: {e}")
            return {}

    def _write_json_with_lock(self, path: Path, data: dict[str, Any]) -> None:
        """Write JSON file with exclusive lock.

        Args:
            path: Path to JSON file.
            data: Data to write.
        """
        # Ensure directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Use atomic write for safety
        self._atomic_json_write(path, data)

    def _update_metadata_file(
        self,
        project_id: str,
        image_id: str,
        metadata: ImageMetadata,
    ) -> None:
        """Update the metadata JSON file.

        Args:
            project_id: Project identifier.
            image_id: Image identifier.
            metadata: Image metadata to store.
        """
        images_dir = self._ensure_project_dir(project_id)
        metadata_path = images_dir / self.METADATA_FILE

        all_metadata = self._read_json_with_lock(metadata_path)
        all_metadata[image_id] = metadata.to_dict()
        self._write_json_with_lock(metadata_path, all_metadata)

    def _update_requests_file(
        self,
        project_id: str,
        image_id: str,
        request: ImageRequest,
    ) -> None:
        """Update the requests JSON file.

        Args:
            project_id: Project identifier.
            image_id: Image identifier.
            request: Request tracking information.
        """
        images_dir = self._ensure_project_dir(project_id)
        requests_path = images_dir / self.REQUESTS_FILE

        all_requests = self._read_json_with_lock(requests_path)
        all_requests[image_id] = request.to_dict()
        self._write_json_with_lock(requests_path, all_requests)

    async def save_image(
        self,
        project_id: str,
        image_data: bytes,
        metadata: ImageMetadata,
        image_id: str | None = None,
        format: str = "png",
    ) -> str:
        """Save an image to storage.

        Args:
            project_id: Project identifier.
            image_data: Raw image bytes.
            metadata: Image metadata.
            image_id: Optional image ID (generates new if not provided).
            format: Image format (default: png).

        Returns:
            The image ID.
        """
        if image_id is None:
            image_id = self._generate_image_id()

        images_dir = self._ensure_project_dir(project_id)
        filename = f"{image_id}.{format}"
        image_path = images_dir / filename

        # Update metadata
        metadata.id = image_id
        metadata.filename = filename
        if not metadata.created_at:
            metadata.created_at = datetime.utcnow().isoformat() + "Z"

        # Write image file atomically
        temp_fd, temp_path = tempfile.mkstemp(
            dir=images_dir,
            prefix=".tmp_",
            suffix=f".{format}",
        )
        try:
            with os.fdopen(temp_fd, "wb") as f:
                f.write(image_data)
            os.rename(temp_path, image_path)
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

        # Update metadata file
        self._update_metadata_file(project_id, image_id, metadata)

        logger.info(f"Saved image {image_id} for project {project_id}")
        return image_id

    async def update_request_status(
        self,
        project_id: str,
        image_id: str,
        status: str,
        error: str | None = None,
        task_id: str | None = None,
        provider_id: str | None = None,
    ) -> None:
        """Update the status of an image request.

        Args:
            project_id: Project identifier.
            image_id: Image identifier.
            status: New status (pending/processing/completed/failed).
            error: Error message if failed.
            task_id: Async task ID.
            provider_id: Provider ID.
        """
        images_dir = self._ensure_project_dir(project_id)
        requests_path = images_dir / self.REQUESTS_FILE

        all_requests = self._read_json_with_lock(requests_path)

        now = datetime.utcnow().isoformat() + "Z"

        if image_id in all_requests:
            request_data = all_requests[image_id]
            request_data["status"] = status
            request_data["updated_at"] = now
            if error is not None:
                request_data["error"] = error
            if task_id is not None:
                request_data["task_id"] = task_id
            if provider_id is not None:
                request_data["provider_id"] = provider_id
        else:
            request_data = {
                "id": image_id,
                "provider_id": provider_id or "",
                "task_id": task_id,
                "status": status,
                "error": error,
                "created_at": now,
                "updated_at": now,
            }

        all_requests[image_id] = request_data
        self._write_json_with_lock(requests_path, all_requests)

    async def get_image_path(self, project_id: str, image_id: str) -> Path | None:
        """Get the filesystem path to an image.

        Args:
            project_id: Project identifier.
            image_id: Image identifier.

        Returns:
            Path to the image file, or None if not found.
        """
        images_dir = self._get_project_images_dir(project_id)
        metadata_path = images_dir / self.METADATA_FILE

        metadata = self._read_json_with_lock(metadata_path)
        if image_id not in metadata:
            return None

        filename = metadata[image_id].get("filename")
        if not filename:
            return None

        image_path = images_dir / filename
        if not image_path.exists():
            return None

        return image_path

    async def get_image_data(self, project_id: str, image_id: str) -> bytes | None:
        """Get the raw image data.

        Args:
            project_id: Project identifier.
            image_id: Image identifier.

        Returns:
            Raw image bytes, or None if not found.
        """
        image_path = await self.get_image_path(project_id, image_id)
        if image_path is None:
            return None

        try:
            return image_path.read_bytes()
        except OSError as e:
            logger.error(f"Failed to read image {image_id}: {e}")
            return None

    async def get_image_metadata(
        self, project_id: str, image_id: str
    ) -> ImageMetadata | None:
        """Get metadata for an image.

        Args:
            project_id: Project identifier.
            image_id: Image identifier.

        Returns:
            ImageMetadata or None if not found.
        """
        images_dir = self._get_project_images_dir(project_id)
        metadata_path = images_dir / self.METADATA_FILE

        all_metadata = self._read_json_with_lock(metadata_path)
        if image_id not in all_metadata:
            return None

        return ImageMetadata.from_dict(all_metadata[image_id])

    async def get_request_status(
        self, project_id: str, image_id: str
    ) -> ImageRequest | None:
        """Get the request status for an image.

        Args:
            project_id: Project identifier.
            image_id: Image identifier.

        Returns:
            ImageRequest or None if not found.
        """
        images_dir = self._get_project_images_dir(project_id)
        requests_path = images_dir / self.REQUESTS_FILE

        all_requests = self._read_json_with_lock(requests_path)
        if image_id not in all_requests:
            return None

        return ImageRequest.from_dict(all_requests[image_id])

    async def list_images(self, project_id: str) -> list[ImageMetadata]:
        """List all images for a project.

        Args:
            project_id: Project identifier.

        Returns:
            List of ImageMetadata objects.
        """
        images_dir = self._get_project_images_dir(project_id)
        metadata_path = images_dir / self.METADATA_FILE

        all_metadata = self._read_json_with_lock(metadata_path)
        return [ImageMetadata.from_dict(m) for m in all_metadata.values()]

    async def delete_image(self, project_id: str, image_id: str) -> bool:
        """Delete an image and its metadata.

        Args:
            project_id: Project identifier.
            image_id: Image identifier.

        Returns:
            True if deleted, False if not found.
        """
        images_dir = self._get_project_images_dir(project_id)

        # Get and delete image file
        image_path = await self.get_image_path(project_id, image_id)
        if image_path and image_path.exists():
            try:
                image_path.unlink()
            except OSError as e:
                logger.error(f"Failed to delete image file {image_id}: {e}")
                return False

        # Remove from metadata
        metadata_path = images_dir / self.METADATA_FILE
        all_metadata = self._read_json_with_lock(metadata_path)
        if image_id in all_metadata:
            del all_metadata[image_id]
            self._write_json_with_lock(metadata_path, all_metadata)

        # Remove from requests
        requests_path = images_dir / self.REQUESTS_FILE
        all_requests = self._read_json_with_lock(requests_path)
        if image_id in all_requests:
            del all_requests[image_id]
            self._write_json_with_lock(requests_path, all_requests)

        logger.info(f"Deleted image {image_id} from project {project_id}")
        return True

    def get_image_url(self, project_id: str, image_id: str) -> str:
        """Generate the API URL for accessing an image.

        Args:
            project_id: Project identifier.
            image_id: Image identifier.

        Returns:
            API URL path for the image.
        """
        return f"/api/images/projects/{project_id}/{image_id}"
