"""Operations Analyst Agent - 运营策划角色."""

from typing import Any

from src.agents.base import BaseAgent


class OperationsAnalyst(BaseAgent):
    """Operations Analyst agent representing the operations planning role.

    The Operations Analyst focuses on:
    - Operational feasibility assessment
    - MVP scope definition
    - Monetization health
    - Long-term retention design
    - Content pacing and lifecycle
    - Ecosystem risk analysis
    """

    role_name = "operations_analyst"

    def get_tools(self) -> list[Any]:
        """Get tools available to the Operations Analyst.

        Returns:
            Empty list (no special tools needed).
        """
        return []
