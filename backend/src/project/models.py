"""Data models for project-level discussions.

This module defines all data structures used in the project discussion workflow,
including GDD documents, modules, discussions, checkpoints, and outputs.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# --- Enums ---


class GDDStatus(str, Enum):
    """Status of GDD document processing."""

    UPLOADING = "uploading"
    PARSING = "parsing"
    READY = "ready"
    ERROR = "error"


class ProjectDiscussionStatus(str, Enum):
    """Status of a project-level batch discussion."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class ModuleDiscussionStatus(str, Enum):
    """Status of a single module discussion."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


# --- GDD Related Models ---


@dataclass
class Section:
    """A section within a parsed document."""

    title: str
    level: int  # Heading level (1-6)
    content: str
    start_line: int
    end_line: int


@dataclass
class ParsedText:
    """Result of parsing a document format (Markdown/PDF/Word)."""

    title: str
    content: str  # Full plain text content
    sections: list[Section] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)  # Author, date, etc.


@dataclass
class GDDModule:
    """A functional module identified within a GDD."""

    id: str  # Module ID (e.g., "combat", "economy")
    name: str  # Display name
    description: str  # Brief description
    source_section: str  # Original section content from GDD
    keywords: list[str] = field(default_factory=list)  # For memory retrieval
    dependencies: list[str] = field(default_factory=list)  # IDs of dependent modules
    estimated_rounds: int = 3  # Estimated discussion rounds


@dataclass
class ParsedGDD:
    """A fully parsed GDD with identified modules."""

    title: str  # Project name
    overview: str  # Project overview
    modules: list[GDDModule] = field(default_factory=list)
    raw_content: str = ""  # Full original content


@dataclass
class GDDDocument:
    """A GDD document record."""

    id: str  # gdd_{uuid}
    project_id: str
    filename: str
    upload_time: datetime
    raw_content_path: str  # Path to original file
    parsed_content_path: str  # Path to parsed JSON
    content_hash: str  # File hash for caching
    parser_version: str  # Parser version for cache invalidation
    status: GDDStatus = GDDStatus.UPLOADING
    error: Optional[str] = None
    parsed_content: Optional[ParsedGDD] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "filename": self.filename,
            "upload_time": self.upload_time.isoformat(),
            "raw_content_path": self.raw_content_path,
            "parsed_content_path": self.parsed_content_path,
            "content_hash": self.content_hash,
            "parser_version": self.parser_version,
            "status": self.status.value,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GDDDocument":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            project_id=data["project_id"],
            filename=data["filename"],
            upload_time=datetime.fromisoformat(data["upload_time"]),
            raw_content_path=data["raw_content_path"],
            parsed_content_path=data["parsed_content_path"],
            content_hash=data["content_hash"],
            parser_version=data["parser_version"],
            status=GDDStatus(data["status"]),
            error=data.get("error"),
        )


# --- Discussion Models ---


@dataclass
class DiscussionProgress:
    """Progress tracking for a batch discussion."""

    total_modules: int
    completed_modules: int
    current_module: Optional[str] = None
    current_round: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_modules": self.total_modules,
            "completed_modules": self.completed_modules,
            "current_module": self.current_module,
            "current_round": self.current_round,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DiscussionProgress":
        """Create from dictionary."""
        return cls(
            total_modules=data["total_modules"],
            completed_modules=data["completed_modules"],
            current_module=data.get("current_module"),
            current_round=data.get("current_round", 0),
        )


@dataclass
class ModuleState:
    """State of a module discussion for checkpoint purposes."""

    module_id: str
    discussion_id: str
    round: int
    message_count: int
    last_message_id: Optional[str] = None  # Cursor only, not full content

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "module_id": self.module_id,
            "discussion_id": self.discussion_id,
            "round": self.round,
            "message_count": self.message_count,
            "last_message_id": self.last_message_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ModuleState":
        """Create from dictionary."""
        return cls(
            module_id=data["module_id"],
            discussion_id=data["discussion_id"],
            round=data["round"],
            message_count=data["message_count"],
            last_message_id=data.get("last_message_id"),
        )


@dataclass
class CompletedModule:
    """Record of a completed module discussion."""

    module_id: str
    design_doc_path: str
    key_decisions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "module_id": self.module_id,
            "design_doc_path": self.design_doc_path,
            "key_decisions": self.key_decisions,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CompletedModule":
        """Create from dictionary."""
        return cls(
            module_id=data["module_id"],
            design_doc_path=data["design_doc_path"],
            key_decisions=data.get("key_decisions", []),
        )


@dataclass
class DiscussionCheckpoint:
    """Checkpoint data for resuming a batch discussion."""

    project_id: str
    gdd_id: str
    discussion_id: str
    selected_modules: list[str]
    current_module_index: int
    current_module_state: Optional[ModuleState] = None
    completed_modules: list[CompletedModule] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "project_id": self.project_id,
            "gdd_id": self.gdd_id,
            "discussion_id": self.discussion_id,
            "selected_modules": self.selected_modules,
            "current_module_index": self.current_module_index,
            "current_module_state": self.current_module_state.to_dict() if self.current_module_state else None,
            "completed_modules": [m.to_dict() for m in self.completed_modules],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DiscussionCheckpoint":
        """Create from dictionary."""
        return cls(
            project_id=data["project_id"],
            gdd_id=data["gdd_id"],
            discussion_id=data["discussion_id"],
            selected_modules=data["selected_modules"],
            current_module_index=data["current_module_index"],
            current_module_state=ModuleState.from_dict(data["current_module_state"])
            if data.get("current_module_state")
            else None,
            completed_modules=[CompletedModule.from_dict(m) for m in data.get("completed_modules", [])],
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.utcnow(),
        )


@dataclass
class ProjectDiscussion:
    """A project-level batch discussion."""

    id: str  # disc_batch_{uuid}
    project_id: str
    gdd_id: str
    selected_modules: list[str]
    module_order: list[str]
    status: ProjectDiscussionStatus = ProjectDiscussionStatus.PENDING
    progress: DiscussionProgress = field(default_factory=lambda: DiscussionProgress(0, 0))
    checkpoint: Optional[DiscussionCheckpoint] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "gdd_id": self.gdd_id,
            "selected_modules": self.selected_modules,
            "module_order": self.module_order,
            "status": self.status.value,
            "progress": self.progress.to_dict(),
            "checkpoint": self.checkpoint.to_dict() if self.checkpoint else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProjectDiscussion":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            project_id=data["project_id"],
            gdd_id=data["gdd_id"],
            selected_modules=data["selected_modules"],
            module_order=data["module_order"],
            status=ProjectDiscussionStatus(data["status"]),
            progress=DiscussionProgress.from_dict(data["progress"]),
            checkpoint=DiscussionCheckpoint.from_dict(data["checkpoint"]) if data.get("checkpoint") else None,
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.utcnow(),
        )


# --- Output Models ---


@dataclass
class Decision:
    """A design decision made during discussion."""

    module_id: str
    content: str
    rationale: str
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "module_id": self.module_id,
            "content": self.content,
            "rationale": self.rationale,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Decision":
        """Create from dictionary."""
        return cls(
            module_id=data["module_id"],
            content=data["content"],
            rationale=data["rationale"],
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else datetime.utcnow(),
        )


@dataclass
class DesignDoc:
    """A generated design document."""

    path: str
    version: str
    sections: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "path": self.path,
            "version": self.version,
            "sections": self.sections,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DesignDoc":
        """Create from dictionary."""
        return cls(
            path=data["path"],
            version=data["version"],
            sections=data.get("sections", []),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
        )


@dataclass
class ModuleDiscussionResult:
    """Result of a single module discussion."""

    module_id: str
    module_name: str
    discussion_id: str
    status: ModuleDiscussionStatus
    design_doc: Optional[DesignDoc] = None
    key_decisions: list[Decision] = field(default_factory=list)
    duration_minutes: float = 0.0
    token_usage: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "module_id": self.module_id,
            "module_name": self.module_name,
            "discussion_id": self.discussion_id,
            "status": self.status.value,
            "design_doc": self.design_doc.to_dict() if self.design_doc else None,
            "key_decisions": [d.to_dict() for d in self.key_decisions],
            "duration_minutes": self.duration_minutes,
            "token_usage": self.token_usage,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ModuleDiscussionResult":
        """Create from dictionary."""
        return cls(
            module_id=data["module_id"],
            module_name=data["module_name"],
            discussion_id=data["discussion_id"],
            status=ModuleDiscussionStatus(data["status"]),
            design_doc=DesignDoc.from_dict(data["design_doc"]) if data.get("design_doc") else None,
            key_decisions=[Decision.from_dict(d) for d in data.get("key_decisions", [])],
            duration_minutes=data.get("duration_minutes", 0.0),
            token_usage=data.get("token_usage", 0),
        )
