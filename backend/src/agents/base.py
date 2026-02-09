"""Base Agent class for the AI Game Design Team."""

from abc import ABC, abstractmethod
from typing import Any

from crewai import Agent, Crew, Process, Task

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

    def _build_response_prompt(self, context: str) -> str:
        """Build a response prompt for the agent.

        Args:
            context: The discussion context to respond to.

        Returns:
            Formatted prompt string.
        """
        return f"""
作为{self.role}，请针对以下讨论内容，从你的专业角度发表观点。

你的背景：{self.backstory}

你的关注点：
{chr(10).join(f"- {area}" for area in self.focus_areas)}

讨论上下文：
{context}

请：
1. 回应讨论中提出的问题
2. 从你的专业角度提出设计建议
3. 指出你认为需要关注的风险或挑战
"""

    def respond_sync(self, context: str) -> str:
        """Synchronously generate a response to the given context.

        Creates a temporary Crew with a single task and runs it synchronously.

        Args:
            context: The discussion context to respond to.

        Returns:
            The agent's response as a string.
        """
        task = Task(
            description=self._build_response_prompt(context),
            expected_output=f"{self.role}对讨论内容的专业分析和建议",
            agent=self.build_agent(),
        )

        crew = Crew(
            agents=[self.build_agent()],
            tasks=[task],
            process=Process.sequential,
        )

        result = crew.kickoff()
        return str(result)

    async def respond_async(self, context: str) -> str:
        """Asynchronously generate a response to the given context.

        This method creates a temporary Crew with a single task to generate
        a response based on the discussion context.

        Args:
            context: The discussion context to respond to.

        Returns:
            The agent's response as a string.
        """
        task = Task(
            description=self._build_response_prompt(context),
            expected_output=f"{self.role}对讨论内容的专业分析和建议",
            agent=self.build_agent(),
        )

        crew = Crew(
            agents=[self.build_agent()],
            tasks=[task],
            process=Process.sequential,
        )

        result = await crew.kickoff_async()
        return str(result)

    def __repr__(self) -> str:
        """Return string representation of the agent."""
        return f"<{self.__class__.__name__}(role='{self.role}')>"
