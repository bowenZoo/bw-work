"""Project registry for managing projects and their persistence."""

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class Project:
    """Project entity representing a game design project."""

    id: str
    name: str
    description: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert project to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Project":
        """Create project from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.utcnow(),
        )


class ProjectRegistry:
    """Registry for managing projects with file-based persistence.

    Projects are stored as JSON files in the data directory with an index
    for quick lookup operations.
    """

    def __init__(self, data_dir: str = "data/projects"):
        """Initialize the registry.

        Args:
            data_dir: Base directory for project data storage.
        """
        self.data_dir = Path(data_dir)
        self.index_path = self.data_dir / "_index.json"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Ensure required directories exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> dict[str, dict]:
        """Load the project index from disk.

        Returns:
            Dictionary mapping project IDs to their metadata.
        """
        if not self.index_path.exists():
            return {}
        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _save_index(self, index: dict[str, dict]) -> None:
        """Save the project index to disk.

        Args:
            index: Dictionary mapping project IDs to their metadata.
        """
        # Use atomic write with temp file
        temp_path = self.index_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        temp_path.replace(self.index_path)

    def _project_dir(self, project_id: str) -> Path:
        """Get the directory path for a project.

        Args:
            project_id: The project ID.

        Returns:
            Path to the project directory.
        """
        return self.data_dir / project_id

    def _project_meta_path(self, project_id: str) -> Path:
        """Get the metadata file path for a project.

        Args:
            project_id: The project ID.

        Returns:
            Path to the project metadata file.
        """
        return self._project_dir(project_id) / "project.json"

    @staticmethod
    def generate_id(name: str) -> str:
        """Generate a project ID from the name.

        Creates a slug-style ID from the project name with a short UUID suffix
        to ensure uniqueness.

        Args:
            name: The project name.

        Returns:
            A unique project ID.
        """
        # Create a slug from the name
        slug = name.lower().strip()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[\s_-]+", "-", slug)
        slug = slug[:30].strip("-")

        # Add a short UUID suffix for uniqueness
        suffix = uuid.uuid4().hex[:8]

        if slug:
            return f"{slug}-{suffix}"
        return suffix

    def create(self, name: str, description: Optional[str] = None) -> Project:
        """Create a new project.

        Args:
            name: The project name.
            description: Optional project description.

        Returns:
            The created project.

        Raises:
            ValueError: If the project name is empty.
        """
        if not name or not name.strip():
            raise ValueError("Project name cannot be empty")

        project_id = self.generate_id(name)
        now = datetime.utcnow()

        project = Project(
            id=project_id,
            name=name.strip(),
            description=description.strip() if description else None,
            created_at=now,
            updated_at=now,
        )

        # Create project directory structure
        project_dir = self._project_dir(project_id)
        project_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (project_dir / "gdd" / "original").mkdir(parents=True, exist_ok=True)
        (project_dir / "gdd" / "parsed").mkdir(parents=True, exist_ok=True)
        (project_dir / "design").mkdir(parents=True, exist_ok=True)
        (project_dir / "checkpoints").mkdir(parents=True, exist_ok=True)

        # Save project metadata
        with open(self._project_meta_path(project_id), "w", encoding="utf-8") as f:
            json.dump(project.to_dict(), f, ensure_ascii=False, indent=2)

        # Update index
        index = self._load_index()
        index[project_id] = {
            "name": project.name,
            "created_at": project.created_at.isoformat(),
        }
        self._save_index(index)

        return project

    def get(self, project_id: str) -> Optional[Project]:
        """Get a project by ID.

        Args:
            project_id: The project ID.

        Returns:
            The project if found, None otherwise.
        """
        meta_path = self._project_meta_path(project_id)
        if not meta_path.exists():
            return None

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Project.from_dict(data)
        except (json.JSONDecodeError, IOError, KeyError):
            return None

    def list(self, limit: int = 100, offset: int = 0) -> list[Project]:
        """List all projects.

        Args:
            limit: Maximum number of projects to return.
            offset: Number of projects to skip.

        Returns:
            List of projects, sorted by creation time (newest first).
        """
        index = self._load_index()

        # Sort by created_at descending
        sorted_ids = sorted(
            index.keys(),
            key=lambda k: index[k].get("created_at", ""),
            reverse=True,
        )

        # Apply pagination
        paginated_ids = sorted_ids[offset:offset + limit]

        # Load full project data
        projects = []
        for project_id in paginated_ids:
            project = self.get(project_id)
            if project:
                projects.append(project)

        return projects

    def update(self, project_id: str, name: Optional[str] = None, description: Optional[str] = None) -> Optional[Project]:
        """Update a project.

        Args:
            project_id: The project ID.
            name: New name (optional).
            description: New description (optional).

        Returns:
            The updated project if found, None otherwise.
        """
        project = self.get(project_id)
        if not project:
            return None

        if name is not None:
            if not name.strip():
                raise ValueError("Project name cannot be empty")
            project.name = name.strip()

        if description is not None:
            project.description = description.strip() if description else None

        project.updated_at = datetime.utcnow()

        # Save updated metadata
        with open(self._project_meta_path(project_id), "w", encoding="utf-8") as f:
            json.dump(project.to_dict(), f, ensure_ascii=False, indent=2)

        # Update index
        index = self._load_index()
        if project_id in index:
            index[project_id]["name"] = project.name
            self._save_index(index)

        return project

    def delete(self, project_id: str) -> bool:
        """Delete a project.

        Note: This only removes the project from the index, not the data directory.
        To fully remove project data, manually delete the project directory.

        Args:
            project_id: The project ID.

        Returns:
            True if the project was deleted, False if not found.
        """
        project = self.get(project_id)
        if not project:
            return False

        # Remove from index
        index = self._load_index()
        if project_id in index:
            del index[project_id]
            self._save_index(index)

        # Mark project as deleted in metadata (soft delete)
        meta_path = self._project_meta_path(project_id)
        if meta_path.exists():
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["deleted_at"] = datetime.utcnow().isoformat()
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except (json.JSONDecodeError, IOError):
                pass

        return True

    def exists(self, project_id: str) -> bool:
        """Check if a project exists.

        Args:
            project_id: The project ID.

        Returns:
            True if the project exists, False otherwise.
        """
        return self._project_meta_path(project_id).exists()

    def count(self) -> int:
        """Get the total number of projects.

        Returns:
            The number of projects in the registry.
        """
        return len(self._load_index())
