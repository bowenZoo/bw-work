"""Summarizer Agent - Generates structured discussion summaries."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from crewai import Agent, Task

from src.agents.base import BaseAgent
from src.memory.base import Discussion


@dataclass
class DiscussionSummary:
    """Structured discussion summary."""

    discussion_id: str
    topic: str
    key_points: list[str]
    agreements: list[str]
    disagreements: list[str]
    open_questions: list[str]
    next_steps: list[str]
    generated_at: datetime
    raw_summary: str


class Summarizer(BaseAgent):
    """Summarizer agent for generating structured discussion summaries.

    The Summarizer focuses on:
    - Extracting key points from discussions
    - Identifying areas of agreement and disagreement
    - Highlighting open questions
    - Suggesting next steps
    """

    role_name = "summarizer"

    def __init__(self, llm: Any | None = None) -> None:
        """Initialize the Summarizer agent.

        Unlike other agents that load from YAML config, the Summarizer
        has a fixed configuration for generating summaries.

        Args:
            llm: Optional LLM instance to use.
        """
        self._llm = llm
        self._agent: Agent | None = None
        # Fixed configuration for summarizer
        self._config = {
            "role": "Discussion Summarizer",
            "goal": "Generate clear, structured summaries of design discussions that capture key decisions, disagreements, and action items",
            "backstory": """You are an expert at analyzing complex discussions and extracting
            the most important information. You excel at identifying consensus, disagreements,
            and open questions. Your summaries help teams quickly understand what was discussed
            and what needs to happen next.""",
            "focus_areas": [
                "Key decision points",
                "Areas of agreement",
                "Points of disagreement",
                "Unresolved questions",
                "Action items and next steps",
            ],
        }

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

    def get_tools(self) -> list[Any]:
        """Get tools available to the Summarizer.

        Returns:
            Empty list (no tools needed for summarization).
        """
        return []

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
                "verbose": False,
                "allow_delegation": False,
                "max_iter": 10,
            }

            if self._llm is not None:
                agent_kwargs["llm"] = self._llm

            self._agent = Agent(**agent_kwargs)

        return self._agent

    def create_summary_task(self, discussion: Discussion) -> Task:
        """Create a task for summarizing a discussion.

        Args:
            discussion: The discussion to summarize.

        Returns:
            CrewAI Task for generating the summary.
        """
        # Format messages for context
        messages_text = "\n\n".join(
            f"**{msg.agent_role}**: {msg.content}" for msg in discussion.messages
        )

        description = f"""
Please analyze the following discussion and generate a structured summary.

**Discussion Topic**: {discussion.topic}

**Discussion Content**:
{messages_text}

Generate a comprehensive summary that includes:

1. **Key Points**: The main ideas and proposals discussed
2. **Agreements**: Points where participants reached consensus
3. **Disagreements**: Points of contention or differing opinions
4. **Open Questions**: Issues that remain unresolved
5. **Next Steps**: Recommended actions to move forward

Format your response as a structured summary with clear sections.
Use bullet points for lists within each section.
"""

        expected_output = """A structured summary with the following sections:
- Key Points (bullet list)
- Agreements (bullet list)
- Disagreements (bullet list)
- Open Questions (bullet list)
- Next Steps (bullet list)"""

        return Task(
            name=f"summarize-{discussion.id}",
            description=description,
            expected_output=expected_output,
            agent=self.build_agent(),
        )

    def parse_summary(self, raw_summary: str, discussion: Discussion) -> DiscussionSummary:
        """Parse raw summary text into structured format.

        Args:
            raw_summary: The raw summary text from the agent.
            discussion: The original discussion.

        Returns:
            Structured DiscussionSummary object.
        """
        # Simple parsing - extract sections based on headers
        sections = {
            "key_points": [],
            "agreements": [],
            "disagreements": [],
            "open_questions": [],
            "next_steps": [],
        }

        current_section = None
        for line in raw_summary.split("\n"):
            line = line.strip()
            if not line:
                continue

            line_lower = line.lower()

            # Detect section headers
            if "key point" in line_lower:
                current_section = "key_points"
            elif "agreement" in line_lower:
                current_section = "agreements"
            elif "disagreement" in line_lower:
                current_section = "disagreements"
            elif "open question" in line_lower or "unresolved" in line_lower:
                current_section = "open_questions"
            elif "next step" in line_lower or "action" in line_lower:
                current_section = "next_steps"
            elif current_section and (line.startswith("-") or line.startswith("*") or line.startswith("+")):
                # Extract bullet point content
                content = line.lstrip("-*+ ").strip()
                if content:
                    sections[current_section].append(content)

        return DiscussionSummary(
            discussion_id=discussion.id,
            topic=discussion.topic,
            key_points=sections["key_points"],
            agreements=sections["agreements"],
            disagreements=sections["disagreements"],
            open_questions=sections["open_questions"],
            next_steps=sections["next_steps"],
            generated_at=datetime.now(),
            raw_summary=raw_summary,
        )

    def __repr__(self) -> str:
        """Return string representation of the agent."""
        return f"<Summarizer(role='{self.role}')>"
