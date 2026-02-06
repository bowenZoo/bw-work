"""Agenda data models for discussion management."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class AgendaItemStatus(str, Enum):
    """Status of an agenda item."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class AgendaSummaryDetails(BaseModel):
    """Detailed summary for a completed agenda item."""

    conclusions: list[str] = Field(default_factory=list)  # 讨论结论
    viewpoints: dict[str, str] = Field(default_factory=dict)  # 各方观点 {角色: 观点}
    open_questions: list[str] = Field(default_factory=list)  # 遗留问题
    next_steps: list[str] = Field(default_factory=list)  # 下一步行动


class AgendaItem(BaseModel):
    """Single agenda item for discussion."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    description: str | None = None
    status: AgendaItemStatus = AgendaItemStatus.PENDING
    summary: str | None = None  # 议题小结 (Markdown)
    summary_details: AgendaSummaryDetails | None = None  # 详细小结（结构化）
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def start(self) -> None:
        """Mark this item as in progress."""
        self.status = AgendaItemStatus.IN_PROGRESS
        self.started_at = datetime.now()

    def complete(self, summary: str, details: AgendaSummaryDetails | None = None) -> None:
        """Mark this item as completed with a summary."""
        self.status = AgendaItemStatus.COMPLETED
        self.summary = summary
        self.summary_details = details
        self.completed_at = datetime.now()

    def skip(self) -> None:
        """Mark this item as skipped."""
        self.status = AgendaItemStatus.SKIPPED

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "summary": self.summary,
            "summary_details": self.summary_details.model_dump() if self.summary_details else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class Agenda(BaseModel):
    """Discussion agenda containing multiple items."""

    items: list[AgendaItem] = Field(default_factory=list)
    current_index: int = 0

    @property
    def current_item(self) -> AgendaItem | None:
        """Get the current agenda item."""
        if 0 <= self.current_index < len(self.items):
            return self.items[self.current_index]
        return None

    @property
    def is_completed(self) -> bool:
        """Check if all items are completed or skipped."""
        return self.current_index >= len(self.items)

    @property
    def progress(self) -> tuple[int, int]:
        """Get progress as (completed_count, total_count)."""
        completed = sum(
            1 for item in self.items
            if item.status in (AgendaItemStatus.COMPLETED, AgendaItemStatus.SKIPPED)
        )
        return completed, len(self.items)

    def add_item(self, title: str, description: str | None = None) -> AgendaItem:
        """Add a new item to the agenda."""
        item = AgendaItem(title=title, description=description)
        self.items.append(item)
        return item

    def get_item_by_id(self, item_id: str) -> AgendaItem | None:
        """Get an item by its ID."""
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def start_current(self) -> AgendaItem | None:
        """Start the current item and return it."""
        if self.current_item:
            self.current_item.start()
            return self.current_item
        return None

    def complete_current(
        self,
        summary: str,
        details: AgendaSummaryDetails | None = None,
    ) -> AgendaItem | None:
        """Complete the current item and move to the next."""
        if self.current_item:
            item = self.current_item
            item.complete(summary, details)
            self.current_index += 1
            return item
        return None

    def skip_current(self) -> AgendaItem | None:
        """Skip the current item and move to the next."""
        if self.current_item:
            item = self.current_item
            item.skip()
            self.current_index += 1
            return item
        return None

    def skip_item(self, item_id: str) -> AgendaItem | None:
        """Skip a specific item by ID."""
        item = self.get_item_by_id(item_id)
        if item and item.status == AgendaItemStatus.PENDING:
            item.skip()
            # If this was the current item, advance
            if self.current_item and self.current_item.id == item_id:
                self.current_index += 1
            return item
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "items": [item.to_dict() for item in self.items],
            "current_index": self.current_index,
        }

    @classmethod
    def from_items_list(cls, items_data: list[dict[str, str]]) -> "Agenda":
        """Create an Agenda from a list of item dictionaries.

        Args:
            items_data: List of dicts with 'title' and optional 'description'.

        Returns:
            New Agenda instance with the items.
        """
        agenda = cls()
        for item_data in items_data:
            agenda.add_item(
                title=item_data.get("title", ""),
                description=item_data.get("description"),
            )
        return agenda
