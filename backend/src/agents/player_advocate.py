"""Player Advocate Agent - 玩家代言人角色."""

from typing import Any

from src.agents.base import BaseAgent


class PlayerAdvocate(BaseAgent):
    """Player Advocate agent representing the player's perspective.

    The Player Advocate focuses on:
    - Player experience evaluation
    - Onboarding difficulty analysis
    - Frustration detection
    - Pay-to-win fairness
    - Social experience
    - Game pacing
    - New player guidance
    """

    role_name = "player_advocate"

    def get_tools(self) -> list[Any]:
        """Get tools available to the Player Advocate.

        Currently returns an empty list as no specific tools are defined.
        Can be extended to include player feedback tools, survey tools, etc.

        Returns:
            Empty list (no tools defined yet).
        """
        return []
