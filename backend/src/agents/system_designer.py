"""System Designer Agent - 系统策划角色."""

from typing import Any

from src.agents.base import BaseAgent


class SystemDesigner(BaseAgent):
    """System Designer agent representing the systems design role.

    The System Designer focuses on:
    - Core gameplay loop design
    - System architecture planning
    - Feature module division
    - Inter-system interaction design
    - Technical feasibility assessment
    """

    role_name = "system_designer"

    def get_tools(self) -> list[Any]:
        """Get tools available to the System Designer.

        Currently returns an empty list as no specific tools are defined.
        Can be extended to include design documentation tools, diagram tools, etc.

        Returns:
            Empty list (no tools defined yet).
        """
        return []
