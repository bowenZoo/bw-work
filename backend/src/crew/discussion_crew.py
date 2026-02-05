"""Discussion Crew - Orchestrates multi-agent design discussions."""

import logging
import threading
import time
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from crewai import Crew, Process, Task
from crewai.tasks.task_output import TaskOutput

from src.agents import NumberDesigner, PlayerAdvocate, SystemDesigner
from src.api.websocket.events import (
    AgentStatus,
    create_error_event,
    create_message_event,
    create_status_event,
)
from src.api.websocket.manager import broadcast_sync
from src.memory.base import Discussion, Message
from src.memory.decision_tracker import DecisionTracker
from src.memory.discussion_memory import DiscussionMemory
from src.monitoring.langfuse_client import create_trace

logger = logging.getLogger(__name__)


class DiscussionState(str, Enum):
    """State of a discussion for pause/resume functionality."""

    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"


# Global registry for discussion states and injected messages
# Key: discussion_id, Value: dict with state and injected messages
_discussion_states: dict[str, dict] = {}
_state_lock = threading.Lock()


def get_discussion_state(discussion_id: str) -> dict | None:
    """Get the state of a discussion.

    Args:
        discussion_id: The discussion ID.

    Returns:
        Discussion state dict or None if not found.
    """
    with _state_lock:
        return _discussion_states.get(discussion_id)


def set_discussion_state(discussion_id: str, state: DiscussionState) -> None:
    """Set the state of a discussion.

    Args:
        discussion_id: The discussion ID.
        state: The new state.
    """
    with _state_lock:
        if discussion_id not in _discussion_states:
            _discussion_states[discussion_id] = {
                "state": state,
                "injected_messages": [],
                "current_task_index": 0,
            }
        else:
            _discussion_states[discussion_id]["state"] = state


def add_injected_message(discussion_id: str, message: dict) -> None:
    """Add an injected message to a discussion.

    Args:
        discussion_id: The discussion ID.
        message: The message to inject.
    """
    with _state_lock:
        if discussion_id in _discussion_states:
            _discussion_states[discussion_id]["injected_messages"].append(message)


def get_and_clear_injected_messages(discussion_id: str) -> list[dict]:
    """Get and clear injected messages for a discussion.

    Args:
        discussion_id: The discussion ID.

    Returns:
        List of injected messages.
    """
    with _state_lock:
        if discussion_id in _discussion_states:
            messages = _discussion_states[discussion_id]["injected_messages"]
            _discussion_states[discussion_id]["injected_messages"] = []
            return messages
        return []


