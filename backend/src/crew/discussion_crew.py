"""Discussion Crew - Orchestrates multi-agent design discussions."""

import json
import logging
import os
import threading
import time
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from crewai import Crew, Process, Task
from crewai.tasks.task_output import TaskOutput

from src.agents import LeadPlanner, NumberDesigner, PlayerAdvocate, SystemDesigner, VisualConceptAgent
import asyncio

from src.agents.lead_planner import (
    DecisionPoint,
    DiscussionStatus,
    VisualConceptRequest,
    parse_agenda_output,
    parse_discussion_status,
    parse_final_decisions,
    parse_visual_requirements,
)
from src.models.agenda import Agenda, AgendaItem, AgendaItemStatus, AgendaSummaryDetails
from src.crew.mention_parser import parse_mentioned_roles
from src.memory.base import Decision
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
from src.monitoring.langfuse_client import get_langfuse_client, start_trace_context

logger = logging.getLogger(__name__)


class DiscussionState(str, Enum):
    """State of a discussion for pause/resume functionality."""

    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"


class DiscussionTimeoutError(RuntimeError):
    """Raised when a discussion times out while paused."""


# Global registry for discussion states and injected messages
# Key: discussion_id, Value: dict with state and injected messages
_discussion_states: dict[str, dict] = {}
_state_lock = threading.Lock()
_STATE_DIR = Path(os.environ.get("DISCUSSION_STATE_DIR", "data/projects/.intervention_state"))


def _state_path(discussion_id: str) -> Path:
    return _STATE_DIR / f"{discussion_id}.json"


def _serialize_state(state_info: dict) -> dict:
    state = state_info.get("state")
    if isinstance(state, DiscussionState):
        state_value = state.value
    else:
        state_value = str(state) if state is not None else DiscussionState.RUNNING.value
    return {
        "state": state_value,
        "injected_messages": state_info.get("injected_messages", []),
        "current_task_index": state_info.get("current_task_index", 0),
    }


