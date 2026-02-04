"""Discussion Crew - Orchestrates multi-agent design discussions."""

import logging
from datetime import datetime
from typing import Any, Callable
from uuid import uuid4

from crewai import Crew, Process, Task
from crewai.tasks.task_output import TaskOutput

from src.agents import NumberDesigner, PlayerAdvocate, SystemDesigner
from src.api.websocket.events import (
    AgentStatus,
    create_message_event,
    create_status_event,
)
from src.api.websocket.manager import broadcast_sync
from src.memory.base import Discussion, Message
from src.memory.decision_tracker import DecisionTracker
from src.memory.discussion_memory import DiscussionMemory
from src.monitoring.langfuse_client import create_trace

logger = logging.getLogger(__name__)


class DiscussionCrew:
    """Orchestrates design discussions between game design team agents.

    The DiscussionCrew manages multi-round discussions where each agent
    contributes their expertise to analyze and design game features.
    """

    def __init__(
        self,
        llm: Any | None = None,
        callback: Callable[[str, str], None] | None = None,
        discussion_id: str | None = None,
        project_id: str | None = None,
        data_dir: str = "data/projects",
    ) -> None:
        """Initialize the discussion crew.

        Args:
            llm: Optional LLM instance to use for all agents.
            callback: Optional callback function called with (agent_role, message)
                     when an agent produces output.
            discussion_id: Optional discussion ID for WebSocket broadcasting.
            project_id: Optional project ID for memory storage.
            data_dir: Data directory for memory storage.
        """
        self._llm = llm
        self._callback = callback
        self._discussion_id = discussion_id or str(uuid4())
        self._project_id = project_id or "default"
        self._data_dir = data_dir

        # Initialize agents
        self._system_designer = SystemDesigner(llm=llm)
        self._number_designer = NumberDesigner(llm=llm)
        self._player_advocate = PlayerAdvocate(llm=llm)

        self._agents = [
            self._system_designer,
            self._number_designer,
            self._player_advocate,
        ]

        # Initialize memory systems
        self._discussion_memory = DiscussionMemory(data_dir=data_dir)
        self._decision_tracker = DecisionTracker(data_dir=data_dir)

        # Current discussion record
        self._current_discussion: Discussion | None = None
        self._messages: list[Message] = []

    @property
    def agents(self) -> list[Any]:
        """Get all agents in the crew."""
        return self._agents

    @property
    def discussion_id(self) -> str:
        """Get the current discussion ID."""
        return self._discussion_id

    @property
    def project_id(self) -> str:
        """Get the project ID."""
        return self._project_id

    def _load_history_context(self, topic: str) -> str:
        """Load historical context related to the topic.

        Args:
            topic: The discussion topic.

        Returns:
            Formatted historical context string.
        """
        context_parts = []

        # Search for related past discussions
        related_discussions = self._discussion_memory.search(topic, limit=3)
        if related_discussions:
            context_parts.append("## 相关历史讨论\n")
            for disc in related_discussions:
                context_parts.append(f"### {disc.topic}")
                if disc.summary:
                    context_parts.append(f"总结: {disc.summary}\n")
                context_parts.append("")

        # Search for related decisions
        related_decisions = self._decision_tracker.search(topic, limit=5, project_id=self._project_id)
        if related_decisions:
            context_parts.append("## 相关历史决策\n")
            for decision in related_decisions:
                context_parts.append(f"- **{decision.title}**: {decision.description}")
                context_parts.append(f"  原因: {decision.rationale}\n")

        return "\n".join(context_parts) if context_parts else ""

    def _init_discussion(self, topic: str) -> Discussion:
        """Initialize a new discussion record.

        Args:
            topic: The discussion topic.

        Returns:
            The created Discussion object.
        """
        discussion = Discussion(
            id=self._discussion_id,
            project_id=self._project_id,
            topic=topic,
            messages=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        self._current_discussion = discussion
        self._messages = []
        return discussion

    def _record_message(self, agent_role: str, content: str) -> None:
        """Record a message from an agent.

        Args:
            agent_role: The agent's role.
            content: The message content.
        """
        message = Message(
            id=str(uuid4()),
            agent_id=agent_role.lower().replace(" ", "_"),
            agent_role=agent_role,
            content=content,
            timestamp=datetime.now(),
        )
        self._messages.append(message)

    def _save_discussion(self, summary: str | None = None) -> None:
        """Save the current discussion to memory.

        Args:
            summary: Optional discussion summary.
        """
        if self._current_discussion is None:
            return

        self._current_discussion.messages = self._messages
        self._current_discussion.summary = summary
        self._current_discussion.updated_at = datetime.now()

        self._discussion_memory.save(self._current_discussion)
        logger.info(
            "Discussion saved: %s (%d messages)",
            self._current_discussion.id,
            len(self._messages),
        )

    def get_historical_decisions(self, limit: int = 10) -> list[Any]:
        """Get historical decisions for the current project.

        Args:
            limit: Maximum number of decisions to return.

        Returns:
            List of Decision objects.
        """
        return self._decision_tracker.list_all(
            project_id=self._project_id,
            limit=limit,
        )

    def create_discussion_tasks(
        self,
        topic: str,
        rounds: int = 3,
    ) -> list[Task]:
        """Create discussion tasks for the given topic.

        Args:
            topic: The design topic to discuss.
            rounds: Number of discussion rounds.

        Returns:
            List of CrewAI Task objects.
        """
        tasks = []

        # Load historical context
        history_context = self._load_history_context(topic)
        history_section = ""
        if history_context:
            history_section = f"\n\n---\n参考历史信息：\n{history_context}\n---\n"

        # Build CrewAI agents
        system_agent = self._system_designer.build_agent()
        number_agent = self._number_designer.build_agent()
        player_agent = self._player_advocate.build_agent()

        agent_sequence = [system_agent, number_agent, player_agent]

        for round_num in range(1, rounds + 1):
            for i, agent in enumerate(agent_sequence):
                # Determine context from previous tasks
                context_tasks = tasks[-3:] if tasks else []

                if round_num == 1 and i == 0:
                    # First speaker starts the discussion
                    description = f"""
作为{agent.role}，请针对以下话题发表你的初步看法和设计建议：

话题：{topic}
{history_section}
请从你的专业角度出发，提出你认为重要的设计考虑点。
输出应该包含：
1. 你对这个话题的理解
2. 你认为需要关注的关键点
3. 你的初步设计建议
"""
                else:
                    # Subsequent speakers respond to previous discussion
                    description = f"""
作为{agent.role}，请基于之前的讨论内容，继续发表你的观点。

话题：{topic}
当前轮次：第{round_num}轮

请：
1. 回应之前发言者提出的观点（同意、补充或提出不同看法）
2. 从你的专业角度补充新的考虑点
3. 如果有分歧，尝试提出平衡各方需求的方案
"""

                expected_output = f"{agent.role}对'{topic}'的专业分析和建议"

                task_name = f"round-{round_num}-{agent.role}"
                task = Task(
                    name=task_name,
                    description=description,
                    expected_output=expected_output,
                    agent=agent,
                    context=context_tasks if context_tasks else None,
                )
                tasks.append(task)

        # Final summary task
        summary_task = Task(
            name="summary",
            description=f"""
请综合所有讨论内容，为话题'{topic}'生成一份讨论总结：

1. 主要共识点
2. 存在的分歧及各方观点
3. 待进一步讨论的问题
4. 建议的下一步行动

请以结构化的方式输出总结。
""",
            expected_output="讨论总结文档",
            agent=system_agent,
            context=tasks[-6:],  # Use last 6 tasks as context
        )
        tasks.append(summary_task)

        return tasks

    def _broadcast_status(self, agent_role: str, status: AgentStatus) -> None:
        """Broadcast agent status change via WebSocket.

        Args:
            agent_role: The agent's role name.
            status: The new agent status.
        """
        if self._discussion_id is None:
            return

        try:
            event = create_status_event(
                discussion_id=self._discussion_id,
                agent_id=agent_role.lower().replace(" ", "_"),
                agent_role=agent_role,
                status=status,
            )
            broadcast_sync(self._discussion_id, event.to_dict())
        except Exception as exc:
            logger.debug("Failed to broadcast status: %s", exc)

    def _broadcast_message(self, agent_role: str, content: str) -> None:
        """Broadcast agent message via WebSocket.

        Args:
            agent_role: The agent's role name.
            content: The message content.
        """
        if self._discussion_id is None:
            return

        try:
            event = create_message_event(
                discussion_id=self._discussion_id,
                agent_id=agent_role.lower().replace(" ", "_"),
                agent_role=agent_role,
                content=content,
            )
            broadcast_sync(self._discussion_id, event.to_dict())
        except Exception as exc:
            logger.debug("Failed to broadcast message: %s", exc)

    def _build_task_callback(
        self,
        trace_span: Any | None,
    ) -> Callable[[TaskOutput], None]:
        """Create a task callback that forwards output and records tracing spans."""

        def _callback(task_output: TaskOutput) -> None:
            agent_role = str(task_output.agent) if task_output.agent else "Unknown"

            # Broadcast status change: speaking -> idle
            self._broadcast_status(agent_role, AgentStatus.IDLE)

            # Broadcast the message content
            self._broadcast_message(agent_role, str(task_output))

            # Record message to memory
            self._record_message(agent_role, str(task_output))

            if self._callback is not None:
                try:
                    self._callback(task_output.agent, str(task_output))
                except Exception as exc:
                    logger.warning("Task callback failed: %s", exc)

            if trace_span is None:
                return

            try:
                span_name = task_output.name or f"task:{task_output.agent}"
                span = trace_span.start_span(
                    name=span_name,
                    input={
                        "description": task_output.description,
                        "expected_output": task_output.expected_output,
                    },
                    metadata={
                        "agent": task_output.agent,
                        "output_format": str(task_output.output_format),
                    },
                )
                span.update(output=task_output.raw)
                span.end()
            except Exception as exc:
                logger.debug("Failed to record Langfuse span: %s", exc)

        return _callback

    def _prepare_trace(
        self,
        topic: str,
        rounds: int,
    ) -> tuple[Any | None, Callable[[TaskOutput], None]]:
        """Create a root trace span and task callback."""
        trace_span = create_trace(
            name="discussion",
            metadata={
                "topic": topic,
                "rounds": rounds,
                "agents": [agent.role for agent in self._agents],
            },
        )
        return trace_span, self._build_task_callback(trace_span)

    def _finalize_trace(
        self,
        trace_span: Any | None,
        *,
        result: Any | None = None,
        error: Exception | None = None,
    ) -> None:
        """Update and end the trace span."""
        if trace_span is None:
            return
        try:
            if error is not None:
                trace_span.update(
                    level="ERROR",
                    status_message=str(error),
                    metadata={"error": str(error)},
                )
            elif result is not None:
                trace_span.update(output=str(result))
            trace_span.end()
        except Exception as exc:
            logger.debug("Failed to finalize Langfuse trace: %s", exc)

    def run(
        self,
        topic: str,
        rounds: int = 3,
        verbose: bool = True,
    ) -> str:
        """Run a design discussion on the given topic.

        Args:
            topic: The design topic to discuss.
            rounds: Number of discussion rounds (default: 3).
            verbose: Whether to print verbose output (default: True).

        Returns:
            The final discussion result/summary.
        """
        # Initialize discussion record
        self._init_discussion(topic)

        tasks = self.create_discussion_tasks(topic, rounds)
        trace_span, task_callback = self._prepare_trace(topic, rounds)

        # Broadcast initial thinking status for first agent
        if self._agents:
            first_agent = self._agents[0]
            self._broadcast_status(first_agent.role, AgentStatus.THINKING)

        try:
            crew = Crew(
                agents=[agent.build_agent() for agent in self._agents],
                tasks=tasks,
                process=Process.sequential,
                verbose=verbose,
                task_callback=task_callback,
            )

            result = crew.kickoff()
            self._finalize_trace(trace_span, result=result)

            # Save discussion to memory with summary
            self._save_discussion(summary=str(result))

            # Broadcast completion status for all agents
            for agent in self._agents:
                self._broadcast_status(agent.role, AgentStatus.IDLE)

            return str(result)
        except Exception as exc:
            self._finalize_trace(trace_span, error=exc)
            # Save discussion even on error (without summary)
            self._save_discussion()
            # Broadcast idle status on error
            for agent in self._agents:
                self._broadcast_status(agent.role, AgentStatus.IDLE)
            raise

    async def run_async(
        self,
        topic: str,
        rounds: int = 3,
        verbose: bool = True,
    ) -> str:
        """Run a design discussion asynchronously.

        Args:
            topic: The design topic to discuss.
            rounds: Number of discussion rounds (default: 3).
            verbose: Whether to print verbose output (default: True).

        Returns:
            The final discussion result/summary.
        """
        # Initialize discussion record
        self._init_discussion(topic)

        tasks = self.create_discussion_tasks(topic, rounds)
        trace_span, task_callback = self._prepare_trace(topic, rounds)

        # Broadcast initial thinking status for first agent
        if self._agents:
            first_agent = self._agents[0]
            self._broadcast_status(first_agent.role, AgentStatus.THINKING)

        try:
            crew = Crew(
                agents=[agent.build_agent() for agent in self._agents],
                tasks=tasks,
                process=Process.sequential,
                verbose=verbose,
                task_callback=task_callback,
            )

            result = await crew.kickoff_async()
            self._finalize_trace(trace_span, result=result)

            # Save discussion to memory with summary
            self._save_discussion(summary=str(result))

            # Broadcast completion status for all agents
            for agent in self._agents:
                self._broadcast_status(agent.role, AgentStatus.IDLE)

            return str(result)
        except Exception as exc:
            self._finalize_trace(trace_span, error=exc)
            # Save discussion even on error (without summary)
            self._save_discussion()
            # Broadcast idle status on error
            for agent in self._agents:
                self._broadcast_status(agent.role, AgentStatus.IDLE)
            raise
