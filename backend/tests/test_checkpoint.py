"""Tests for checkpoint management."""

import tempfile
from pathlib import Path

import pytest

from src.project.discussion.checkpoint import CheckpointManager
from src.project.models import DiscussionCheckpoint, ModuleState, CompletedModule


class TestCheckpointManager:
    """Tests for CheckpointManager."""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.manager = CheckpointManager(data_dir=self.temp_dir, retention_count=3)

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_checkpoint(self, discussion_id: str = "disc_001") -> DiscussionCheckpoint:
        """Create a test checkpoint."""
        return DiscussionCheckpoint(
            project_id="test-project",
            gdd_id="gdd_001",
            discussion_id=discussion_id,
            selected_modules=["combat", "equipment", "progression"],
            current_module_index=1,
        )

    def test_save_and_load(self):
        """Test saving and loading checkpoint."""
        checkpoint = self._create_checkpoint()
        self.manager.save(checkpoint)

        loaded = self.manager.load("test-project", "disc_001")

        assert loaded is not None
        assert loaded.project_id == "test-project"
        assert loaded.discussion_id == "disc_001"
        assert loaded.selected_modules == ["combat", "equipment", "progression"]
        assert loaded.current_module_index == 1

    def test_save_creates_versioned_file(self):
        """Test that save creates versioned files."""
        checkpoint = self._create_checkpoint()
        self.manager.save(checkpoint)

        checkpoint_dir = Path(self.temp_dir) / "test-project" / "checkpoints"
        files = list(checkpoint_dir.glob("disc_001_*.json"))

        # Should have at least 2 files: one versioned, one _latest
        assert len(files) >= 2
        latest = checkpoint_dir / "disc_001_latest.json"
        assert latest.exists()

    def test_load_nonexistent(self):
        """Test loading nonexistent checkpoint returns None."""
        loaded = self.manager.load("test-project", "nonexistent")
        assert loaded is None

    def test_exists(self):
        """Test checkpoint existence check."""
        assert not self.manager.exists("test-project", "disc_001")

        checkpoint = self._create_checkpoint()
        self.manager.save(checkpoint)

        assert self.manager.exists("test-project", "disc_001")

    def test_delete(self):
        """Test deleting checkpoints."""
        checkpoint = self._create_checkpoint()
        self.manager.save(checkpoint)
        assert self.manager.exists("test-project", "disc_001")

        deleted = self.manager.delete("test-project", "disc_001")
        assert deleted
        assert not self.manager.exists("test-project", "disc_001")

    def test_list_discussions_with_checkpoints(self):
        """Test listing discussions with checkpoints."""
        self.manager.save(self._create_checkpoint("disc_001"))
        self.manager.save(self._create_checkpoint("disc_002"))

        discussions = self.manager.list_discussions_with_checkpoints("test-project")

        assert "disc_001" in discussions
        assert "disc_002" in discussions

    def test_update_module_state(self):
        """Test updating module state."""
        checkpoint = self._create_checkpoint()
        self.manager.save(checkpoint)

        updated = self.manager.update_module_state(
            checkpoint,
            module_id="equipment",
            discussion_id="mod_disc_001",
            round_num=3,
            message_count=15,
            last_message_id="msg_123",
        )

        assert updated.current_module_state is not None
        assert updated.current_module_state.module_id == "equipment"
        assert updated.current_module_state.round == 3
        assert updated.current_module_state.message_count == 15

        # Verify persisted
        loaded = self.manager.load("test-project", "disc_001")
        assert loaded.current_module_state.module_id == "equipment"

    def test_mark_module_completed(self):
        """Test marking module as completed."""
        checkpoint = self._create_checkpoint()
        checkpoint.current_module_index = 0
        self.manager.save(checkpoint)

        updated = self.manager.mark_module_completed(
            checkpoint,
            module_id="combat",
            design_doc_path="design/combat-system.md",
            key_decisions=["Turn-based combat", "Combo system"],
        )

        assert len(updated.completed_modules) == 1
        assert updated.completed_modules[0].module_id == "combat"
        assert updated.current_module_index == 1
        assert updated.current_module_state is None

    def test_retention_cleanup(self):
        """Test old checkpoint cleanup by retention count."""
        checkpoint = self._create_checkpoint()

        # Save multiple versions
        for i in range(5):
            checkpoint.current_module_index = i
            self.manager.save(checkpoint)
            import time
            time.sleep(0.1)  # Ensure different timestamps

        checkpoint_dir = Path(self.temp_dir) / "test-project" / "checkpoints"
        versioned_files = [f for f in checkpoint_dir.glob("disc_001_*.json")
                          if not f.stem.endswith("_latest")]

        # Should keep only retention_count (3) versioned files
        assert len(versioned_files) <= 3

    def test_save_with_completed_modules(self):
        """Test saving checkpoint with completed modules."""
        checkpoint = self._create_checkpoint()
        checkpoint.completed_modules = [
            CompletedModule(
                module_id="combat",
                design_doc_path="design/combat.md",
                key_decisions=["Decision 1"],
            )
        ]
        self.manager.save(checkpoint)

        loaded = self.manager.load("test-project", "disc_001")
        assert len(loaded.completed_modules) == 1
        assert loaded.completed_modules[0].module_id == "combat"