def cleanup_discussion_state(discussion_id: str) -> None:
    """Clean up discussion state when finished.

    Args:
        discussion_id: The discussion ID.
    """
    with _state_lock:
        if discussion_id in _discussion_states:
            del _discussion_states[discussion_id]


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
        self._task_agent_roles: list[str] = []
        self._task_index = 0

        # Pause/resume state
        self._pause_check_interval = 0.5  # seconds
        self._pause_timeout = 30 * 60  # 30 minutes auto-finish timeout

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

    def _reset_task_sequence(self) -> None:
        """Reset the task sequence tracking for status updates."""
        self._task_agent_roles = []
        self._task_index = 0

    def _check_pause_and_wait(self) -> list[dict]:
        """Check if discussion is paused and wait if so.

        This method blocks until the discussion is resumed or times out.
        It's called between agent turns to allow human intervention.

        Returns:
            List of injected messages to incorporate into the discussion.
        """
        state_info = get_discussion_state(self._discussion_id)
        if state_info is None:
            return []

        if state_info["state"] != DiscussionState.PAUSED:
            return []

        # Broadcast pause status
        self._broadcast_discussion_event("discussion_paused")

        # Wait for resume or timeout
        start_time = time.time()
        while True:
            state_info = get_discussion_state(self._discussion_id)
            if state_info is None:
                break

            if state_info["state"] == DiscussionState.RUNNING:
                # Resumed - get injected messages
                injected = get_and_clear_injected_messages(self._discussion_id)
                self._broadcast_discussion_event("discussion_resumed")
                return injected

            if state_info["state"] == DiscussionState.FINISHED:
                # Manually finished while paused
                break

            # Check timeout
            if time.time() - start_time > self._pause_timeout:
                logger.warning(
                    "Discussion %s paused timeout, auto-finishing",
                    self._discussion_id,
                )
                set_discussion_state(self._discussion_id, DiscussionState.FINISHED)
                break

            time.sleep(self._pause_check_interval)

        return []

    def _inject_user_messages(self, messages: list[dict]) -> None:
        """Inject user messages into the discussion context.

        Args:
            messages: List of injected message dicts.
        """
        for msg in messages:
            # Record to memory
            self._record_message(
                agent_role="User",
                content=msg.get("content", ""),
            )
            # Broadcast the user message
            self._broadcast_message(
                agent_role="User",
                content=msg.get("content", ""),
            )

    def request_pause(self) -> bool:
        """Request to pause the discussion.

        Returns:
            True if pause request was accepted.
        """
        state_info = get_discussion_state(self._discussion_id)
        if state_info is None:
            # Initialize state if not exists
            set_discussion_state(self._discussion_id, DiscussionState.PAUSED)
            return True

        if state_info["state"] == DiscussionState.RUNNING:
            set_discussion_state(self._discussion_id, DiscussionState.PAUSED)
            return True

        return False

    def request_resume(self) -> bool:
        """Request to resume the discussion.

        Returns:
            True if resume request was accepted.
        """
        state_info = get_discussion_state(self._discussion_id)
        if state_info is None:
            return False

        if state_info["state"] == DiscussionState.PAUSED:
            set_discussion_state(self._discussion_id, DiscussionState.RUNNING)
            return True

        return False

    def inject_message(self, content: str) -> bool:
        """Inject a user message into the discussion.

        Args:
            content: The message content.

        Returns:
            True if injection was successful.
        """
        state_info = get_discussion_state(self._discussion_id)
        if state_info is None:
            return False

        message = {
            "role": "user",
            "content": content,
            "source": "intervention",
            "timestamp": datetime.now().isoformat(),
            "save_to_memory": True,
        }
        add_injected_message(self._discussion_id, message)
        return True

    def is_paused(self) -> bool:
        """Check if the discussion is paused.

        Returns:
            True if paused.
        """
        state_info = get_discussion_state(self._discussion_id)
        if state_info is None:
            return False
        return state_info["state"] == DiscussionState.PAUSED

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
        self._reset_task_sequence()

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
                self._task_agent_roles.append(agent.role)

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
        self._task_agent_roles.append(system_agent.role)

        return tasks

    def _broadcast_status(
        self,
        agent_role: str,
        status: AgentStatus,
        content: str | None = None,
    ) -> None:
        """Broadcast agent status change via WebSocket.

        Args:
            agent_role: The agent's role name.
            status: The new agent status.
            content: Optional status message.
        """
        if self._discussion_id is None:
            return

        try:
            event = create_status_event(
                discussion_id=self._discussion_id,
                agent_id=agent_role.lower().replace(" ", "_"),
                agent_role=agent_role,
                status=status,
                content=content,
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

    def _broadcast_discussion_event(self, content: str) -> None:
        """Broadcast a discussion-level event via WebSocket."""
        if self._discussion_id is None:
            return

        try:
            event = create_status_event(
                discussion_id=self._discussion_id,
                agent_id="discussion",
                agent_role="discussion",
                status=AgentStatus.IDLE,
                content=content,
            )
            broadcast_sync(self._discussion_id, event.to_dict())
        except Exception as exc:
            logger.debug("Failed to broadcast discussion event: %s", exc)

    def _broadcast_error(self, content: str) -> None:
        """Broadcast an error event via WebSocket."""
        if self._discussion_id is None:
            return

        try:
            event = create_error_event(
                discussion_id=self._discussion_id,
                content=content,
            )
            broadcast_sync(self._discussion_id, event.to_dict())
        except Exception as exc:
            logger.debug("Failed to broadcast error event: %s", exc)

    def _build_task_callback(
        self,
        trace_span: Any | None,
    ) -> Callable[[TaskOutput], None]:
        """Create a task callback that forwards output and records tracing spans."""

        def _callback(task_output: TaskOutput) -> None:
            agent_role = str(task_output.agent) if task_output.agent else "Unknown"

            # Broadcast status change: speaking -> idle
            self._broadcast_status(agent_role, AgentStatus.SPEAKING)
            self._broadcast_message(agent_role, str(task_output))
            self._broadcast_status(agent_role, AgentStatus.IDLE)

            # Record message to memory
            self._record_message(agent_role, str(task_output))

            # Check for pause between agent turns (intervention checkpoint)
            injected_messages = self._check_pause_and_wait()
            if injected_messages:
                self._inject_user_messages(injected_messages)

            # Broadcast thinking status for next agent, if any
            self._task_index += 1
            if self._task_index < len(self._task_agent_roles):
                next_role = self._task_agent_roles[self._task_index]
                self._broadcast_status(next_role, AgentStatus.THINKING)

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
        """Create a root trace span and task callback.

        Uses discussion_id as session_id to enable cost tracking and
        trace aggregation per discussion.
        """
        trace_span = create_trace(
            name="discussion",
            session_id=self._discussion_id,  # Enable per-discussion cost tracking
            metadata={
                "topic": topic,
                "rounds": rounds,
                "agents": [agent.role for agent in self._agents],
                "discussion_id": self._discussion_id,
                "project_id": self._project_id,
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

        # Initialize discussion state for pause/resume
        set_discussion_state(self._discussion_id, DiscussionState.RUNNING)

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

            # Mark discussion as finished and clean up
            set_discussion_state(self._discussion_id, DiscussionState.FINISHED)
            cleanup_discussion_state(self._discussion_id)

            # Broadcast completion status for all agents
            for agent in self._agents:
                self._broadcast_status(agent.role, AgentStatus.IDLE)
            self._broadcast_discussion_event("discussion_completed")

            return str(result)
        except Exception as exc:
            self._finalize_trace(trace_span, error=exc)
            self._broadcast_error(str(exc))
            self._broadcast_discussion_event("discussion_failed")
            # Save discussion even on error (without summary)
            self._save_discussion()
            # Clean up discussion state
            cleanup_discussion_state(self._discussion_id)
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

        # Initialize discussion state for pause/resume
        set_discussion_state(self._discussion_id, DiscussionState.RUNNING)

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

            # Mark discussion as finished and clean up
            set_discussion_state(self._discussion_id, DiscussionState.FINISHED)
            cleanup_discussion_state(self._discussion_id)

            # Broadcast completion status for all agents
            for agent in self._agents:
                self._broadcast_status(agent.role, AgentStatus.IDLE)
            self._broadcast_discussion_event("discussion_completed")

            return str(result)
        except Exception as exc:
            self._finalize_trace(trace_span, error=exc)
            self._broadcast_error(str(exc))
            self._broadcast_discussion_event("discussion_failed")
            # Save discussion even on error (without summary)
            self._save_discussion()
            # Clean up discussion state
            cleanup_discussion_state(self._discussion_id)
            # Broadcast idle status on error
            for agent in self._agents:
                self._broadcast_status(agent.role, AgentStatus.IDLE)
            raise
