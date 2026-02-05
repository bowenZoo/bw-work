"""Project discussion module.

Provides functionality for:
- Project-level memory management
- Batch discussion execution
- Checkpoint/resume support
"""

# Lazy imports to avoid circular dependencies
__all__ = ["ProjectMemory", "CheckpointManager"]


def __getattr__(name: str):
    if name == "ProjectMemory":
        from src.project.discussion.project_memory import ProjectMemory
        return ProjectMemory
    elif name == "CheckpointManager":
        from src.project.discussion.checkpoint import CheckpointManager
        return CheckpointManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