def _persist_state(discussion_id: str, state_info: dict) -> None:
    try:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        _state_path(discussion_id).write_text(
            json.dumps(_serialize_state(state_info), ensure_ascii=True),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.debug("Failed to persist discussion state: %s", exc)


def _load_state_from_disk(discussion_id: str) -> dict | None:
    path = _state_path(discussion_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        state_value = data.get("state", DiscussionState.RUNNING.value)
        return {
            "state": DiscussionState(state_value),
            "injected_messages": data.get("injected_messages", []),
            "current_task_index": data.get("current_task_index", 0),
        }
    except Exception as exc:
        logger.debug("Failed to load discussion state: %s", exc)
        return None


def get_discussion_state(discussion_id: str) -> dict | None:
    """Get the state of a discussion.

    Args:
        discussion_id: The discussion ID.

    Returns:
        Discussion state dict or None if not found.
    """
    with _state_lock:
        state = _discussion_states.get(discussion_id)
        if state is None:
            loaded = _load_state_from_disk(discussion_id)
            if loaded:
                _discussion_states[discussion_id] = loaded
                state = loaded
        return state


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
        _persist_state(discussion_id, _discussion_states[discussion_id])


def add_injected_message(discussion_id: str, message: dict) -> None:
    """Add an injected message to a discussion.

    Args:
        discussion_id: The discussion ID.
        message: The message to inject.
    """
    with _state_lock:
        if discussion_id in _discussion_states:
            _discussion_states[discussion_id]["injected_messages"].append(message)
            _persist_state(discussion_id, _discussion_states[discussion_id])


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
            _persist_state(discussion_id, _discussion_states[discussion_id])
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
    try:
        _state_path(discussion_id).unlink(missing_ok=True)
    except Exception as exc:
        logger.debug("Failed to remove discussion state file: %s", exc)


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
        enable_visual_concept: bool = False,
    ) -> None:
        """Initialize the discussion crew.

        Args:
            llm: Optional LLM instance to use for all agents.
            callback: Optional callback function called with (agent_role, message)
                     when an agent produces output.
            discussion_id: Optional discussion ID for WebSocket broadcasting.
            project_id: Optional project ID for memory storage.
            data_dir: Data directory for memory storage.
            enable_visual_concept: Whether to include the Visual Concept Agent.
        """
        self._llm = llm
        self._callback = callback
        self._discussion_id = discussion_id or str(uuid4())
        self._project_id = project_id or "default"
        self._data_dir = data_dir
        self._enable_visual_concept = enable_visual_concept

        # Initialize agents - Lead Planner is the moderator
        self._lead_planner = LeadPlanner(llm=llm)
        self._system_designer = SystemDesigner(llm=llm)
        self._number_designer = NumberDesigner(llm=llm)
        self._player_advocate = PlayerAdvocate(llm=llm)

        # Discussion agents (excluding lead planner who moderates)
        self._discussion_agents = [
            self._system_designer,
            self._number_designer,
            self._player_advocate,
        ]

        # All agents including lead planner
        self._agents = [
            self._lead_planner,
            self._system_designer,
            self._number_designer,
            self._player_advocate,
        ]

        # Optionally add Visual Concept Agent
        if enable_visual_concept:
            self._visual_concept = VisualConceptAgent(
                llm=llm,
                project_id=self._project_id,
            )
            self._agents.append(self._visual_concept)
        else:
            self._visual_concept = None

        # Initialize memory systems
        self._discussion_memory = DiscussionMemory(data_dir=data_dir)
        self._decision_tracker = DecisionTracker(data_dir=data_dir)

        # Current discussion record
        self._current_discussion: Discussion | None = None
        self._messages: list[Message] = []
        self._task_agent_roles: list[str] = []
        self._task_index = 0
        self._abort_reason: str | None = None

        # Pause/resume state
        self._pause_check_interval = 0.5  # seconds
        self._pause_timeout = 30 * 60  # 30 minutes auto-finish timeout

        # Auto-pause configuration
        self._auto_pause_interval = 5  # pause every N rounds, 0=disabled
        self._total_rounds = 0  # set during run()

        # Dynamic discussion control
        self._current_round = 0
        self._discussion_status = DiscussionStatus.CONTINUE
        self._pending_questions: list[str] = []

        # Message sequence counter for ordering parallel messages
        self._message_sequence = 0

        # Agenda management
        self._agenda: Agenda | None = None

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

    def _next_sequence(self) -> int:
        """Get the next message sequence number.

        Returns:
            The next sequence number.
        """
        self._message_sequence += 1
        return self._message_sequence

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
                self._abort_reason = "Discussion paused timeout"
                raise DiscussionTimeoutError(self._abort_reason)

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

    def _init_agenda(self, items_data: list[dict[str, str]]) -> Agenda:
        """Initialize the discussion agenda from parsed items.

        Args:
            items_data: List of dicts with 'title' and 'description'.

        Returns:
            The created Agenda object.
        """
        self._agenda = Agenda.from_items_list(items_data)
        # Start the first item
        if self._agenda.items:
            self._agenda.start_current()
        return self._agenda

    def get_agenda(self) -> Agenda | None:
        """Get the current agenda.

        Returns:
            The current Agenda or None if not initialized.
        """
        return self._agenda

    async def _generate_agenda_item_summary(
        self,
        item: AgendaItem,
        discussion_content: str,
    ) -> tuple[str, AgendaSummaryDetails]:
        """Generate a summary for a completed agenda item.

        Args:
            item: The agenda item to summarize.
            discussion_content: The discussion content for this item.

        Returns:
            Tuple of (markdown_summary, structured_details).
        """
        prompt = f"""请为以下议题生成讨论小结：

议题：{item.title}
{f"描述：{item.description}" if item.description else ""}

讨论内容：
{discussion_content}

请按以下格式输出：

# 议题小结：{item.title}

## 讨论结论
- 结论1
- 结论2

## 各方观点
- 系统策划：...
- 数值策划：...
- 玩家代言人：...

## 遗留问题
- 问题1（如有）

## 下一步行动
- 行动1
"""
        task = Task(
            description=prompt,
            expected_output="议题小结文档",
            agent=self._lead_planner.build_agent(),
        )

        crew = Crew(
            agents=[self._lead_planner.build_agent()],
            tasks=[task],
            process=Process.sequential,
        )

        result = await crew.kickoff_async()
        summary_text = str(result)

        # Parse the summary into structured details
        details = self._parse_agenda_summary(summary_text)

        return summary_text, details

    def _parse_agenda_summary(self, summary_text: str) -> AgendaSummaryDetails:
        """Parse agenda summary text into structured details.

        Args:
            summary_text: The markdown summary text.

        Returns:
            AgendaSummaryDetails with extracted information.
        """
        import re

        details = AgendaSummaryDetails()

        # Extract conclusions
        conclusions_match = re.search(
            r"##\s*讨论结论\s*\n(.*?)(?=\n##|\Z)",
            summary_text,
            re.DOTALL,
        )
        if conclusions_match:
            conclusions_text = conclusions_match.group(1)
            details.conclusions = [
                line.strip().lstrip("-").strip()
                for line in conclusions_text.strip().split("\n")
                if line.strip() and line.strip().startswith("-")
            ]

        # Extract viewpoints
        viewpoints_match = re.search(
            r"##\s*各方观点\s*\n(.*?)(?=\n##|\Z)",
            summary_text,
            re.DOTALL,
        )
        if viewpoints_match:
            viewpoints_text = viewpoints_match.group(1)
            # Match pattern: - 角色：观点
            viewpoint_pattern = r"-\s*(.+?)[：:]\s*(.+?)(?=\n-|\Z)"
            for match in re.finditer(viewpoint_pattern, viewpoints_text, re.DOTALL):
                role = match.group(1).strip()
                viewpoint = match.group(2).strip()
                details.viewpoints[role] = viewpoint

        # Extract open questions
        questions_match = re.search(
            r"##\s*遗留问题\s*\n(.*?)(?=\n##|\Z)",
            summary_text,
            re.DOTALL,
        )
        if questions_match:
            questions_text = questions_match.group(1)
            details.open_questions = [
                line.strip().lstrip("-").strip()
                for line in questions_text.strip().split("\n")
                if line.strip() and line.strip().startswith("-")
            ]

        # Extract next steps
        next_steps_match = re.search(
            r"##\s*下一步行动\s*\n(.*?)(?=\n##|\Z)",
            summary_text,
            re.DOTALL,
        )
        if next_steps_match:
            next_steps_text = next_steps_match.group(1)
            details.next_steps = [
                line.strip().lstrip("-").strip()
                for line in next_steps_text.strip().split("\n")
                if line.strip() and line.strip().startswith("-")
            ]

        return details

    async def complete_current_agenda_item(
        self,
        discussion_content: str,
    ) -> AgendaItem | None:
        """Complete the current agenda item with a generated summary.

        Args:
            discussion_content: The discussion content for this item.

        Returns:
            The completed AgendaItem or None if no current item.
        """
        if self._agenda is None or self._agenda.current_item is None:
            return None

        item = self._agenda.current_item

        # Generate summary
        self._broadcast_discussion_event(f"正在生成议题小结：{item.title}...")
        summary_text, details = await self._generate_agenda_item_summary(item, discussion_content)

        # Complete the item
        self._agenda.complete_current(summary_text, details)

        # Broadcast agenda update
        self._broadcast_agenda_event("item_complete", {
            "item_id": item.id,
            "title": item.title,
            "summary": summary_text,
        })

        # Start next item if available
        if self._agenda.current_item:
            self._agenda.start_current()
            self._broadcast_agenda_event("item_start", {
                "item_id": self._agenda.current_item.id,
                "title": self._agenda.current_item.title,
            })

        return item

    def _broadcast_agenda_event(self, event_type: str, data: dict) -> None:
        """Broadcast an agenda-related event via WebSocket.

        Args:
            event_type: Type of agenda event (e.g., 'item_start', 'item_complete').
            data: Event data dictionary.
        """
        if self._discussion_id is None:
            return

        try:
            from src.api.websocket.events import create_agenda_event
            event = create_agenda_event(
                discussion_id=self._discussion_id,
                event_type=event_type,
                data=data,
            )
            broadcast_sync(event.to_dict(), discussion_id=self._discussion_id)
        except ImportError:
            # Fallback: use generic status event
            self._broadcast_discussion_event(f"议程更新: {event_type}")
        except Exception as exc:
            logger.debug("Failed to broadcast agenda event: %s", exc)

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

    def _save_decisions(self, final_result: str, topic: str) -> list[str]:
        """Extract and save decisions from the final result.

        Args:
            final_result: The final decision document from Lead Planner.
            topic: The discussion topic.

        Returns:
            List of saved decision IDs.
        """
        decision_points = parse_final_decisions(final_result)
        saved_ids: list[str] = []

        for point in decision_points:
            # Build description with alternatives if any
            description = point.decision
            if point.alternatives:
                alt_text = "\n".join(f"- {alt}" for alt in point.alternatives)
                description += f"\n\n考虑过的替代方案：\n{alt_text}"
            if point.related_discussion:
                description += f"\n\n相关讨论：{point.related_discussion}"

            decision = Decision(
                id="",  # Will be generated by tracker
                discussion_id=self._discussion_id,
                title=f"[{topic}] {point.title}",
                description=description,
                rationale=point.rationale,
                made_by="主策划",
                created_at=datetime.now(),
            )

            decision_id = self._decision_tracker.save(decision, project_id=self._project_id)
            saved_ids.append(decision_id)
            logger.info("Decision saved: %s - %s", decision_id, point.title)

        if saved_ids:
            self._broadcast_discussion_event(f"已保存 {len(saved_ids)} 个决策")

        return saved_ids

    async def _generate_visual_concepts(self, final_result: str) -> list[str]:
        """Generate visual concepts based on the final decision document.

        Args:
            final_result: The final decision document from Lead Planner.

        Returns:
            List of generated image URLs.
        """
        if self._visual_concept is None:
            return []

        visual_requests = parse_visual_requirements(final_result)
        if not visual_requests:
            return []

        self._broadcast_discussion_event(f"正在生成 {len(visual_requests)} 个视觉概念...")

        generated_urls: list[str] = []

        # Map visual types to style IDs
        type_to_style = {
            "ui": "ui_icon",
            "界面": "ui_icon",
            "图标": "ui_icon",
            "场景": "concept_scene",
            "环境": "concept_scene",
            "角色": "concept_character",
            "人物": "concept_character",
            "物品": "concept_item",
            "道具": "concept_item",
        }

        for request in visual_requests:
            try:
                # Determine style based on type
                style_id = "concept_scene"  # default
                type_lower = request.type.lower()
                for keyword, style in type_to_style.items():
                    if keyword in type_lower:
                        style_id = style
                        break

                # Generate the image
                result = await self._visual_concept.image_service.generate(
                    description=f"{request.type}: {request.description}",
                    project_id=self._project_id,
                    style_id=style_id,
                    agent="visual_concept",
                )

                if result.success and result.image_url:
                    generated_urls.append(result.image_url)
                    self._broadcast_message(
                        "视觉概念",
                        f"已生成 {request.type}:\n![{request.type}]({result.image_url})",
                    )
                    logger.info("Generated visual concept: %s -> %s", request.type, result.image_url)
                else:
                    logger.warning("Failed to generate visual: %s - %s", request.type, result.error)

            except Exception as e:
                logger.warning("Error generating visual concept: %s", e)

        if generated_urls:
            self._broadcast_discussion_event(f"已生成 {len(generated_urls)} 个视觉概念")

        return generated_urls

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
        rounds: int = 2,
        attachment: str | None = None,
    ) -> list[Task]:
        """Create discussion tasks for the given topic with lead planner moderation.

        The new flow:
        - Phase 0: Lead Planner opens the discussion
        - Phase 1-N: Each round has discussion agents speak, then lead planner summarizes
        - Final: Lead Planner makes final decisions and generates document

        Args:
            topic: The design topic to discuss.
            rounds: Maximum number of discussion rounds.
            attachment: Optional markdown attachment content.

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
        lead_agent = self._lead_planner.build_agent()
        system_agent = self._system_designer.build_agent()
        number_agent = self._number_designer.build_agent()
        player_agent = self._player_advocate.build_agent()

        discussion_agents = [system_agent, number_agent, player_agent]

        # Phase 0: Lead Planner Opening
        opening_description = self._lead_planner.create_opening_prompt(topic, attachment)
        if history_section:
            opening_description += f"\n{history_section}"

        opening_task = Task(
            name="opening",
            description=opening_description,
            expected_output="讨论开场：明确目标、关键问题、讨论范围和期望产出",
            agent=lead_agent,
        )
        tasks.append(opening_task)
        self._task_agent_roles.append(lead_agent.role)

        # Phase 1-N: Discussion Rounds
        for round_num in range(1, rounds + 1):
            # Each discussion agent responds to lead planner's questions/opening
            for agent in discussion_agents:
                context_tasks = tasks[-4:] if tasks else []

                if round_num == 1:
                    # First round: respond to lead planner's opening questions
                    description = f"""
