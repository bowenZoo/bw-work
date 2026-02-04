"""Number Designer Agent - 数值策划角色."""

from typing import Any

from src.agents.base import BaseAgent


class NumberDesigner(BaseAgent):
    """Number Designer agent representing the numerical design role.

    The Number Designer focuses on:
    - Combat formula design
    - Attribute growth curves
    - Economy system balance
    - Monetization design
    - Resource generation/consumption
    - Difficulty curve design
    """

    role_name = "number_designer"

    def get_tools(self) -> list[Any]:
        """Get tools available to the Number Designer.

        Currently returns an empty list as no specific tools are defined.
        Can be extended to include calculation tools, simulation tools, etc.

        Returns:
            Empty list (no tools defined yet).
        """
        return []
