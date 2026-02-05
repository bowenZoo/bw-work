"""Batch discussion runner for executing multiple module discussions."""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

from src.project.models import (
    DiscussionCheckpoint,
    DiscussionProgress,
    GDDModule,
    ModuleDiscussionResult,
    ModuleDiscussionStatus,
    ProjectDiscussion,
    ProjectDiscussionStatus,
)
from src.project.discussion.checkpoint import CheckpointManager
from src.project.discussion.project_memory import ProjectMemory

logger = logging.getLogger(__name__)


class BatchRunnerState(str, Enum):
    """State of the batch runner."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ModuleDiscussionContext:
    """Context for a single module discussion."""

    module: GDDModule
    project_id: str
    gdd_id: str
    project_memory_context: str
    max_rounds: int = 10


@dataclass
class BatchDiscussionConfig:
    """Configuration for batch discussion execution."""

    max_rounds_per_module: int = 10
    checkpoint_interval_seconds: int = 60
    ws_throttle_ms: int = 300
    max_retries: int = 3


# Type for WebSocket broadcast function
WSBroadcastFunc = Callable[[str, dict], Any]


class BatchDiscussionRunner:
    """Executes batch discussions across multiple modules.

    Handles:
    - Sequential module discussions
    - Checkpoint/resume
    - Progress tracking
    - WebSocket notifications
    """

    def __init__(
        self,
        project_id: str,
        gdd_id: str,
        modules: list[GDDModule],
        module_order: list[str],
        data_dir: str = "data/projects",
        config: Optional[BatchDiscussionConfig] = None,
    ):
        """Initialize the batch runner.

        Args:
            project_id: Project identifier.
            gdd_id: GDD document identifier.
            modules: List of modules to discuss.
            module_order: Order of module IDs for discussion.
            data_dir: Base data directory.
            config: Optional configuration.
        """
        self.project_id = project_id
        self.gdd_id = gdd_id
        self.modules = {m.id: m for m in modules}
        self.module_order = module_order
        self.data_dir = Path(data_dir)
        self.config = config or BatchDiscussionConfig()

        # State
        self.discussion_id = f"disc_batch_{uuid.uuid4().hex[:12]}"
        self.state = BatchRunnerState.PENDING
        self.current_module_index = 0
        self.results: list[ModuleDiscussionResult] = []
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None

        # Managers
        self.checkpoint_manager = CheckpointManager(data_dir)
        self.project_memory = ProjectMemory(data_dir)

        # WebSocket callback
        self._ws_broadcast: Optional[WSBroadcastFunc] = None
        self._last_ws_time = 0.0

        # Control flags
        self._pause_requested = False
        self._skip_requested = False

    def set_ws_broadcast(self, broadcast_func: WSBroadcastFunc) -> None:
        """Set the WebSocket broadcast function.

        Args:
            broadcast_func: Function to broadcast messages.
        """
        self._ws_broadcast = broadcast_func

    def _broadcast(self, event_type: str, data: dict) -> None:
        """Broadcast a WebSocket message with throttling.

        Args:
            event_type: Type of event.
            data: Event data.
        """
        if not self._ws_broadcast:
            return

        # Apply throttling
        now = time.time() * 1000
        if now - self._last_ws_time < self.config.ws_throttle_ms:
            return

        self._last_ws_time = now

        try:
            message = {"type": event_type, "project_id": self.project_id, **data}
            self._ws_broadcast(self.project_id, message)
        except Exception as e:
            logger.warning(f"WebSocket broadcast failed: {e}")

    def get_discussion(self) -> ProjectDiscussion:
        """Get the current discussion state.

        Returns:
            ProjectDiscussion object.
        """
        return ProjectDiscussion(
            id=self.discussion_id,
            project_id=self.project_id,
            gdd_id=self.gdd_id,
            selected_modules=list(self.modules.keys()),
            module_order=self.module_order,
            status=ProjectDiscussionStatus(self.state.value),
            progress=DiscussionProgress(
                total_modules=len(self.module_order),
                completed_modules=len(self.results),
                current_module=self.module_order[self.current_module_index]
                if self.current_module_index < len(self.module_order)
                else None,
                current_round=0,
            ),
            created_at=self.start_time or datetime.utcnow(),
        )

    def request_pause(self) -> None:
        """Request the runner to pause after current module."""
        self._pause_requested = True
        logger.info(f"Pause requested for {self.discussion_id}")

    def request_skip(self) -> None:
        """Request to skip the current module."""
        self._skip_requested = True
        logger.info(f"Skip requested for {self.discussion_id}")

    def _create_checkpoint(self) -> DiscussionCheckpoint:
        """Create a checkpoint for the current state."""
        from src.project.models import CompletedModule

        completed = [
            CompletedModule(
                module_id=r.module_id,
                design_doc_path=r.design_doc.path if r.design_doc else "",
                key_decisions=[d.content for d in r.key_decisions],
            )
            for r in self.results
        ]

        return DiscussionCheckpoint(
            project_id=self.project_id,
            gdd_id=self.gdd_id,
            discussion_id=self.discussion_id,
            selected_modules=list(self.modules.keys()),
            current_module_index=self.current_module_index,
            completed_modules=completed,
        )

    async def run(self) -> list[ModuleDiscussionResult]:
        """Execute the batch discussion.

        Returns:
            List of results for each module discussion.
        """
        self.state = BatchRunnerState.RUNNING
        self.start_time = datetime.utcnow()

        # Load project memory
        self.project_memory.load(self.project_id)

        # Broadcast start
        self._broadcast(
            "project_discussion_start",
            {
                "discussion_id": self.discussion_id,
                "total_modules": len(self.module_order),
                "module_order": self.module_order,
            },
        )

        try:
            while self.current_module_index < len(self.module_order):
                # Check for pause
                if self._pause_requested:
                    await self._handle_pause()
                    break

                # Get current module
                module_id = self.module_order[self.current_module_index]
                module = self.modules.get(module_id)

                if not module:
                    logger.warning(f"Module {module_id} not found, skipping")
                    self.current_module_index += 1
                    continue

                # Run module discussion
                result = await self._run_module_discussion(module)
                self.results.append(result)

                # Save checkpoint
                checkpoint = self._create_checkpoint()
                self.checkpoint_manager.save(checkpoint)

                # Move to next module
                self.current_module_index += 1
                self._skip_requested = False

            # All modules completed
            if not self._pause_requested:
                self.state = BatchRunnerState.COMPLETED
                self.end_time = datetime.utcnow()

                # Broadcast completion
                duration = (self.end_time - self.start_time).total_seconds() / 60
                self._broadcast(
                    "project_discussion_complete",
                    {
                        "discussion_id": self.discussion_id,
                        "total_duration_minutes": duration,
                        "design_docs": [
                            r.design_doc.path for r in self.results if r.design_doc
                        ],
                        "summary_path": f"data/projects/{self.project_id}/design/index.md",
                    },
                )

        except Exception as e:
            logger.exception(f"Batch discussion failed: {e}")
            self.state = BatchRunnerState.FAILED
            raise

        return self.results

    async def resume(self, checkpoint: DiscussionCheckpoint) -> list[ModuleDiscussionResult]:
        """Resume a batch discussion from a checkpoint.

        Args:
            checkpoint: Checkpoint to resume from.

        Returns:
            List of results for remaining module discussions.
        """
        # Restore state from checkpoint
        self.discussion_id = checkpoint.discussion_id
        self.current_module_index = checkpoint.current_module_index

        # Restore completed results (simplified - full restoration would need more data)
        for cm in checkpoint.completed_modules:
            result = ModuleDiscussionResult(
                module_id=cm.module_id,
                module_name=self.modules.get(cm.module_id, GDDModule(id=cm.module_id, name=cm.module_id, description="", source_section="")).name,
                discussion_id=f"resumed_{cm.module_id}",
                status=ModuleDiscussionStatus.COMPLETED,
                key_decisions=[],
            )
            self.results.append(result)

        logger.info(f"Resumed batch discussion {self.discussion_id} from module {self.current_module_index}")

        # Continue execution
        return await self.run()

    async def _run_module_discussion(self, module: GDDModule) -> ModuleDiscussionResult:
        """Run a single module discussion.

        Args:
            module: Module to discuss.

        Returns:
            ModuleDiscussionResult.
        """
        start_time = datetime.utcnow()

        # Broadcast module start
        self._broadcast(
            "module_discussion_start",
            {
                "discussion_id": self.discussion_id,
                "module_id": module.id,
                "module_name": module.name,
                "module_index": self.current_module_index,
                "total_modules": len(self.module_order),
            },
        )

        # Get context from project memory
        context = self.project_memory.get_context_for_module(module.id, module.dependencies)

        try:
            # Check for skip request
            if self._skip_requested:
                logger.info(f"Skipping module {module.id}")
                return ModuleDiscussionResult(
                    module_id=module.id,
                    module_name=module.name,
                    discussion_id=f"skipped_{module.id}",
                    status=ModuleDiscussionStatus.SKIPPED,
                )

            # TODO: Integrate with actual discussion crew
            # For now, create a placeholder result
            result = await self._execute_module_discussion(module, context)

            # Update project memory with decisions
            for decision in result.key_decisions:
                self.project_memory.add_decision(
                    module_id=module.id,
                    module_name=module.name,
                    decision=decision.content,
                    rationale=decision.rationale,
                )

            # Broadcast module completion
            self._broadcast(
                "module_discussion_complete",
                {
                    "discussion_id": self.discussion_id,
                    "module_id": module.id,
                    "design_doc_path": result.design_doc.path if result.design_doc else "",
                    "key_decisions": [d.content for d in result.key_decisions],
                },
            )

            return result

        except Exception as e:
            logger.exception(f"Module discussion failed for {module.id}: {e}")
            return ModuleDiscussionResult(
                module_id=module.id,
                module_name=module.name,
                discussion_id=f"failed_{module.id}",
                status=ModuleDiscussionStatus.FAILED,
            )

    async def _execute_module_discussion(
        self, module: GDDModule, context: str
    ) -> ModuleDiscussionResult:
        """Execute the actual module discussion using the discussion crew.

        This is a placeholder that should be integrated with the actual
        DiscussionCrew implementation.

        Args:
            module: Module to discuss.
            context: Project context for the discussion.

        Returns:
            ModuleDiscussionResult.
        """
        # Placeholder implementation
        # In real implementation, this would:
        # 1. Create a DiscussionCrew with module context
        # 2. Run the discussion
        # 3. Generate design document
        # 4. Extract key decisions

        discussion_id = f"mod_disc_{uuid.uuid4().hex[:8]}"

        # Simulate discussion progress
        for round_num in range(1, min(module.estimated_rounds + 1, self.config.max_rounds_per_module + 1)):
            if self._skip_requested or self._pause_requested:
                break

            # Broadcast progress
            self._broadcast(
                "module_discussion_progress",
                {
                    "discussion_id": self.discussion_id,
                    "module_id": module.id,
                    "round": round_num,
                    "speaker": "System",
                    "summary": f"Round {round_num} of {module.name} discussion",
                },
            )

            # Small delay to simulate processing
            await asyncio.sleep(0.1)

        # Create result
        from src.project.models import DesignDoc, Decision

        design_doc = DesignDoc(
            path=f"data/projects/{self.project_id}/design/{module.id}-system.md",
            version="1.0",
            sections=["Overview", "Mechanics", "Parameters"],
        )

        return ModuleDiscussionResult(
            module_id=module.id,
            module_name=module.name,
            discussion_id=discussion_id,
            status=ModuleDiscussionStatus.COMPLETED,
            design_doc=design_doc,
            key_decisions=[
                Decision(
                    module_id=module.id,
                    content=f"Placeholder decision for {module.name}",
                    rationale="Placeholder rationale",
                )
            ],
            duration_minutes=module.estimated_rounds * 0.5,
            token_usage=0,
        )

    async def _handle_pause(self) -> None:
        """Handle pause request."""
        self.state = BatchRunnerState.PAUSED
        checkpoint = self._create_checkpoint()
        self.checkpoint_manager.save(checkpoint)

        self._broadcast(
            "discussion_paused",
            {
                "discussion_id": self.discussion_id,
                "checkpoint_id": f"{self.discussion_id}_latest",
                "current_module": self.module_order[self.current_module_index]
                if self.current_module_index < len(self.module_order)
                else None,
                "completed_modules": len(self.results),
            },
        )

        logger.info(f"Discussion {self.discussion_id} paused at module {self.current_module_index}")
        self._pause_requested = False
