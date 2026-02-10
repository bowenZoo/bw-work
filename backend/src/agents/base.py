"""Base Agent class for the AI Game Design Team."""

import asyncio
import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Any

from crewai import Agent, Crew, Process, Task

from src.config.settings import load_role_config, settings

logger = logging.getLogger(__name__)

# Kickoff-level retry settings
MAX_KICKOFF_RETRIES = 3
RETRY_BASE_DELAY = 5  # seconds

_RETRYABLE_KEYWORDS = (
    "Too many connections", "429", "502", "503", "504",
    "rate_limit", "quota", "timeout", "Connection",
    "bad_response_status_code", "pre_consume_token_quota_failed",
)


class BaseAgent(ABC):
    """Base class for all game design team agents.

    Each agent represents a specific role in the game design team,
    with its own expertise, goals, and communication style defined
    in a YAML configuration file.
    """

    # Subclasses must define their role name
    role_name: str = ""

    def __init__(self, llm: Any | None = None, config_overrides: dict | None = None) -> None:
        """Initialize the agent with its role configuration.

        Args:
            llm: Optional LLM instance to use. If not provided,
                 will use the default from CrewAI.
            config_overrides: Optional dict to override role config values.
        """
        if not self.role_name:
            raise ValueError("Subclass must define role_name")

        self._config = load_role_config(self.role_name)
        if config_overrides:
            self._config.update(config_overrides)
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

    # Patterns indicating a malformed tool-call response from the LLM
    _TOOL_CALL_PATTERNS = re.compile(
        r"ChatCompletionMessageFunctionToolCall|"
        r"no_tool_available|"
        r"Function\(arguments=|"
        r"\bToolCall\(",
        re.IGNORECASE,
    )

    def _sanitize_response(self, raw: str) -> str | None:
        """Check if the response is a valid text response.

        Returns the response as-is if valid, or None if it looks like
        a raw tool-call object that leaked through CrewAI.
        """
        if not raw or not raw.strip():
            return None
        if self._TOOL_CALL_PATTERNS.search(raw):
            logger.warning(
                "%s returned a tool-call object instead of text: %.120s",
                self.role,
                raw,
            )
            return None
        return raw.strip()

    def respond_sync(self, context: str, *, _retried: bool = False) -> str:
        """Synchronously generate a response to the given context.

        Creates a temporary Crew with a single task and runs it synchronously.
        If the LLM returns a malformed tool-call response, retries once.
        On retryable API errors (rate limit, connection, 5xx), retries with
        exponential backoff up to MAX_KICKOFF_RETRIES times.

        Args:
            context: The discussion context to respond to.

        Returns:
            The agent's response as a string.
        """
        task = Task(
            description=self._build_response_prompt(context),
            expected_output=f"{self.role}对讨论内容的专业分析和建议，纯文本回复",
            agent=self.build_agent(),
        )

        crew = Crew(
            agents=[self.build_agent()],
            tasks=[task],
            process=Process.sequential,
        )

        last_error: Exception | None = None
        for attempt in range(MAX_KICKOFF_RETRIES):
            try:
                result = crew.kickoff()
                text = self._sanitize_response(str(result))

                if text is None and not _retried:
                    logger.info("Retrying %s response due to malformed output", self.role)
                    return self.respond_sync(context, _retried=True)

                return text or f"（{self.role}暂时无法给出回复）"
            except Exception as e:
                error_msg = str(e)
                is_retryable = any(k in error_msg for k in _RETRYABLE_KEYWORDS)
                if not is_retryable or attempt == MAX_KICKOFF_RETRIES - 1:
                    raise
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "Agent %s kickoff attempt %d/%d failed, retrying in %ds: %s",
                    self.role, attempt + 1, MAX_KICKOFF_RETRIES, delay, error_msg[:120],
                )
                time.sleep(delay)
                last_error = e

        raise last_error  # type: ignore[misc]

    async def respond_async(self, context: str, *, _retried: bool = False) -> str:
        """Asynchronously generate a response to the given context.

        This method creates a temporary Crew with a single task to generate
        a response based on the discussion context.  On retryable API errors,
        retries with exponential backoff.

        Args:
            context: The discussion context to respond to.

        Returns:
            The agent's response as a string.
        """
        task = Task(
            description=self._build_response_prompt(context),
            expected_output=f"{self.role}对讨论内容的专业分析和建议，纯文本回复",
            agent=self.build_agent(),
        )

        crew = Crew(
            agents=[self.build_agent()],
            tasks=[task],
            process=Process.sequential,
        )

        last_error: Exception | None = None
        for attempt in range(MAX_KICKOFF_RETRIES):
            try:
                result = await crew.kickoff_async()
                text = self._sanitize_response(str(result))

                if text is None and not _retried:
                    logger.info("Retrying %s async response due to malformed output", self.role)
                    return await self.respond_async(context, _retried=True)

                return text or f"（{self.role}暂时无法给出回复）"
            except Exception as e:
                error_msg = str(e)
                is_retryable = any(k in error_msg for k in _RETRYABLE_KEYWORDS)
                if not is_retryable or attempt == MAX_KICKOFF_RETRIES - 1:
                    raise
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "Agent %s async kickoff attempt %d/%d failed, retrying in %ds: %s",
                    self.role, attempt + 1, MAX_KICKOFF_RETRIES, delay, error_msg[:120],
                )
                await asyncio.sleep(delay)
                last_error = e

        raise last_error  # type: ignore[misc]

    def __repr__(self) -> str:
        """Return string representation of the agent."""
        return f"<{self.__class__.__name__}(role='{self.role}')>"
