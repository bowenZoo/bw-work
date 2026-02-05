"""Checkpoint management for resumable batch discussions."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from src.project.models import (
    CompletedModule,
    DiscussionCheckpoint,
    ModuleState,
)

logger = logging.getLogger(__name__)

# Default settings
DEFAULT_RETENTION_COUNT = 5  # Number of checkpoints to keep per discussion
DEFAULT_MAX_AGE_DAYS = 30  # Maximum age of checkpoints in days


class CheckpointManager:
    """Manages checkpoints for batch discussions.

    Checkpoints enable:
    - Resuming after interruption
    - Recovery after service restart
    - Progress tracking

    Checkpoints are saved atomically to prevent corruption.
    """

    def __init__(
        self,
        data_dir: str = "data/projects",
        retention_count: int = DEFAULT_RETENTION_COUNT,
        max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    ):
        """Initialize checkpoint manager.

        Args:
            data_dir: Base directory for project data.
            retention_count: Number of checkpoints to keep per discussion.
            max_age_days: Maximum age of checkpoints before cleanup.
        """
        self.data_dir = Path(data_dir)
        self.retention_count = retention_count
        self.max_age_days = max_age_days

    def _checkpoint_dir(self, project_id: str) -> Path:
        """Get checkpoint directory for a project."""
        return self.data_dir / project_id / "checkpoints"

    def _checkpoint_path(self, project_id: str, discussion_id: str, timestamp: Optional[str] = None) -> Path:
        """Get path for a checkpoint file.

        Args:
            project_id: Project identifier.
            discussion_id: Discussion identifier.
            timestamp: Optional timestamp suffix for versioning.

        Returns:
            Path to checkpoint file.
        """
        checkpoint_dir = self._checkpoint_dir(project_id)
        if timestamp:
            return checkpoint_dir / f"{discussion_id}_{timestamp}.json"
        return checkpoint_dir / f"{discussion_id}_latest.json"

    def _list_checkpoints(self, project_id: str, discussion_id: str) -> list[Path]:
        """List all checkpoint files for a discussion.

        Args:
            project_id: Project identifier.
            discussion_id: Discussion identifier.

        Returns:
            List of checkpoint file paths, sorted by modification time (newest first).
        """
        checkpoint_dir = self._checkpoint_dir(project_id)
        if not checkpoint_dir.exists():
            return []

        pattern = f"{discussion_id}_*.json"
        files = list(checkpoint_dir.glob(pattern))
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return files

    def save(self, checkpoint: DiscussionCheckpoint) -> Path:
        """Save a checkpoint atomically.

        Creates a timestamped version and updates the 'latest' pointer.

        Args:
            checkpoint: Checkpoint data to save.

        Returns:
            Path to the saved checkpoint file.
        """
        project_id = checkpoint.project_id
        discussion_id = checkpoint.discussion_id
        checkpoint_dir = self._checkpoint_dir(project_id)
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        checkpoint.updated_at = datetime.utcnow()
        data = checkpoint.to_dict()

        # Save timestamped version
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        versioned_path = self._checkpoint_path(project_id, discussion_id, timestamp)

        # Atomic write
        temp_path = versioned_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        temp_path.replace(versioned_path)

        # Update latest pointer
        latest_path = self._checkpoint_path(project_id, discussion_id)
        temp_latest = latest_path.with_suffix(".tmp")
        with open(temp_latest, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        temp_latest.replace(latest_path)

        logger.info(f"Saved checkpoint for {discussion_id} at {versioned_path}")

        # Cleanup old checkpoints
        self._cleanup_old_checkpoints(project_id, discussion_id)

        return latest_path

    def load(self, project_id: str, discussion_id: str) -> Optional[DiscussionCheckpoint]:
        """Load the latest checkpoint for a discussion.

        Args:
            project_id: Project identifier.
            discussion_id: Discussion identifier.

        Returns:
            DiscussionCheckpoint if found, None otherwise.
        """
        latest_path = self._checkpoint_path(project_id, discussion_id)
        if not latest_path.exists():
            return None

        try:
            with open(latest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return DiscussionCheckpoint.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to load checkpoint {latest_path}: {e}")
            return None

    def load_version(self, project_id: str, discussion_id: str, timestamp: str) -> Optional[DiscussionCheckpoint]:
        """Load a specific version of a checkpoint.

        Args:
            project_id: Project identifier.
            discussion_id: Discussion identifier.
            timestamp: Timestamp of the version to load.

        Returns:
            DiscussionCheckpoint if found, None otherwise.
        """
        path = self._checkpoint_path(project_id, discussion_id, timestamp)
        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return DiscussionCheckpoint.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to load checkpoint version {path}: {e}")
            return None

    def delete(self, project_id: str, discussion_id: str) -> bool:
        """Delete all checkpoints for a discussion.

        Args:
            project_id: Project identifier.
            discussion_id: Discussion identifier.

        Returns:
            True if any checkpoints were deleted.
        """
        files = self._list_checkpoints(project_id, discussion_id)
        latest_path = self._checkpoint_path(project_id, discussion_id)

        deleted = False
        for path in files:
            try:
                path.unlink()
                deleted = True
            except OSError as e:
                logger.warning(f"Failed to delete checkpoint {path}: {e}")

        if latest_path.exists():
            try:
                latest_path.unlink()
                deleted = True
            except OSError as e:
                logger.warning(f"Failed to delete latest checkpoint: {e}")

        if deleted:
            logger.info(f"Deleted checkpoints for {discussion_id}")
        return deleted

    def exists(self, project_id: str, discussion_id: str) -> bool:
        """Check if a checkpoint exists for a discussion.

        Args:
            project_id: Project identifier.
            discussion_id: Discussion identifier.

        Returns:
            True if checkpoint exists.
        """
        return self._checkpoint_path(project_id, discussion_id).exists()

    def list_discussions_with_checkpoints(self, project_id: str) -> list[str]:
        """List all discussions with checkpoints for a project.

        Args:
            project_id: Project identifier.

        Returns:
            List of discussion IDs with checkpoints.
        """
        checkpoint_dir = self._checkpoint_dir(project_id)
        if not checkpoint_dir.exists():
            return []

        # Find all *_latest.json files
        latest_files = list(checkpoint_dir.glob("*_latest.json"))
        discussion_ids = []

        for path in latest_files:
            # Extract discussion ID from filename
            name = path.stem  # Remove .json
            if name.endswith("_latest"):
                discussion_id = name[:-7]  # Remove _latest
                discussion_ids.append(discussion_id)

        return discussion_ids

    def _cleanup_old_checkpoints(self, project_id: str, discussion_id: str) -> None:
        """Clean up old checkpoint versions.

        Keeps the latest N versions and removes those older than max_age_days.

        Args:
            project_id: Project identifier.
            discussion_id: Discussion identifier.
        """
        files = self._list_checkpoints(project_id, discussion_id)

        # Keep only versioned files (not _latest)
        versioned_files = [f for f in files if not f.stem.endswith("_latest")]

        # Remove excess versions
        if len(versioned_files) > self.retention_count:
            for path in versioned_files[self.retention_count:]:
                try:
                    path.unlink()
                    logger.debug(f"Deleted old checkpoint: {path}")
                except OSError:
                    pass

        # Remove old checkpoints
        cutoff = datetime.utcnow() - timedelta(days=self.max_age_days)
        for path in versioned_files:
            try:
                mtime = datetime.fromtimestamp(path.stat().st_mtime)
                if mtime < cutoff:
                    path.unlink()
                    logger.debug(f"Deleted expired checkpoint: {path}")
            except OSError:
                pass

    def cleanup_project(self, project_id: str) -> int:
        """Clean up all expired checkpoints for a project.

        Args:
            project_id: Project identifier.

        Returns:
            Number of checkpoints deleted.
        """
        checkpoint_dir = self._checkpoint_dir(project_id)
        if not checkpoint_dir.exists():
            return 0

        deleted = 0
        cutoff = datetime.utcnow() - timedelta(days=self.max_age_days)

        for path in checkpoint_dir.glob("*.json"):
            if path.stem.endswith("_latest"):
                continue  # Don't delete latest pointers

            try:
                mtime = datetime.fromtimestamp(path.stat().st_mtime)
                if mtime < cutoff:
                    path.unlink()
                    deleted += 1
            except OSError:
                pass

        if deleted:
            logger.info(f"Cleaned up {deleted} expired checkpoints for {project_id}")
        return deleted

    def update_module_state(
        self,
        checkpoint: DiscussionCheckpoint,
        module_id: str,
        discussion_id: str,
        round_num: int,
        message_count: int,
        last_message_id: Optional[str] = None,
    ) -> DiscussionCheckpoint:
        """Update the current module state in a checkpoint.

        Args:
            checkpoint: Checkpoint to update.
            module_id: Current module ID.
            discussion_id: Discussion ID for the module.
            round_num: Current round number.
            message_count: Number of messages so far.
            last_message_id: ID of the last message (cursor).

        Returns:
            Updated checkpoint (also saved to disk).
        """
        checkpoint.current_module_state = ModuleState(
            module_id=module_id,
            discussion_id=discussion_id,
            round=round_num,
            message_count=message_count,
            last_message_id=last_message_id,
        )
        self.save(checkpoint)
        return checkpoint

    def mark_module_completed(
        self,
        checkpoint: DiscussionCheckpoint,
        module_id: str,
        design_doc_path: str,
        key_decisions: list[str],
    ) -> DiscussionCheckpoint:
        """Mark a module as completed in the checkpoint.

        Args:
            checkpoint: Checkpoint to update.
            module_id: Completed module ID.
            design_doc_path: Path to generated design document.
            key_decisions: List of key decisions from the discussion.

        Returns:
            Updated checkpoint (also saved to disk).
        """
        checkpoint.completed_modules.append(
            CompletedModule(
                module_id=module_id,
                design_doc_path=design_doc_path,
                key_decisions=key_decisions,
            )
        )
        checkpoint.current_module_index += 1
        checkpoint.current_module_state = None
        self.save(checkpoint)
        return checkpoint
