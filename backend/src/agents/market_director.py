"""Market Director Agent - Provides market insights in concept discussions."""

from src.agents.base import BaseAgent


class MarketDirector(BaseAgent):
    """Market Director agent providing market and commercial perspective.

    Participates in concept incubation discussions to help evaluate the
    market viability and positioning of game concepts.
    """

    role_name = "market_director"

    def get_tools(self) -> list:
        return []
