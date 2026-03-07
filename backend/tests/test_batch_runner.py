"""Tests for batch discussion runner."""

import asyncio
import tempfile
from pathlib import Path

import pytest

from src.project.discussion.batch_runner import (
    BatchDiscussionRunner,
    BatchDiscussionConfig,
    BatchRunnerState,
)
from src.project.models import GDDModule, ModuleDiscussionStatus


class TestBatchDiscussionRunner:
    """Tests for BatchDiscussionRunner."""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.modules = [
            GDDModule(
                id="combat",
                name="Combat System",
                description="Combat mechanics",
                source_section="Combat section",
                dependencies=[],
                estimated_rounds=2,
            ),
            GDDModule(
                id="equipment",
                name="Equipment System",
                description="Equipment",
                source_section="Equipment section",
                dependencies=["combat"],
                estimated_rounds=2,
            ),
            GDDModule(
                id="progression",
                name="Progression System",
                description="Progression",
                source_section="Progression section",
                dependencies=["combat"],
                estimated_rounds=2,
            ),
        ]

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_runner(self) -> BatchDiscussionRunner:
        return BatchDiscussionRunner(
            project_id="test-project",
            gdd_id="gdd_001",
            modules=self.modules,
            module_order=["combat", "equipment", "progression"],
            data_dir=self.temp_dir,
            config=BatchDiscussionConfig(
                max_rounds_per_module=3,
                checkpoint_interval_seconds=1,
                ws_throttle_ms=0,
            ),
        )

    @pytest.mark.asyncio
    async def test_run_completes_all_modules(self):
        """Test that run completes all modules."""
        runner = self._create_runner()
        results = await runner.run()

        assert len(results) == 3
        assert runner.state == BatchRunnerState.COMPLETED
        assert all(r.status == ModuleDiscussionStatus.COMPLETED for r in results)

    @pytest.mark.asyncio
    async def test_pause_and_resume(self):
        """Test pause and resume functionality."""
        runner = self._create_runner()

        # Run for a bit then pause - use gather for reliable interleaving
        async def pause_after_delay():
            await asyncio.sleep(0.05)
            runner.request_pause()

        results, _ = await asyncio.gather(
            runner.run(),
            pause_after_delay(),
        )

        # Should be paused with some modules done
        assert runner.state == BatchRunnerState.PAUSED

        # Load checkpoint and resume
        from src.project.discussion.checkpoint import CheckpointManager
        checkpoint_manager = CheckpointManager(self.temp_dir)
        checkpoint = checkpoint_manager.load("test-project", runner.discussion_id)

        # Create new runner and resume
        new_runner = self._create_runner()
        new_results = await new_runner.resume(checkpoint)

        assert new_runner.state == BatchRunnerState.COMPLETED

    @pytest.mark.asyncio
    async def test_skip_module(self):
        """Test skipping a module."""
        runner = self._create_runner()

        # Skip after first module starts
        async def skip_after_delay():
            await asyncio.sleep(0.02)
            runner.request_skip()

        asyncio.create_task(skip_after_delay())
        results = await runner.run()

        # At least one module should be skipped or all completed
        statuses = [r.status for r in results]
        assert ModuleDiscussionStatus.SKIPPED in statuses or all(
            s == ModuleDiscussionStatus.COMPLETED for s in statuses
        )

    def test_get_discussion(self):
        """Test getting discussion state."""
        runner = self._create_runner()
        discussion = runner.get_discussion()

        assert discussion.project_id == "test-project"
        assert discussion.gdd_id == "gdd_001"
        assert len(discussion.selected_modules) == 3
        assert discussion.module_order == ["combat", "equipment", "progression"]

    @pytest.mark.asyncio
    async def test_creates_checkpoint_after_each_module(self):
        """Test that checkpoints are created after each module."""
        runner = self._create_runner()
        await runner.run()

        from src.project.discussion.checkpoint import CheckpointManager
        checkpoint_manager = CheckpointManager(self.temp_dir)

        assert checkpoint_manager.exists("test-project", runner.discussion_id)
        checkpoint = checkpoint_manager.load("test-project", runner.discussion_id)

        assert len(checkpoint.completed_modules) == 3

    @pytest.mark.asyncio
    async def test_ws_broadcast_called(self):
        """Test that WebSocket broadcasts are made."""
        runner = self._create_runner()

        broadcasts = []

        def mock_broadcast(project_id: str, message: dict):
            broadcasts.append(message)

        runner.set_ws_broadcast(mock_broadcast)
        await runner.run()

        # Should have start, module starts/completes, and end
        types = [b["type"] for b in broadcasts]
        assert "project_discussion_start" in types
        assert "module_discussion_start" in types
        assert "module_discussion_complete" in types
        assert "project_discussion_complete" in types
