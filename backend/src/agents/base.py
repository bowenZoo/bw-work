"""Base Agent class for the AI Game Design Team."""

from abc import ABC, abstractmethod
from typing import Any

from crewai import Agent

from src.config.settings import load_role_config, settings


class BaseAgent(ABC):
    """Base class for all game design team agents.

    Each agent represents a specific role in the game design team,
    with its own expertise, goals, and communication style defined
    in a YAML configuration file.
    """

    # Subclasses must define their role name
    role_name: str = ""

    def __init__(self, llm: Any | None = None) -> None:
        """Initialize the agent with its role configuration.

        Args:
            llm: Optional LLM instance to use. If not provided,
                 will use the default from CrewAI.
        """
        if not self.role_name:
            raise ValueError("Subclass must define role_name")

        self._config = load_role_config(self.role_name)
        self._llm = llm
        self._agent: Agent | None = None

    @property
    def config(self) -> dict[str, Any]:
        """Get the role configuration dictionary."""
        return self._config

    @property
    def role(self) -> str:
        """Get the agent's role title."""
        return self._config.get("role", "")

    @property
    def goal(self) -> str:
        """Get the agent's primary goal."""
        return self._config.get("goal", "")

    @property
    def backstory(self) -> str:
        """Get the agent's backstory/personality."""
        return self._config.get("backstory", "")

    @property
    def focus_areas(self) -> list[str]:
        """Get the agent's focus areas/expertise."""
        return self._config.get("focus_areas", [])

    @abstractmethod
    def get_tools(self) -> list[Any]:
        """Get the tools available to this agent.

        Returns:
            List of tool instances the agent can use.
        """
        pass

    def build_agent(self) -> Agent:
        """Build and return the CrewAI Agent instance.

        Returns:
            Configured CrewAI Agent instance.
        """
        if self._agent is None:
            agent_kwargs: dict[str, Any] = {
                "role": self.role,
                "goal": self.goal,
                "backstory": self.backstory,
                "tools": self.get_tools(),
                "verbose": settings.debug,
                "allow_delegation": False,
            }

            if self._llm is not None:
                agent_kwargs["llm"] = self._llm

            self._agent = Agent(**agent_kwargs)

        return self._agent

    def __repr__(self) -> str:
        """Return string representation of the agent."""
        return f"<{self.__class__.__name__}(role='{self.role}')>"
