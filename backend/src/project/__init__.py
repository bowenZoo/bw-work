"""Project-level discussion module.

This module provides functionality for:
- Project management
- GDD (Game Design Document) parsing
- Batch discussions with checkpoint support
- Design document generation
"""

from src.project.registry import ProjectRegistry, Project

__all__ = ["ProjectRegistry", "Project"]
