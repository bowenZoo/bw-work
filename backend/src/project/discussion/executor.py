"""Background executor for batch discussions with persistence and recovery."""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Default settings
DEFAULT_MAX_CONCURRENCY = 2
DEFAULT_QUEUE_SIZE = 100


class TaskStatus(str, Enum):
    """Status of a background task."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskRecord:
    """Record of a background task for persistence."""

    task_id: str
    task_type: str  # "batch_discussion", etc.
    project_id: str
    discussion_id: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    config: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for persistence."""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "project_id": self.project_id,
            "discussion_id": self.discussion_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
            "config": self.config,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TaskRecord":
        """Create from dictionary."""
        return cls(
            task_id=data["task_id"],
            task_type=data["task_type"],
            project_id=data["project_id"],
            discussion_id=data["discussion_id"],
            status=TaskStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            error=data.get("error"),
            config=data.get("config", {}),
        )


class BatchExecutor:
    """Manages background execution of batch discussions.

    Features:
    - Task persistence for recovery after restart
    - Concurrency control
    - Task queue management
    - Automatic recovery on startup
    """

    def __init__(
        self,
        data_dir: str = "data/projects",
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
        queue_size: int = DEFAULT_QUEUE_SIZE,
    ):
        """Initialize the executor.

        Args:
            data_dir: Base data directory.
            max_concurrency: Maximum concurrent discussions.
            queue_size: Maximum queue size.
        """
        self.data_dir = Path(data_dir)
        self.max_concurrency = max_concurrency
        self.queue_size = queue_size

        self._registry_path = self.data_dir / ".task_registry.json"
        self._tasks: dict[str, TaskRecord] = {}
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=queue_size)
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._shutdown = False

        # Task factory function
        self._task_factory: Optional[Callable] = None

    def set_task_factory(self, factory: Callable) -> None:
        """Set the factory function for creating discussion runners.

        Args:
            factory: Function that creates and runs a batch discussion.
        """
        self._task_factory = factory

    def _load_registry(self) -> None:
        """Load task registry from disk."""
        if not self._registry_path.exists():
            return

        try:
            with open(self._registry_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._tasks = {
                task_id: TaskRecord.from_dict(record)
                for task_id, record in data.items()
            }
            logger.info(f"Loaded {len(self._tasks)} tasks from registry")
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to load task registry: {e}")

    def _save_registry(self) -> None:
        """Save task registry to disk."""
        self.data_dir.mkdir(parents=True, exist_ok=True)

        data = {task_id: record.to_dict() for task_id, record in self._tasks.items()}

        temp_path = self._registry_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        temp_path.replace(self._registry_path)

    def register_task(
        self,
        task_id: str,
        task_type: str,
        project_id: str,
        discussion_id: str,
        config: Optional[dict] = None,
    ) -> TaskRecord:
        """Register a new task.

        Args:
            task_id: Unique task identifier.
            task_type: Type of task.
            project_id: Project identifier.
            discussion_id: Discussion identifier.
            config: Optional task configuration.

        Returns:
            Created TaskRecord.
        """
        now = datetime.utcnow()
        record = TaskRecord(
            task_id=task_id,
            task_type=task_type,
            project_id=project_id,
            discussion_id=discussion_id,
            status=TaskStatus.PENDING,
            created_at=now,
            updated_at=now,
            config=config or {},
        )

        self._tasks[task_id] = record
        self._save_registry()
        logger.info(f"Registered task {task_id}")
        return record

    def update_status(
        self,
        task_id: str,
        status: TaskStatus,
        error: Optional[str] = None,
    ) -> Optional[TaskRecord]:
        """Update task status.

        Args:
            task_id: Task identifier.
            status: New status.
            error: Optional error message.

        Returns:
            Updated TaskRecord or None if not found.
        """
        record = self._tasks.get(task_id)
        if not record:
            return None

        record.status = status
        record.updated_at = datetime.utcnow()

        if status == TaskStatus.RUNNING and not record.started_at:
            record.started_at = datetime.utcnow()
        elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            record.completed_at = datetime.utcnow()

        if error:
            record.error = error

        self._save_registry()
        return record

    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        """Get a task by ID.

        Args:
            task_id: Task identifier.

        Returns:
            TaskRecord or None if not found.
        """
        return self._tasks.get(task_id)

    def get_tasks_by_project(self, project_id: str) -> list[TaskRecord]:
        """Get all tasks for a project.

        Args:
            project_id: Project identifier.

        Returns:
            List of TaskRecords.
        """
        return [t for t in self._tasks.values() if t.project_id == project_id]

    def get_pending_tasks(self) -> list[TaskRecord]:
        """Get all pending tasks.

        Returns:
            List of pending TaskRecords.
        """
        return [t for t in self._tasks.values() if t.status == TaskStatus.PENDING]

    def get_running_tasks(self) -> list[TaskRecord]:
        """Get all running tasks.

        Returns:
            List of running TaskRecords.
        """
        return [t for t in self._tasks.values() if t.status == TaskStatus.RUNNING]

    async def submit(self, task_id: str) -> bool:
        """Submit a task for execution.

        Args:
            task_id: Task identifier.

        Returns:
            True if submitted successfully.
        """
        record = self._tasks.get(task_id)
        if not record:
            logger.error(f"Task {task_id} not found")
            return False

        if record.status != TaskStatus.PENDING:
            logger.warning(f"Task {task_id} not in pending state")
            return False

        try:
            await self._queue.put(task_id)
            logger.info(f"Submitted task {task_id} to queue")
            return True
        except asyncio.QueueFull:
            logger.error(f"Queue full, cannot submit task {task_id}")
            return False

    async def cancel(self, task_id: str) -> bool:
        """Cancel a task.

        Args:
            task_id: Task identifier.

        Returns:
            True if cancelled successfully.
        """
        record = self._tasks.get(task_id)
        if not record:
            return False

        if record.status == TaskStatus.RUNNING:
            # Cancel running task
            running_task = self._running_tasks.get(task_id)
            if running_task:
                running_task.cancel()
                del self._running_tasks[task_id]

        self.update_status(task_id, TaskStatus.CANCELLED)
        logger.info(f"Cancelled task {task_id}")
        return True

    async def _process_queue(self) -> None:
        """Process tasks from the queue."""
        while not self._shutdown:
            try:
                task_id = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            record = self._tasks.get(task_id)
            if not record or record.status != TaskStatus.PENDING:
                self._queue.task_done()
                continue

            # Acquire semaphore for concurrency control
            async with self._semaphore:
                await self._execute_task(task_id)
                self._queue.task_done()

    async def _execute_task(self, task_id: str) -> None:
        """Execute a single task.

        Args:
            task_id: Task identifier.
        """
        record = self._tasks.get(task_id)
        if not record:
            return

        self.update_status(task_id, TaskStatus.RUNNING)

        try:
            if not self._task_factory:
                raise RuntimeError("Task factory not set")

            # Create async task
            task = asyncio.create_task(
                self._task_factory(
                    project_id=record.project_id,
                    discussion_id=record.discussion_id,
                    config=record.config,
                )
            )
            self._running_tasks[task_id] = task

            # Wait for completion
            await task

            self.update_status(task_id, TaskStatus.COMPLETED)
            logger.info(f"Task {task_id} completed")

        except asyncio.CancelledError:
            self.update_status(task_id, TaskStatus.CANCELLED)
            logger.info(f"Task {task_id} cancelled")
        except Exception as e:
            logger.exception(f"Task {task_id} failed: {e}")
            self.update_status(task_id, TaskStatus.FAILED, str(e))
        finally:
            if task_id in self._running_tasks:
                del self._running_tasks[task_id]

    async def start(self) -> None:
        """Start the executor and recover pending tasks."""
        self._load_registry()
        self._shutdown = False

        # Recover tasks that were running before shutdown
        for task_id, record in self._tasks.items():
            if record.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                # Reset running tasks to pending for re-execution
                if record.status == TaskStatus.RUNNING:
                    self.update_status(task_id, TaskStatus.PENDING)
                await self.submit(task_id)

        # Start queue processor
        asyncio.create_task(self._process_queue())
        logger.info("BatchExecutor started")

    async def shutdown(self) -> None:
        """Shutdown the executor gracefully."""
        self._shutdown = True

        # Cancel all running tasks
        for task_id, task in list(self._running_tasks.items()):
            task.cancel()
            self.update_status(task_id, TaskStatus.PENDING)  # Will be recovered on restart

        # Wait for queue to drain
        await self._queue.join()

        self._save_registry()
        logger.info("BatchExecutor shutdown complete")

    def cleanup_completed(self, max_age_days: int = 7) -> int:
        """Clean up old completed/failed tasks.

        Args:
            max_age_days: Maximum age of tasks to keep.

        Returns:
            Number of tasks removed.
        """
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(days=max_age_days)
        to_remove = []

        for task_id, record in self._tasks.items():
            if record.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                if record.completed_at and record.completed_at < cutoff:
                    to_remove.append(task_id)

        for task_id in to_remove:
            del self._tasks[task_id]

        if to_remove:
            self._save_registry()
            logger.info(f"Cleaned up {len(to_remove)} old tasks")

        return len(to_remove)


# Global executor instance
_executor: Optional[BatchExecutor] = None


def get_executor() -> BatchExecutor:
    """Get the global executor instance."""
    global _executor
    if _executor is None:
        _executor = BatchExecutor()
    return _executor


async def initialize_executor(
    data_dir: str = "data/projects",
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
) -> BatchExecutor:
    """Initialize and start the global executor.

    Args:
        data_dir: Base data directory.
        max_concurrency: Maximum concurrent discussions.

    Returns:
        Initialized BatchExecutor.
    """
    global _executor
    _executor = BatchExecutor(data_dir, max_concurrency)
    await _executor.start()
    return _executor