作为{agent.role}，请针对主策划提出的问题，从你的专业角度发表观点。

话题：{topic}
当前阶段：第{round_num}轮讨论

请：
1. 回应主策划提出的关键问题
2. 从你的专业角度提出设计建议
3. 指出你认为需要关注的风险或挑战
"""
                else:
                    # Subsequent rounds: respond based on lead planner's summary and new questions
                    description = f"""
作为{agent.role}，请基于主策划的总结和新问题，继续发表你的观点。

话题：{topic}
当前阶段：第{round_num}轮讨论

请：
1. 回应主策划提出的新问题或需要深入的点
2. 针对存在分歧的地方，给出你的论据
3. 如果同意某个观点，说明原因；如果有补充，具体说明
"""

                expected_output = f"{agent.role}对'{topic}'第{round_num}轮的专业分析"

                task = Task(
                    name=f"round-{round_num}-{agent.role}",
                    description=description,
                    expected_output=expected_output,
                    agent=agent,
                    context=context_tasks if context_tasks else None,
                )
                tasks.append(task)
                self._task_agent_roles.append(agent.role)

            # Lead Planner summarizes this round
            summary_description = self._lead_planner.create_round_summary_prompt(round_num, topic)
            summary_task = Task(
                name=f"round-{round_num}-summary",
                description=summary_description,
                expected_output=f"第{round_num}轮总结：共识、分歧、需深入的问题、下一步",
                agent=lead_agent,
                context=tasks[-3:],  # Last 3 discussion agent responses
            )
            tasks.append(summary_task)
            self._task_agent_roles.append(lead_agent.role)

        # Final Phase: Lead Planner makes final decisions
        final_description = self._lead_planner.create_final_decision_prompt(topic)
        final_task = Task(
            name="final-decision",
            description=final_description,
            expected_output="策划决策文档：设计概述、关键决策及理由、待确认事项、下一步行动",
            agent=lead_agent,
            context=tasks[-6:],  # Use last 6 tasks as context
        )
        tasks.append(final_task)
        self._task_agent_roles.append(lead_agent.role)

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
            broadcast_sync(event.to_dict(), discussion_id=self._discussion_id)
        except Exception as exc:
            logger.debug("Failed to broadcast status: %s", exc)

    def _broadcast_message(
        self,
        agent_role: str,
        content: str,
        sequence: int | None = None,
    ) -> None:
        """Broadcast agent message via WebSocket.

        Args:
            agent_role: The agent's role name.
            content: The message content.
            sequence: Optional message sequence number. If None, auto-increments.
        """
        if self._discussion_id is None:
            return

        # Use provided sequence or auto-increment
        msg_sequence = sequence if sequence is not None else self._next_sequence()

        try:
            event = create_message_event(
                discussion_id=self._discussion_id,
                agent_id=agent_role.lower().replace(" ", "_"),
                agent_role=agent_role,
                content=content,
                sequence=msg_sequence,
            )
            broadcast_sync(event.to_dict(), discussion_id=self._discussion_id)
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
            broadcast_sync(event.to_dict(), discussion_id=self._discussion_id)
        except Exception as exc:
            logger.debug("Failed to broadcast discussion event: %s", exc)

    async def _run_parallel_responses(
        self,
        mentioned_roles: list[str],
        context: str,
    ) -> list[tuple[str, str]]:
        """Run parallel responses from mentioned agents.

        This method calls all mentioned agents in parallel using asyncio.gather().
        If no specific roles are mentioned, all discussion agents respond.

        Args:
            mentioned_roles: List of role names that should respond.
            context: The discussion context to respond to.

        Returns:
            List of (role, response) tuples in completion order.
        """
        # Filter agents based on mentioned roles
        agents_to_call = [
            agent for agent in self._discussion_agents
            if agent.role in mentioned_roles
        ]

        # If no specific roles mentioned, all agents respond
        if not agents_to_call:
            agents_to_call = self._discussion_agents

        # Broadcast thinking status for all participating agents
        for agent in agents_to_call:
            self._broadcast_status(agent.role, AgentStatus.THINKING)

        # Define async function to call a single agent
        async def call_agent(agent: Any) -> tuple[str, str]:
            response = await agent.respond_async(context)
            return (agent.role, response)

        # Run all agent calls in parallel
        results = await asyncio.gather(*[
            call_agent(agent) for agent in agents_to_call
        ])

        return list(results)

    def _process_round_summary(self, summary: str, task_name: str) -> None:
        """Process a round summary from the Lead Planner.

        Args:
            summary: The Lead Planner's summary output.
            task_name: The task name (e.g., "round-1-summary").
        """
        # Extract round number from task name
        try:
            round_num = int(task_name.split("-")[1])
            self._current_round = round_num
        except (IndexError, ValueError):
            pass

        # Parse the summary to determine discussion status
        status, questions = parse_discussion_status(summary)
        self._discussion_status = status
        self._pending_questions = questions

        # Log the status change
        logger.info(
            "Discussion %s round %d: status=%s, pending_questions=%d",
            self._discussion_id,
            self._current_round,
            status.value,
            len(questions),
        )

        # Broadcast status change
        status_msg = {
            "continue": f"第{self._current_round}轮总结完成，继续讨论",
            "sufficient": f"第{self._current_round}轮总结完成，讨论充分，准备最终决策",
            "refine": f"第{self._current_round}轮总结完成，需要深入讨论{len(questions)}个问题",
        }
        self._broadcast_discussion_event(status_msg.get(status.value, ""))

        # Auto-pause check: pause every N rounds (skip if this is the last round)
        if (
            self._auto_pause_interval > 0
            and self._current_round > 0
            and self._current_round % self._auto_pause_interval == 0
            and self._current_round < self._total_rounds
        ):
            logger.info(
                "Auto-pausing discussion %s at round %d (interval=%d)",
                self._discussion_id,
                self._current_round,
                self._auto_pause_interval,
            )
            set_discussion_state(self._discussion_id, DiscussionState.PAUSED)
            self._broadcast_discussion_event(
                f"discussion_auto_paused:已完成第{self._current_round}轮讨论，等待继续"
            )

    def _broadcast_error(self, content: str) -> None:
        """Broadcast an error event via WebSocket."""
        if self._discussion_id is None:
            return

        try:
            event = create_error_event(
                discussion_id=self._discussion_id,
                content=content,
            )
            broadcast_sync(event.to_dict(), discussion_id=self._discussion_id)
        except Exception as exc:
            logger.debug("Failed to broadcast error event: %s", exc)

    def _build_task_callback(
        self,
        trace_span: Any | None,
    ) -> Callable[[TaskOutput], None]:
        """Create a task callback that forwards output and records tracing spans."""

        def _callback(task_output: TaskOutput) -> None:
            agent_role = str(task_output.agent) if task_output.agent else "Unknown"
            task_name = task_output.name or ""

            # Broadcast status change: speaking -> idle
            self._broadcast_status(agent_role, AgentStatus.SPEAKING)
            self._broadcast_message(agent_role, str(task_output))
            self._broadcast_status(agent_role, AgentStatus.IDLE)

            # Record message to memory
            self._record_message(agent_role, str(task_output))

            # Check if this is a lead planner round summary
            if "summary" in task_name and "主策划" in agent_role:
                self._process_round_summary(str(task_output), task_name)

            # Check for pause between agent turns (intervention checkpoint)
            injected_messages = self._check_pause_and_wait()
            if self._abort_reason:
                raise DiscussionTimeoutError(self._abort_reason)
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
                langfuse_client = get_langfuse_client()
                if langfuse_client is None or not hasattr(
                    langfuse_client, "start_as_current_observation"
                ):
                    return

                span_name = task_output.name or f"task:{task_output.agent}"
                with langfuse_client.start_as_current_observation(
                    as_type="span",
                    name=span_name,
                ) as span:
                    span.update(
                        input={
                            "description": task_output.description,
                            "expected_output": task_output.expected_output,
                        },
                        output=task_output.raw,
                        metadata={
                            "agent": task_output.agent,
                            "output_format": str(task_output.output_format),
                        },
                    )
            except Exception as exc:
                logger.debug("Failed to record Langfuse span: %s", exc)

        return _callback

    def _prepare_trace_metadata(
        self,
        topic: str,
        rounds: int,
    ) -> dict[str, Any]:
        """Prepare trace metadata for Langfuse."""
        return {
            "topic": topic,
            "rounds": rounds,
            "agents": [agent.role for agent in self._agents],
            "discussion_id": self._discussion_id,
            "project_id": self._project_id,
        }

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
        except Exception as exc:
            logger.debug("Failed to finalize Langfuse trace: %s", exc)

    def run(
        self,
        topic: str,
        rounds: int = 2,
        verbose: bool = True,
        attachment: str | None = None,
        auto_pause_interval: int = 5,
    ) -> str:
        """Run a design discussion on the given topic.

        Args:
            topic: The design topic to discuss.
            rounds: Number of discussion rounds (default: 3).
            verbose: Whether to print verbose output (default: True).
            attachment: Optional markdown attachment content.
            auto_pause_interval: Auto-pause every N rounds (0=disabled).

        Returns:
            The final discussion result/summary.
        """
        # Initialize discussion record
        self._init_discussion(topic)

        # Store auto-pause config
        self._auto_pause_interval = auto_pause_interval
        self._total_rounds = rounds

        # Initialize discussion state for pause/resume
        set_discussion_state(self._discussion_id, DiscussionState.RUNNING)

        self._abort_reason = None
        tasks = self.create_discussion_tasks(topic, rounds, attachment=attachment)
        trace_metadata = self._prepare_trace_metadata(topic, rounds)

        # Broadcast initial thinking status for first agent
        if self._agents:
            first_agent = self._agents[0]
            self._broadcast_status(first_agent.role, AgentStatus.THINKING)

        trace_span: Any | None = None
        try:
            with start_trace_context(
                name="discussion",
                session_id=self._discussion_id,
                metadata=trace_metadata,
            ) as span:
                trace_span = span
                task_callback = self._build_task_callback(trace_span)
                crew = Crew(
                    agents=[agent.build_agent() for agent in self._agents],
                    tasks=tasks,
                    process=Process.sequential,
                    verbose=verbose,
                    task_callback=task_callback,
                )

                result = crew.kickoff()

                if self._abort_reason:
                    raise DiscussionTimeoutError(self._abort_reason)

                self._finalize_trace(trace_span, result=result)

            # Save discussion to memory with summary
            self._save_discussion(summary=str(result))

            # Extract and save decisions from the final result
            try:
                self._save_decisions(str(result), topic)
            except Exception as e:
                logger.warning("Failed to save decisions: %s", e)

            # Generate visual concepts if enabled (sync wrapper)
            if self._visual_concept is not None:
                try:
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(self._generate_visual_concepts(str(result)))
                    finally:
                        loop.close()
                except Exception as e:
                    logger.warning("Failed to generate visual concepts: %s", e)

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
        rounds: int = 2,
        verbose: bool = True,
        attachment: str | None = None,
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

        self._abort_reason = None
        tasks = self.create_discussion_tasks(topic, rounds)
        trace_metadata = self._prepare_trace_metadata(topic, rounds)

        # Broadcast initial thinking status for first agent
        if self._agents:
            first_agent = self._agents[0]
            self._broadcast_status(first_agent.role, AgentStatus.THINKING)

        trace_span: Any | None = None
        try:
            with start_trace_context(
                name="discussion",
                session_id=self._discussion_id,
                metadata=trace_metadata,
            ) as span:
                trace_span = span
                task_callback = self._build_task_callback(trace_span)
                crew = Crew(
                    agents=[agent.build_agent() for agent in self._agents],
                    tasks=tasks,
                    process=Process.sequential,
                    verbose=verbose,
                    task_callback=task_callback,
                )

                result = await crew.kickoff_async()

                if self._abort_reason:
                    raise DiscussionTimeoutError(self._abort_reason)

                self._finalize_trace(trace_span, result=result)

            # Save discussion to memory with summary
            self._save_discussion(summary=str(result))

            # Extract and save decisions from the final result
            try:
                self._save_decisions(str(result), topic)
            except Exception as e:
                logger.warning("Failed to save decisions: %s", e)

            # Generate visual concepts if enabled (async)
            if self._visual_concept is not None:
                try:
                    await self._generate_visual_concepts(str(result))
                except Exception as e:
                    logger.warning("Failed to generate visual concepts: %s", e)

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

    async def _lead_planner_opening(
        self,
        topic: str,
        attachment: str | None = None,
    ) -> str:
        """Generate Lead Planner's opening statement.

        Args:
            topic: The discussion topic.
            attachment: Optional attachment content.

        Returns:
            The Lead Planner's opening statement.
        """
        opening_prompt = self._lead_planner.create_opening_prompt(topic, attachment)
        task = Task(
            description=opening_prompt,
            expected_output="讨论开场：明确目标、关键问题、讨论范围和期望产出",
            agent=self._lead_planner.build_agent(),
        )

        crew = Crew(
            agents=[self._lead_planner.build_agent()],
            tasks=[task],
            process=Process.sequential,
        )

        result = await crew.kickoff_async()
        return str(result)

    async def _lead_planner_summary(
        self,
        round_num: int,
        topic: str,
        context: str,
    ) -> str:
        """Generate Lead Planner's round summary.

        Args:
            round_num: Current round number.
            topic: The discussion topic.
            context: The full discussion context.

        Returns:
            The Lead Planner's summary for this round.
        """
        summary_prompt = self._lead_planner.create_round_summary_prompt(round_num, topic)
        full_prompt = f"{summary_prompt}\n\n---\n讨论记录：\n{context}"

        task = Task(
            description=full_prompt,
            expected_output=f"第{round_num}轮总结：共识、分歧、需深入的问题、下一步",
            agent=self._lead_planner.build_agent(),
        )

        crew = Crew(
            agents=[self._lead_planner.build_agent()],
            tasks=[task],
            process=Process.sequential,
        )

        result = await crew.kickoff_async()
        return str(result)

    async def _lead_planner_final_decision(
        self,
        topic: str,
        context: str,
    ) -> str:
        """Generate Lead Planner's final decision document.

        Args:
            topic: The discussion topic.
            context: The full discussion context.

        Returns:
            The Lead Planner's final decision document.
        """
        final_prompt = self._lead_planner.create_final_decision_prompt(topic)
        full_prompt = f"{final_prompt}\n\n---\n讨论记录：\n{context}"

        task = Task(
            description=full_prompt,
            expected_output="策划决策文档：设计概述、关键决策及理由、待确认事项、下一步行动",
            agent=self._lead_planner.build_agent(),
        )

        crew = Crew(
            agents=[self._lead_planner.build_agent()],
            tasks=[task],
            process=Process.sequential,
        )

        result = await crew.kickoff_async()
        return str(result)

    async def run_dynamic(
        self,
        topic: str,
        max_rounds: int = 5,
        attachment: str | None = None,
    ) -> str:
        """Run a dynamic discussion with parallel agent responses.

        This method implements the new discussion flow where:
        1. Lead Planner opens the discussion
        2. Mentioned roles respond in parallel
        3. Lead Planner summarizes and determines if more discussion is needed
        4. Repeat until sufficient or max_rounds reached
        5. Lead Planner makes final decisions

        Args:
            topic: The design topic to discuss.
            max_rounds: Maximum number of discussion rounds.
            attachment: Optional markdown attachment content.

        Returns:
            The final discussion result/decision document.
        """
        # Initialize discussion record
        self._init_discussion(topic)

        # Initialize discussion state for pause/resume
        set_discussion_state(self._discussion_id, DiscussionState.RUNNING)

        trace_metadata = self._prepare_trace_metadata(topic, max_rounds)

        try:
            with start_trace_context(
                name="discussion_dynamic",
                session_id=self._discussion_id,
                metadata=trace_metadata,
            ) as trace_span:

                # Phase 0: Lead Planner opens the discussion
                self._broadcast_status(self._lead_planner.role, AgentStatus.THINKING)
                opening = await self._lead_planner_opening(topic, attachment)

                self._broadcast_status(self._lead_planner.role, AgentStatus.SPEAKING)
                self._broadcast_message(self._lead_planner.role, opening)
                self._record_message(self._lead_planner.role, opening)
                self._broadcast_status(self._lead_planner.role, AgentStatus.IDLE)

                # Initialize context with opening
                context = f"议题：{topic}\n\n主策划开场：\n{opening}"
                round_num = 0

                # Phase 1-N: Dynamic discussion rounds
                while round_num < max_rounds:
                    round_num += 1
                    self._current_round = round_num

                    # Parse mentioned roles from context (primarily from latest summary/opening)
                    mentioned_roles = parse_mentioned_roles(opening if round_num == 1 else context)

                    # Run parallel responses from mentioned agents
                    responses = await self._run_parallel_responses(mentioned_roles, context)

                    # Record and broadcast responses
                    for role, response in responses:
                        self._broadcast_status(role, AgentStatus.SPEAKING)
                        self._broadcast_message(role, response)
                        self._record_message(role, response)
                        self._broadcast_status(role, AgentStatus.IDLE)
                        context += f"\n\n{role}：\n{response}"

                    # Check for pause/intervention
                    injected_messages = self._check_pause_and_wait()
                    if self._abort_reason:
                        raise DiscussionTimeoutError(self._abort_reason)
                    if injected_messages:
                        self._inject_user_messages(injected_messages)
                        for msg in injected_messages:
                            context += f"\n\n用户介入：\n{msg.get('content', '')}"

                    # Lead Planner summarizes this round
                    self._broadcast_status(self._lead_planner.role, AgentStatus.THINKING)
                    summary = await self._lead_planner_summary(round_num, topic, context)

                    self._broadcast_status(self._lead_planner.role, AgentStatus.SPEAKING)
                    self._broadcast_message(self._lead_planner.role, summary)
                    self._record_message(self._lead_planner.role, summary)
                    self._broadcast_status(self._lead_planner.role, AgentStatus.IDLE)
                    context += f"\n\n主策划总结（第{round_num}轮）：\n{summary}"

                    # Check if discussion should continue
                    status, questions = parse_discussion_status(summary)
                    self._discussion_status = status
                    self._pending_questions = questions

                    if status == DiscussionStatus.SUFFICIENT:
                        logger.info("Discussion %s: sufficient after round %d", self._discussion_id, round_num)
                        break

                    self._broadcast_discussion_event(f"第{round_num}轮讨论完成")

                # Final Phase: Lead Planner makes final decisions
                self._broadcast_discussion_event("正在生成最终决策文档...")
                self._broadcast_status(self._lead_planner.role, AgentStatus.THINKING)
                final_decision = await self._lead_planner_final_decision(topic, context)

                self._broadcast_status(self._lead_planner.role, AgentStatus.SPEAKING)
                self._broadcast_message(self._lead_planner.role, final_decision)
                self._record_message(self._lead_planner.role, final_decision)
                self._broadcast_status(self._lead_planner.role, AgentStatus.IDLE)

                self._finalize_trace(trace_span, result=final_decision)

            # Save discussion to memory
            self._save_discussion(summary=final_decision)

            # Extract and save decisions
            try:
                self._save_decisions(final_decision, topic)
            except Exception as e:
                logger.warning("Failed to save decisions: %s", e)

            # Generate visual concepts if enabled
            if self._visual_concept is not None:
                try:
                    await self._generate_visual_concepts(final_decision)
                except Exception as e:
                    logger.warning("Failed to generate visual concepts: %s", e)

            # Mark discussion as finished and clean up
            set_discussion_state(self._discussion_id, DiscussionState.FINISHED)
            cleanup_discussion_state(self._discussion_id)

            # Broadcast completion status
            for agent in self._agents:
                self._broadcast_status(agent.role, AgentStatus.IDLE)
            self._broadcast_discussion_event("discussion_completed")

            return final_decision

        except Exception as exc:
            self._broadcast_error(str(exc))
            self._broadcast_discussion_event("discussion_failed")
            self._save_discussion()
            cleanup_discussion_state(self._discussion_id)
            for agent in self._agents:
                self._broadcast_status(agent.role, AgentStatus.IDLE)
            raise
