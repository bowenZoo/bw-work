"""Discussion Crew - Orchestrates multi-agent design discussions."""

import json
import logging
import os
import re
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from crewai import Crew, Process, Task
from crewai.tasks.task_output import TaskOutput

from src.agents import LeadPlanner, NumberDesigner, OperationsAnalyst, PlayerAdvocate, SystemDesigner, VisualConceptAgent
from src.agents.creative_director import CreativeDirector
from src.agents.tech_director import TechDirector
from src.agents.market_director import MarketDirector
from src.agents.moderators import (
    SystemDesignerModerator, NumberDesignerModerator, VisualConceptModerator,
    MarketDirectorModerator, OperationsAnalystModerator, PlayerAdvocateModerator,
)
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
from src.crew.mention_parser import parse_mentioned_roles, sanitize_speakers_in_text, PRODUCER_ROLE
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

# Regex patterns for parsing LLM directive blocks
AGENDA_DIRECTIVE_PATTERN = re.compile(r"```agenda_update\s*\n(.*?)```", re.DOTALL)
DOC_RESTRUCTURE_PATTERN = re.compile(r"```doc_restructure\s*\n(.*?)```", re.DOTALL)
INTERVENTION_ASSESSMENT_PATTERN = re.compile(r"```intervention_assessment\s*\n(.*?)```", re.DOTALL)
HOLISTIC_REVIEW_PATTERN = re.compile(r"```holistic_review\s*\n(.*?)```", re.DOTALL)


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

    # Available discussion agents (excluding lead planner).
    # Class-level so external code can query available roles.
    AVAILABLE_AGENTS: dict[str, type] = {
        "system_designer": SystemDesigner,
        "number_designer": NumberDesigner,
        "player_advocate": PlayerAdvocate,
        "operations_analyst": OperationsAnalyst,
        "market_director": MarketDirector,
        "tech_director": TechDirector,
    }

    # Agents that can serve as moderator (replace lead_planner)
    MODERATOR_AGENTS: dict[str, type] = {
        "lead_planner": LeadPlanner,
        "creative_director": CreativeDirector,
        "system_designer": SystemDesignerModerator,
        "number_designer": NumberDesignerModerator,
        "visual_concept": VisualConceptModerator,
        "market_director": MarketDirectorModerator,
        "operations_analyst": OperationsAnalystModerator,
        "player_advocate": PlayerAdvocateModerator,
        "tech_director": TechDirector,
    }

    _TOOL_CALL_RE = re.compile(
        r"ChatCompletionMessageFunctionToolCall|no_tool_available|Function\(arguments=",
        re.IGNORECASE,
    )

    @staticmethod
    def _sanitize_crew_output(raw: str, label: str = "agent") -> str:
        """Sanitize CrewAI output, filtering out malformed tool-call responses."""
        if DiscussionCrew._TOOL_CALL_RE.search(raw):
            logger.warning("Malformed tool-call in %s output: %.120s", label, raw)
            return ""
        return raw

    def __init__(
        self,
        llm: Any | None = None,
        callback: Callable[[str, str], None] | None = None,
        discussion_id: str | None = None,
        project_id: str | None = None,
        data_dir: str = "data/projects",
        enable_visual_concept: bool = False,
        agent_roles: list[str] | None = None,
        agent_configs: dict | None = None,
        moderator_role: str | None = None,
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
            agent_roles: Optional list of agent role names to participate.
                        If None, all agents participate (backward compatible).
            agent_configs: Optional dict of role_name -> config overrides.
            moderator_role: Optional role name to use as moderator instead of
                           lead_planner (e.g. 'creative_director').
        """
        self._llm = llm
        self._callback = callback
        self._discussion_id = discussion_id or str(uuid4())
        self._project_id = project_id or "default"
        self._data_dir = data_dir
        self._enable_visual_concept = enable_visual_concept

        # Determine moderator class
        moderator_cls = self.MODERATOR_AGENTS.get(moderator_role or "lead_planner", LeadPlanner)
        lead_overrides = (agent_configs or {}).get(moderator_role or "lead_planner") or (agent_configs or {}).get("lead_planner")
        self._lead_planner = moderator_cls(llm=llm, config_overrides=lead_overrides)
        self._moderator_role = moderator_role or "lead_planner"

        # Build discussion agents based on agent_roles selection
        # Exclude the moderator role itself from discussion agents
        self._discussion_agents = []
        for role, cls in self.AVAILABLE_AGENTS.items():
            if agent_roles is None or role in agent_roles:
                overrides = (agent_configs or {}).get(role)
                agent = cls(llm=llm, config_overrides=overrides)
                self._discussion_agents.append(agent)

        # Also include lead_planner as discussion agent if using a different moderator
        # and lead_planner is explicitly in agent_roles
        if self._moderator_role != "lead_planner" and (agent_roles is None or "lead_planner" in (agent_roles or [])):
            lp_overrides = (agent_configs or {}).get("lead_planner")
            lp = LeadPlanner(llm=llm, config_overrides=lp_overrides)
            self._discussion_agents.append(lp)

        # All agents including lead planner
        self._agents = [self._lead_planner] + self._discussion_agents

        # Optionally add Visual Concept Agent
        if enable_visual_concept and (agent_roles is None or "visual_concept" in agent_roles):
            vc_overrides = (agent_configs or {}).get("visual_concept")
            self._visual_concept = VisualConceptAgent(
                llm=llm,
                config_overrides=vc_overrides,
                project_id=self._project_id,
            )
            self._agents.append(self._visual_concept)
        else:
            self._visual_concept = None

        # Keep backward-compat references if agents were created
        self._system_designer = next(
            (a for a in self._discussion_agents if a.role_name == "system_designer"), None
        )
        self._number_designer = next(
            (a for a in self._discussion_agents if a.role_name == "number_designer"), None
        )
        self._player_advocate = next(
            (a for a in self._discussion_agents if a.role_name == "player_advocate"), None
        )

        # Initialize memory systems
        self._discussion_memory = DiscussionMemory(data_dir=data_dir)
        self._decision_tracker = DecisionTracker(data_dir=data_dir)

        # Current discussion record
        self._current_discussion: Discussion | None = None
        self._messages: list[Message] = []
        self._task_agent_roles: list[str] = []
        self._task_index = 0
        self._abort_reason: str | None = None
        self._unsaved_message_count = 0  # Track messages since last incremental save
        self._INCREMENTAL_SAVE_INTERVAL = 1  # Save to disk after every message

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

        # Document-centric mode
        self._doc_plan = None  # DocPlan instance
        self._doc_writer = None  # DocWriter instance
        self._section_summaries: list[str] = []  # sliding window of recent summaries
        self._section_decisions: dict[str, list[str]] = {}  # section_id -> accumulated round decisions

        # Checkpoint system
        self._briefing: str = ""
        self._checkpoint_counter = 0
        self._pending_decision_checkpoints: dict[str, Any] = {}  # cp_id -> Checkpoint
        self._checkpoint_lock = __import__("threading").Lock()
        self._pending_producer_messages: list[dict] = []
        self._producer_message_lock = __import__("threading").Lock()
        self._producer_digest_pending: str | None = None  # digest to inject into next round

        # Concurrency semaphore — set by the caller (_run_discussion_sync) so that
        # the crew can release the slot while waiting for a human decision and
        # re-acquire it when the discussion resumes.
        self._concurrency_semaphore: Any | None = None

        # Inject context-aware tools into agents
        self._inject_context_tools()

    def _inject_context_tools(self) -> None:
        """Inject context-aware tools (memory_search, read_project_doc, request_vote) into agents."""
        try:
            from src.crew.tools import (
                create_memory_search_tool,
                create_read_project_doc_tool,
                create_request_vote_tool,
            )
            from src.api.websocket.manager import global_connection_manager

            memory_tool = create_memory_search_tool(self._discussion_memory, self._project_id)
            doc_tool = create_read_project_doc_tool(self._project_id)
            vote_tool = create_request_vote_tool(self._discussion_id, global_connection_manager)

            # All agents get memory_search and read_project_doc
            for agent in self._agents:
                agent._extra_tools.extend([memory_tool, doc_tool])

            # Only lead planner gets request_vote
            self._lead_planner._extra_tools.append(vote_tool)
        except Exception as exc:
            logger.warning("Failed to inject context-aware tools: %s", exc)

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

    def _gather_project_documents(self) -> str:
        """Gather all project documents for discussion penetration."""
        try:
            from src.admin.database import AdminDatabase
            db = AdminDatabase()
            docs = db.get_project_documents(self._project_id)
            if not docs:
                return ""
            parts = []
            for doc in docs:
                title = doc.get("title", "未命名")
                content = doc.get("content", "")
                if content:
                    if len(content) > 3000:
                        content = content[:3000] + "\n... (已截断)"
                    parts.append(f"### {title}\n{content}")
            return "\n\n".join(parts) if parts else ""
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to gather project documents: {e}")
            return ""

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

    def _wait_for_producer_turn(self) -> None:
        """Pause and wait for the producer (human) to send a message.

        Called when ``制作人`` appears in a ``speakers`` block. Blocks until
        a producer message arrives or the discussion is manually resumed /
        finished.  Does **not** consume the messages — they remain in
        ``_pending_producer_messages`` for normal processing by
        ``_check_producer_messages()``.
        """
        from src.crew.mention_parser import PRODUCER_ROLE as _PR  # local import avoids cycle

        set_discussion_state(self._discussion_id, DiscussionState.PAUSED)
        self._broadcast_discussion_event(
            "discussion_waiting_producer:等待制作人发言，请在下方输入框中分享您的想法..."
        )
        logger.info("Discussion %s: waiting for producer turn", self._discussion_id)

        start_time = time.time()
        while True:
            # Auto-resume when the producer sends any message
            if self._has_pending_producer_messages():
                set_discussion_state(self._discussion_id, DiscussionState.RUNNING)
                self._broadcast_discussion_event("discussion_resumed")
                logger.info(
                    "Discussion %s: producer message received, resuming", self._discussion_id
                )
                return

            state_info = get_discussion_state(self._discussion_id)
            if state_info is None:
                return

            current_state = state_info["state"]
            if current_state in (DiscussionState.RUNNING, DiscussionState.FINISHED):
                return

            if time.time() - start_time > self._pause_timeout:
                logger.warning(
                    "Discussion %s: producer turn timed out", self._discussion_id
                )
                self._abort_reason = "Producer turn timed out"
                set_discussion_state(self._discussion_id, DiscussionState.FINISHED)
                raise DiscussionTimeoutError(self._abort_reason)

            time.sleep(self._pause_check_interval)

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

    # ------------------------------------------------------------------
    # Windowed context builder — replaces unbounded context accumulation
    # ------------------------------------------------------------------

    def _build_windowed_context(
        self,
        topic: str,
        opening: str,
        current_round_messages: list[tuple[str, str]],
        last_summary: str | None = None,
        injected_messages: list[dict] | None = None,
        producer_messages: list[tuple[str, str]] | None = None,
        *,
        summary_window: int = 3,
        for_lead_planner: bool = False,
    ) -> str:
        """Build a windowed context for LLM calls instead of full history.

        Constructs a three-layer context that mimics human meeting memory:
        - Layer 1: Topic + briefing (fixed)
        - Layer 2: Historical round summaries (compressed)
        - Layer 3: Current round full messages (working memory)

        Args:
            topic: The discussion topic.
            opening: Lead Planner's opening statement.
            current_round_messages: List of (role, content) for current round.
            last_summary: The previous round's lead planner summary.
            injected_messages: User intervention messages in current round.
            producer_messages: Producer messages as (content, digest) pairs.
            summary_window: Number of historical round summaries to include.
                For lead planner, this is automatically doubled.
            for_lead_planner: If True, uses larger context window.

        Returns:
            A structured context string, typically 4K-8K tokens.
        """
        parts: list[str] = []
        effective_window = summary_window * 2 if for_lead_planner else summary_window

        # --- Layer 1: Meeting meta ---
        parts.append(f"## 议题\n{topic}")

        # Briefing (if available)
        if self._briefing:
            parts.append(f"\n## 项目简报\n{self._briefing[:1000]}")

        # Opening (truncated for non-LP agents)
        opening_limit = 1500 if for_lead_planner else 600
        opening_text = opening[:opening_limit]
        if len(opening) > opening_limit:
            opening_text += "\n…(开场内容已截断)"
        parts.append(f"\n## 主策划开场\n{opening_text}")

        # --- Layer 2: Compressed history (round summaries) ---
        round_summaries = []
        if self._current_discussion and self._current_discussion.round_summaries:
            round_summaries = self._current_discussion.round_summaries

        if round_summaries:
            # Take the most recent N summaries
            recent_summaries = round_summaries[-effective_window:]
            total_rounds = len(round_summaries)

            parts.append(f"\n## 历史讨论摘要（共{total_rounds}轮，显示最近{len(recent_summaries)}轮）")

            # If there are earlier rounds not shown, add a compressed note
            if total_rounds > effective_window:
                skipped = total_rounds - effective_window
                # Extract key decisions from older summaries
                early_decisions = self._extract_decisions_from_summaries(
                    round_summaries[:skipped]
                )
                if early_decisions:
                    parts.append(f"\n### 早期讨论已达成的关键决策\n{early_decisions}")

            for summary_data in recent_summaries:
                round_num = summary_data.get("round", "?")
                content = summary_data.get("content", "")
                # For non-LP agents, truncate each summary
                if not for_lead_planner and len(content) > 800:
                    content = content[:800] + "\n…(摘要已截断)"
                parts.append(f"\n### 第{round_num}轮摘要\n{content}")

        # --- Layer 3: Working memory (current round) ---
        # Previous round summary (transition context)
        if last_summary and last_summary not in str(round_summaries[-1:]):
            parts.append(f"\n## 上一轮主策划总结\n{last_summary}")

        # Current round messages
        if current_round_messages:
            parts.append("\n## 当前轮讨论")
            for role, content in current_round_messages:
                parts.append(f"\n{role}：\n{content}")

        # Injected user/intervention messages
        if injected_messages:
            for msg in injected_messages:
                parts.append(f"\n用户介入：\n{msg.get('content', '')}")

        # Producer messages and digests
        if producer_messages:
            for content, digest in producer_messages:
                parts.append(f"\n制作人：\n{content}")
                if digest:
                    parts.append(f"\n[主策划消化制作人消息]：\n{digest}")

        return "\n".join(parts)

    def _extract_decisions_from_summaries(
        self,
        summaries: list[dict],
    ) -> str:
        """Extract key decisions from a list of round summary dicts.

        Scans the 'content' field for consensus and decision sections.

        Args:
            summaries: List of round summary dicts with 'content' key.

        Returns:
            Formatted string of extracted decisions, or empty string.
        """
        decisions: list[str] = []
        for s in summaries:
            content = s.get("content", "")
            # Look for consensus / decision sections in the summary
            for pattern in [
                r"###?\s*(?:已达成共识|临时决策|决策)\s*\n(.*?)(?=\n###?|\Z)",
                r"###?\s*(?:共识|Consensus)\s*\n(.*?)(?=\n###?|\Z)",
            ]:
                match = re.search(pattern, content, re.DOTALL)
                if match:
                    for line in match.group(1).strip().split("\n"):
                        stripped = line.strip()
                        if stripped and (stripped.startswith("-") or stripped.startswith("*")):
                            decisions.append(stripped)
                    break  # one pattern match per summary is enough
            if len(decisions) >= 20:
                break

        return "\n".join(decisions) if decisions else ""

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
- 运营策划：...

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
        self._unsaved_message_count = 0

        # Save immediately so the discussion exists in DiscussionMemory
        # even if the server restarts before crew.kickoff() completes
        self._discussion_memory.save(discussion)
        logger.info("Discussion initialized and saved: %s", self._discussion_id)

        return discussion

    def _record_message(self, agent_role: str, content: str) -> None:
        """Record a message from an agent.

        Args:
            agent_role: The agent's role.
            content: The message content.
        """
        message = Message(
            id=str(uuid4()),
            agent_id=self._role_to_agent_id(agent_role),
            agent_role=agent_role,
            content=content,
            timestamp=datetime.now(),
        )
        self._messages.append(message)

        # Incremental save to persist messages periodically
        self._unsaved_message_count += 1
        if self._unsaved_message_count >= self._INCREMENTAL_SAVE_INTERVAL:
            self._incremental_save()

    def _incremental_save(self) -> None:
        """Save current messages to DiscussionMemory without summary."""
        if self._current_discussion is None:
            return
        self._current_discussion.messages = list(self._messages)
        self._current_discussion.updated_at = datetime.now()
        try:
            self._discussion_memory.save(self._current_discussion)
            self._unsaved_message_count = 0
            logger.debug(
                "Incremental save: %s (%d messages)",
                self._current_discussion.id,
                len(self._messages),
            )
        except Exception as e:
            logger.warning("Incremental save failed: %s", e)

    def _generate_round_summary(self, round_num: int, raw_summary: str) -> dict:
        """Parse Lead Planner's round summary into structured data.

        Reuses _parse_agenda_summary logic without extra LLM calls.

        Args:
            round_num: The round number.
            raw_summary: The raw summary text from Lead Planner.

        Returns:
            A dict with round, content, key_points, open_questions, generated_at.
        """
        import re

        key_points: list[str] = []
        open_questions: list[str] = []

        # Extract key points / conclusions
        for pattern in [
            r"##\s*(?:讨论结论|关键共识|本轮共识|共识)\s*\n(.*?)(?=\n##|\Z)",
            r"##\s*(?:Key Points|Conclusions)\s*\n(.*?)(?=\n##|\Z)",
        ]:
            match = re.search(pattern, raw_summary, re.DOTALL)
            if match:
                for line in match.group(1).strip().split("\n"):
                    stripped = line.strip()
                    if stripped.startswith("-") or stripped.startswith("*"):
                        key_points.append(stripped.lstrip("-*").strip())
                break

        # If no structured section found, extract bullet points from full text
        if not key_points:
            for line in raw_summary.split("\n"):
                stripped = line.strip()
                if stripped.startswith("- ") and len(stripped) > 10:
                    key_points.append(stripped.lstrip("- ").strip())
                    if len(key_points) >= 5:
                        break

        # Extract open questions
        for pattern in [
            r"##\s*(?:遗留问题|待解决|Open Questions)\s*\n(.*?)(?=\n##|\Z)",
        ]:
            match = re.search(pattern, raw_summary, re.DOTALL)
            if match:
                for line in match.group(1).strip().split("\n"):
                    stripped = line.strip()
                    if stripped.startswith("-") or stripped.startswith("*"):
                        open_questions.append(stripped.lstrip("-*").strip())
                break

        summary_data = {
            "round": round_num,
            "content": raw_summary,
            "key_points": key_points,
            "open_questions": open_questions,
            "generated_at": datetime.now(timezone.utc).isoformat()
            if hasattr(datetime.now(), "tzinfo")
            else datetime.utcnow().isoformat(),
        }
        return summary_data

    def _broadcast_round_summary(self, summary_data: dict) -> None:
        """Broadcast a round summary via WebSocket.

        Args:
            summary_data: The structured round summary dict.
        """
        if self._discussion_id is None:
            return

        try:
            from src.api.websocket.events import create_round_summary_event

            event = create_round_summary_event(
                discussion_id=self._discussion_id,
                round_num=summary_data["round"],
                content=summary_data["content"],
                key_points=summary_data.get("key_points"),
                open_questions=summary_data.get("open_questions"),
            )
            broadcast_sync(event.to_dict(), discussion_id=self._discussion_id)
        except Exception as exc:
            logger.debug("Failed to broadcast round summary: %s", exc)

    def _save_round_summary(self, summary_data: dict) -> None:
        """Save round summary to the discussion record.

        Args:
            summary_data: The structured round summary dict.
        """
        if self._current_discussion is None:
            return
        self._current_discussion.round_summaries.append(summary_data)
        self._incremental_save()

    def _trigger_round_organize(self, round_num: int) -> None:
        """Trigger document organization in a background daemon thread.

        Args:
            round_num: The round number that triggered the organize.
        """
        if self._current_discussion is None:
            return

        discussion_id = self._discussion_id

        def _organize_in_background() -> None:
            max_attempts = 2
            for attempt in range(max_attempts):
                try:
                    from src.agents.doc_organizer import DocOrganizer
                    from src.api.routes.discussion import _get_llm_from_config

                    llm = _get_llm_from_config()
                    if llm is None:
                        logger.debug("Skipping round organize: LLM not configured")
                        return

                    stored = self._discussion_memory.load(discussion_id)
                    if stored is None or not stored.messages:
                        return

                    organizer = DocOrganizer(llm=llm)
                    result = organizer.run_organize(stored)

                    logger.info(
                        "Round %d organize for %s: %d documents",
                        round_num,
                        discussion_id,
                        len(result.files),
                    )

                    # Broadcast doc update event
                    self._broadcast_doc_update(
                        round_num=round_num,
                        files=result.files,
                    )
                    return  # success
                except Exception as exc:
                    if attempt < max_attempts - 1:
                        logger.warning(
                            "Round organize attempt %d failed for %s round %d: %s, retrying in 10s",
                            attempt + 1, discussion_id, round_num, exc,
                        )
                        time.sleep(10)
                    else:
                        logger.warning("Round organize failed for %s round %d: %s", discussion_id, round_num, exc)

        thread = threading.Thread(
            target=_organize_in_background,
            name=f"round-organize-{discussion_id}-r{round_num}",
            daemon=True,
        )
        thread.start()

    def _broadcast_doc_update(self, round_num: int, files: list) -> None:
        """Broadcast a document update event via WebSocket.

        Args:
            round_num: The round that triggered the update.
            files: List of OrganizeFile results.
        """
        if self._discussion_id is None:
            return

        try:
            from src.api.websocket.events import create_doc_update_event

            file_infos = [
                {"filename": f.filename, "title": f.title}
                for f in files
            ]
            event = create_doc_update_event(
                discussion_id=self._discussion_id,
                round_num=round_num,
                file_count=len(files),
                files=file_infos,
            )
            broadcast_sync(event.to_dict(), discussion_id=self._discussion_id)
        except Exception as exc:
            logger.debug("Failed to broadcast doc update: %s", exc)

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
        discussion_agents = [a.build_agent() for a in self._discussion_agents]

        # Document penetration: inject project documents as context
        doc_context = self._gather_project_documents()
        if doc_context:
            history_section += f"\n\n---\n项目已有文档（参考但不重复）：\n{doc_context}\n---\n"

        # Phase 0: Lead Planner Opening
        agent_list = [(a.role, a.goal) for a in self._discussion_agents]
        opening_description = self._lead_planner.create_opening_prompt(topic, attachment, agent_list=agent_list)
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

**严格控制在 200 字以内。直击要点，不说废话和客套话，不重复他人已说过的内容。**
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

**严格控制在 200 字以内。直击要点，不说废话和客套话，不重复他人已说过的内容。**
"""

                expected_output = f"{agent.role}对'{topic}'第{round_num}轮的简短专业分析（200字以内）"

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
            summary_description = self._lead_planner.create_round_summary_prompt(round_num, topic, agent_list=agent_list)
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
        final_description = self._lead_planner.create_final_decision_prompt(topic, agent_list=agent_list)
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

    def _role_to_agent_id(self, agent_role: str) -> str:
        """Map agent role (Chinese display name) to frontend agent ID.

        Looks up the role_name from registered agents, falling back to
        sanitized role string.
        """
        for agent in self._agents:
            if agent.role == agent_role:
                return agent.role_name
        return agent_role.lower().replace(" ", "_")

    def _broadcast_status(
        self,
        agent_role: str,
        status: AgentStatus,
        content: str | None = None,
    ) -> None:
        """Broadcast agent status change via WebSocket.

        Also updates the global agent status registry so that
        newly-connected clients receive the current state on sync.

        Args:
            agent_role: The agent's role name.
            status: The new agent status.
            content: Optional status message.
        """
        if self._discussion_id is None:
            return

        try:
            agent_id = self._role_to_agent_id(agent_role)

            # Update per-discussion agent status registry
            from src.api.routes.discussion import set_agent_status
            set_agent_status(self._discussion_id, agent_id, status.value)

            event = create_status_event(
                discussion_id=self._discussion_id,
                agent_id=agent_id,
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
            agent_id = self._role_to_agent_id(agent_role)
            event = create_message_event(
                discussion_id=self._discussion_id,
                agent_id=agent_id,
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
            # Reset per-discussion agent statuses when discussion ends
            if content in ("discussion_completed", "discussion_failed"):
                from src.api.routes.discussion import reset_agent_statuses
                reset_agent_statuses(self._discussion_id)

            event = create_status_event(
                discussion_id=self._discussion_id,
                agent_id="discussion",
                agent_role="discussion",
                status=AgentStatus.IDLE,
                content=content,
            )
            # Lifecycle events (completed/failed) are also sent to lobby
            is_lifecycle = content in (
                "discussion_completed", "discussion_failed",
                "discussion_started", "discussion_created",
            )
            broadcast_sync(
                event.to_dict(),
                discussion_id=self._discussion_id,
                lobby_event=is_lifecycle,
            )
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
            try:
                from src.crew.tools import set_tool_context, clear_tool_context
                set_tool_context(self._discussion_id, agent.role_name)
            except Exception:
                pass
            try:
                response = await agent.respond_async(context)
            finally:
                try:
                    clear_tool_context()
                except Exception:
                    pass
            return (agent.role, response)

        # Run all agent calls in parallel
        results = await asyncio.gather(*[
            call_agent(agent) for agent in agents_to_call
        ])

        return list(results)

    def _run_agents_parallel_sync(
        self,
        agents_to_call: list[Any],
        context: str,
        interrupt_check: Callable[[], bool] | None = None,
    ) -> tuple[list[tuple[str, str]], bool]:
        """Run multiple agents in parallel, broadcasting as each completes.

        All agents start thinking simultaneously. As each finishes, its
        response is broadcast (speaking → message → idle) immediately.

        When *interrupt_check* is provided it is polled periodically (every
        3 seconds) and after every agent completion.  If it returns ``True``
        the method stops waiting for remaining agents, sets them to idle,
        and returns partial results with ``interrupted=True``.  Background
        threads continue to run but their outputs are discarded.

        Args:
            agents_to_call: List of agent instances to call.
            context: The discussion context to respond to.
            interrupt_check: Optional callable returning True when an
                interrupt is requested (e.g. producer message arrived).

        Returns:
            Tuple of (results, was_interrupted).
        """
        if not agents_to_call:
            return [], False

        # Single agent — no thread pool, no interrupt during LLM call
        if len(agents_to_call) == 1:
            agent = agents_to_call[0]
            self._broadcast_status(agent.role, AgentStatus.THINKING)
            try:
                from src.crew.tools import set_tool_context, clear_tool_context
                set_tool_context(self._discussion_id, agent.role_name)
            except Exception:
                pass
            try:
                response = agent.respond_sync(context)
            finally:
                try:
                    clear_tool_context()
                except Exception:
                    pass
            self._broadcast_status(agent.role, AgentStatus.SPEAKING)
            self._broadcast_message(agent.role, response)
            self._record_message(agent.role, response)
            self._broadcast_status(agent.role, AgentStatus.IDLE)
            return [(agent.role, response)], False

        # Broadcast THINKING for all agents at once
        for agent in agents_to_call:
            self._broadcast_status(agent.role, AgentStatus.THINKING)

        results: list[tuple[str, str]] = []
        interrupted = False

        def _call_with_tool_context(agent: Any, ctx: str) -> str:
            try:
                from src.crew.tools import set_tool_context, clear_tool_context
                set_tool_context(self._discussion_id, agent.role_name)
            except Exception:
                pass
            try:
                return agent.respond_sync(ctx)
            finally:
                try:
                    from src.crew.tools import clear_tool_context
                    clear_tool_context()
                except Exception:
                    pass

        pool = ThreadPoolExecutor(max_workers=len(agents_to_call))
        future_to_agent = {
            pool.submit(_call_with_tool_context, agent, context): agent
            for agent in agents_to_call
        }
        pending = set(future_to_agent.keys())

        while pending:
            # Wait for next completion or timeout for interrupt polling
            done, pending = wait(
                pending, timeout=3.0, return_when=FIRST_COMPLETED,
            )

            for future in done:
                agent = future_to_agent[future]
                try:
                    response = future.result()
                except Exception as exc:
                    logger.warning("Agent %s failed: %s", agent.role, exc)
                    response = f"（{agent.role}暂时无法给出回复）"

                # Broadcast immediately as this agent finishes
                self._broadcast_status(agent.role, AgentStatus.SPEAKING)
                self._broadcast_message(agent.role, response)
                self._record_message(agent.role, response)
                self._broadcast_status(agent.role, AgentStatus.IDLE)

                results.append((agent.role, response))

            # Check for interrupt after processing completions
            if pending and interrupt_check and interrupt_check():
                interrupted = True
                logger.info(
                    "Discussion %s: agent parallel run interrupted, "
                    "%d/%d agents completed",
                    self._discussion_id,
                    len(results),
                    len(future_to_agent),
                )
                # Set remaining agents to idle
                for f in pending:
                    a = future_to_agent[f]
                    self._broadcast_status(a.role, AgentStatus.IDLE)
                break

        # Non-blocking shutdown when interrupted: background threads
        # complete on their own but we proceed immediately.
        # Normal path: wait for all threads to finish cleanly.
        pool.shutdown(wait=not interrupted)

        return results, interrupted

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
            if "summary" in task_name and ("主策划" in agent_role or self._lead_planner.role in agent_role):
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
                built_agents = [agent.build_agent() for agent in self._agents]
                logger.info("Discussion %s: %d agents, %d tasks", self._discussion_id, len(built_agents), len(tasks))

                crew = Crew(
                    agents=built_agents,
                    tasks=tasks,
                    process=Process.sequential,
                    verbose=verbose,
                    task_callback=task_callback,
                )

                result = crew.kickoff()
                logger.info("Discussion %s: crew.kickoff() completed", self._discussion_id)

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
                    loop = asyncio.new_event_loop()
                    try:
                        loop.run_until_complete(self._generate_visual_concepts(str(result)))
                    finally:
                        loop.close()
                except Exception as e:
                    logger.warning("Failed to generate visual concepts: %s", e)

            # Mark discussion as finished and clean up
            set_discussion_state(self._discussion_id, DiscussionState.FINISHED)
            cleanup_discussion_state(self._discussion_id)

            # Auto-generate discussion output from final result
            try:
                from src.admin.database import AdminDatabase
                adb = AdminDatabase()
                final_text = str(result)
                if final_text and len(final_text) > 50:
                    adb.create_discussion_output(
                        self._discussion_id,
                        title=f"讨论产出: {self._topic[:50]}",
                        content=final_text,
                        output_type="new_doc"
                    )
                    logger.info("Auto-generated discussion output for %s", self._discussion_id)
            except Exception as e:
                logger.warning("Failed to auto-generate output: %s", e)

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

    # ------------------------------------------------------------------
    # Orchestrated (dynamic speaker) mode - sync helpers
    # ------------------------------------------------------------------

    def _lead_planner_opening_sync(
        self,
        topic: str,
        attachment: str | None = None,
    ) -> str:
        """Generate Lead Planner's opening statement synchronously."""
        agent_list = [(a.role, a.goal) for a in self._discussion_agents]
        opening_prompt = self._lead_planner.create_opening_prompt(topic, attachment, agent_list=agent_list)
        history_context = self._load_history_context(topic)
        if history_context:
            opening_prompt += f"\n\n---\n参考历史信息：\n{history_context}\n---\n"

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
        result = crew.kickoff()
        return str(result)

    def _lead_planner_summary_sync(
        self,
        round_num: int,
        topic: str,
        context: str,
    ) -> str:
        """Generate Lead Planner's round summary synchronously.

        Args:
            round_num: Current round number.
            topic: The discussion topic.
            context: Windowed discussion context (not full history).
        """
        summary_prompt = self._lead_planner.create_round_summary_prompt(
            round_num, topic, agent_list=[(a.role, a.goal) for a in self._discussion_agents]
        )
        full_prompt = f"{summary_prompt}\n\n---\n讨论上下文：\n{context}"

        task = Task(
            description=full_prompt,
            expected_output=f"第{round_num}轮总结：共识、分歧、需深入的问题、下一轮发言人",
            agent=self._lead_planner.build_agent(),
        )
        crew = Crew(
            agents=[self._lead_planner.build_agent()],
            tasks=[task],
            process=Process.sequential,
        )
        result = crew.kickoff()
        output = self._sanitize_crew_output(str(result), "lead_planner_summary")
        return output or f"第{round_num}轮讨论已完成，暂无法生成总结。"

    def _lead_planner_final_decision_sync(
        self,
        topic: str,
        context: str,
    ) -> str:
        """Generate Lead Planner's final decision document synchronously.

        Args:
            topic: The discussion topic.
            context: Windowed discussion context (not full history).
        """
        final_prompt = self._lead_planner.create_final_decision_prompt(
            topic, agent_list=[(a.role, a.goal) for a in self._discussion_agents]
        )
        full_prompt = f"{final_prompt}\n\n---\n讨论上下文：\n{context}"

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
        result = crew.kickoff()
        output = self._sanitize_crew_output(str(result), "lead_planner_final")
        return output or "讨论已完成，暂无法生成决策文档。"

    def run_orchestrated(
        self,
        topic: str,
        max_rounds: int = 10,
        verbose: bool = False,
        attachment: str | None = None,
        auto_pause_interval: int = 5,
    ) -> str:
        """Run a dynamically orchestrated discussion.

        Unlike run() which pre-creates all tasks and uses fixed rotation,
        this method runs round-by-round with the Lead Planner deciding
        who speaks each round, enabling natural conversation flow.

        Args:
            topic: The design topic to discuss.
            max_rounds: Maximum number of discussion rounds.
            verbose: Whether to print verbose output.
            attachment: Optional markdown attachment content.
            auto_pause_interval: Auto-pause every N rounds (0=disabled).

        Returns:
            The final discussion result/decision document.
        """
        from src.crew.mention_parser import parse_next_speakers

        # Initialize discussion record
        self._init_discussion(topic)
        self._auto_pause_interval = auto_pause_interval
        self._total_rounds = max_rounds

        # Initialize discussion state for pause/resume
        set_discussion_state(self._discussion_id, DiscussionState.RUNNING)
        self._abort_reason = None

        trace_metadata = self._prepare_trace_metadata(topic, max_rounds)
        trace_span: Any | None = None

        try:
            with start_trace_context(
                name="discussion_orchestrated",
                session_id=self._discussion_id,
                metadata=trace_metadata,
            ) as span:
                trace_span = span

                # --- Phase 0: Lead Planner Opening ---
                self._broadcast_status(self._lead_planner.role, AgentStatus.THINKING)
                opening = self._lead_planner_opening_sync(topic, attachment)
                opening = sanitize_speakers_in_text(opening, known_roles=[a.role for a in self._discussion_agents])

                self._broadcast_status(self._lead_planner.role, AgentStatus.SPEAKING)
                self._broadcast_message(self._lead_planner.role, opening)
                self._record_message(self._lead_planner.role, opening)
                self._broadcast_status(self._lead_planner.role, AgentStatus.IDLE)

                # Windowed context: track current round messages instead of
                # accumulating all history into a single growing string.
                round_num = 0
                last_summary: str | None = None
                current_round_msgs: list[tuple[str, str]] = []
                pending_injected: list[dict] = []

                # --- Phase 1-N: Dynamic Discussion Rounds ---
                while round_num < max_rounds:
                    round_num += 1
                    self._current_round = round_num
                    current_round_msgs = []
                    pending_injected = []

                    # Determine who speaks this round
                    source_text = opening if round_num == 1 else (last_summary or opening)
                    next_speakers = parse_next_speakers(source_text, known_roles=[a.role for a in self._discussion_agents])

                    # Pause if the speakers block requests producer turn
                    if PRODUCER_ROLE in (next_speakers or []):
                        self._wait_for_producer_turn()
                        if self._abort_reason:
                            raise DiscussionTimeoutError(self._abort_reason)
                        next_speakers = [s for s in next_speakers if s != PRODUCER_ROLE] or None

                    # Filter agents to those who should speak
                    if next_speakers:
                        agents_to_call = [
                            agent for agent in self._discussion_agents
                            if agent.role in next_speakers
                        ]
                    else:
                        agents_to_call = list(self._discussion_agents)

                    # Fallback: if parsing missed everything, all agents respond
                    if not agents_to_call:
                        agents_to_call = list(self._discussion_agents)

                    # Broadcast who is participating this round
                    participating_names = [a.role for a in agents_to_call]
                    self._broadcast_discussion_event(
                        f"第{round_num}轮：{', '.join(participating_names)} 参与讨论"
                    )
                    logger.info(
                        "Discussion %s round %d: speakers=%s",
                        self._discussion_id,
                        round_num,
                        participating_names,
                    )

                    # Build windowed context for agents
                    agent_context = self._build_windowed_context(
                        topic, opening, current_round_msgs,
                        last_summary=last_summary,
                        summary_window=3,
                    )

                    # All agents think in parallel, broadcast as each finishes
                    round_responses, _ = self._run_agents_parallel_sync(
                        agents_to_call, agent_context,
                    )
                    for role, response in round_responses:
                        current_round_msgs.append((role, response))

                    # Check for pause/intervention
                    injected_messages = self._check_pause_and_wait()
                    if self._abort_reason:
                        raise DiscussionTimeoutError(self._abort_reason)
                    if injected_messages:
                        self._inject_user_messages(injected_messages)
                        pending_injected.extend(injected_messages)

                    # Lead Planner summarizes this round (larger context window)
                    self._broadcast_status(self._lead_planner.role, AgentStatus.THINKING)
                    lp_context = self._build_windowed_context(
                        topic, opening, current_round_msgs,
                        last_summary=last_summary,
                        injected_messages=pending_injected or None,
                        summary_window=3,
                        for_lead_planner=True,
                    )
                    latest_summary = self._lead_planner_summary_sync(round_num, topic, lp_context)
                    last_summary = latest_summary

                    self._broadcast_status(self._lead_planner.role, AgentStatus.SPEAKING)
                    self._broadcast_message(self._lead_planner.role, latest_summary)
                    self._record_message(self._lead_planner.role, latest_summary)
                    self._broadcast_status(self._lead_planner.role, AgentStatus.IDLE)

                    # Generate and broadcast round summary
                    round_summary = self._generate_round_summary(round_num, latest_summary)
                    self._save_round_summary(round_summary)
                    self._broadcast_round_summary(round_summary)

                    # Trigger background document organization
                    self._trigger_round_organize(round_num)

                    # Parse discussion status
                    status, questions = parse_discussion_status(latest_summary)
                    self._discussion_status = status
                    self._pending_questions = questions

                    if status == DiscussionStatus.SUFFICIENT:
                        logger.info(
                            "Discussion %s: sufficient after round %d",
                            self._discussion_id,
                            round_num,
                        )
                        break

                    # Auto-pause check
                    if (
                        self._auto_pause_interval > 0
                        and round_num % self._auto_pause_interval == 0
                        and round_num < max_rounds
                    ):
                        logger.info(
                            "Auto-pausing discussion %s at round %d (interval=%d)",
                            self._discussion_id,
                            round_num,
                            self._auto_pause_interval,
                        )
                        set_discussion_state(
                            self._discussion_id, DiscussionState.PAUSED
                        )
                        self._broadcast_discussion_event(
                            f"discussion_auto_paused:已完成第{round_num}轮讨论，等待继续"
                        )
                        injected = self._check_pause_and_wait()
                        if self._abort_reason:
                            raise DiscussionTimeoutError(self._abort_reason)
                        if injected:
                            self._inject_user_messages(injected)
                            pending_injected.extend(injected)

                    self._broadcast_discussion_event(f"第{round_num}轮讨论完成")

                # --- Final Phase: Lead Planner Decision ---
                self._broadcast_discussion_event("正在生成最终决策文档...")
                self._broadcast_status(self._lead_planner.role, AgentStatus.THINKING)
                final_context = self._build_windowed_context(
                    topic, opening, current_round_msgs,
                    last_summary=last_summary,
                    injected_messages=pending_injected or None,
                    summary_window=5,
                    for_lead_planner=True,
                )
                final_decision = self._lead_planner_final_decision_sync(topic, final_context)

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
                    loop = asyncio.new_event_loop()
                    try:
                        loop.run_until_complete(
                            self._generate_visual_concepts(final_decision)
                        )
                    finally:
                        loop.close()
                except Exception as e:
                    logger.warning("Failed to generate visual concepts: %s", e)

            # Cleanup
            set_discussion_state(self._discussion_id, DiscussionState.FINISHED)
            cleanup_discussion_state(self._discussion_id)

            for agent in self._agents:
                self._broadcast_status(agent.role, AgentStatus.IDLE)
            self._broadcast_discussion_event("discussion_completed")

            return final_decision

        except Exception as exc:
            self._finalize_trace(trace_span, error=exc)
            self._broadcast_error(str(exc))
            self._broadcast_discussion_event("discussion_failed")
            self._save_discussion()
            cleanup_discussion_state(self._discussion_id)
            for agent in self._agents:
                self._broadcast_status(agent.role, AgentStatus.IDLE)
            raise

    def extend_orchestrated(
        self,
        topic: str,
        follow_up: str = "",
        additional_rounds: int = 10,
    ) -> str:
        """Extend a completed discussion with additional rounds.

        Loads existing discussion from memory, optionally adds a follow-up
        message, then continues with more rounds of discussion.

        Args:
            topic: The original discussion topic.
            follow_up: Optional user follow-up question.
            additional_rounds: Number of additional rounds.

        Returns:
            The final decision document.
        """
        from src.crew.mention_parser import parse_next_speakers

        # Load existing discussion from memory
        stored = self._discussion_memory.load(self._discussion_id)
        if stored is None:
            raise ValueError(f"Discussion {self._discussion_id} not found in memory")

        # Restore state
        self._current_discussion = stored
        self._messages = list(stored.messages)
        self._message_sequence = len(self._messages)
        self._unsaved_message_count = 0

        # Determine starting round from existing summaries
        start_round = (
            len(stored.round_summaries) + 1 if stored.round_summaries else 1
        )

        # Reconstruct opening from first lead planner message (if available)
        opening = ""
        for msg in stored.messages:
            if msg.agent_role in ("主策划", "lead_planner", self._lead_planner.role, self._moderator_role):
                opening = msg.content
                break

        # Inject follow-up as user message
        if follow_up:
            self._record_message("User", follow_up)
            self._broadcast_message("User", follow_up)

        # Set up state
        self._auto_pause_interval = 0
        self._total_rounds = start_round + additional_rounds
        set_discussion_state(self._discussion_id, DiscussionState.RUNNING)
        self._abort_reason = None

        trace_metadata = self._prepare_trace_metadata(topic, additional_rounds)
        trace_span: Any | None = None
        end_round = start_round + additional_rounds - 1

        try:
            with start_trace_context(
                name="discussion_extend",
                session_id=self._discussion_id,
                metadata=trace_metadata,
            ) as span:
                trace_span = span
                round_num = start_round - 1
                last_summary: str | None = None
                current_round_msgs: list[tuple[str, str]] = []
                pending_injected: list[dict] = []

                # Use follow-up as initial context for speaker parsing
                if follow_up:
                    pending_injected.append({"content": follow_up})

                while round_num < end_round:
                    round_num += 1
                    self._current_round = round_num
                    current_round_msgs = []
                    round_injected: list[dict] = []

                    # Determine speakers
                    if round_num == start_round and follow_up:
                        source_text = follow_up
                    elif last_summary:
                        source_text = last_summary
                    else:
                        source_text = opening[-2000:] if opening else topic

                    next_speakers = parse_next_speakers(source_text, known_roles=[a.role for a in self._discussion_agents])

                    # Pause if the speakers block requests producer turn
                    if PRODUCER_ROLE in (next_speakers or []):
                        self._wait_for_producer_turn()
                        if self._abort_reason:
                            raise DiscussionTimeoutError(self._abort_reason)
                        next_speakers = [s for s in next_speakers if s != PRODUCER_ROLE] or None

                    agents_to_call = (
                        [a for a in self._discussion_agents if a.role in next_speakers]
                        if next_speakers
                        else list(self._discussion_agents)
                    )
                    if not agents_to_call:
                        agents_to_call = list(self._discussion_agents)

                    participating = [a.role for a in agents_to_call]
                    self._broadcast_discussion_event(
                        f"第{round_num}轮：{', '.join(participating)} 参与讨论"
                    )
                    logger.info(
                        "Extend %s round %d: speakers=%s",
                        self._discussion_id, round_num, participating,
                    )

                    # Build windowed context for agents
                    agent_context = self._build_windowed_context(
                        topic, opening, current_round_msgs,
                        last_summary=last_summary,
                        injected_messages=pending_injected or None,
                        summary_window=3,
                    )

                    # All agents think in parallel, broadcast as each finishes
                    round_responses, _ = self._run_agents_parallel_sync(
                        agents_to_call, agent_context,
                    )
                    for role, response in round_responses:
                        current_round_msgs.append((role, response))

                    # Pause/intervention check
                    injected = self._check_pause_and_wait()
                    if self._abort_reason:
                        raise DiscussionTimeoutError(self._abort_reason)
                    if injected:
                        self._inject_user_messages(injected)
                        round_injected.extend(injected)

                    # Lead Planner summary (larger context window)
                    self._broadcast_status(self._lead_planner.role, AgentStatus.THINKING)
                    lp_context = self._build_windowed_context(
                        topic, opening, current_round_msgs,
                        last_summary=last_summary,
                        injected_messages=(pending_injected + round_injected) or None,
                        summary_window=3,
                        for_lead_planner=True,
                    )
                    latest_summary = self._lead_planner_summary_sync(
                        round_num, topic, lp_context
                    )
                    last_summary = latest_summary
                    pending_injected = []  # Clear after first round

                    self._broadcast_status(self._lead_planner.role, AgentStatus.SPEAKING)
                    self._broadcast_message(self._lead_planner.role, latest_summary)
                    self._record_message(self._lead_planner.role, latest_summary)
                    self._broadcast_status(self._lead_planner.role, AgentStatus.IDLE)

                    # Round summary + doc organize
                    round_summary = self._generate_round_summary(round_num, latest_summary)
                    self._save_round_summary(round_summary)
                    self._broadcast_round_summary(round_summary)
                    self._trigger_round_organize(round_num)

                    # Check status
                    status, questions = parse_discussion_status(latest_summary)
                    self._discussion_status = status
                    self._pending_questions = questions

                    if status == DiscussionStatus.SUFFICIENT:
                        logger.info(
                            "Extend %s: sufficient after round %d",
                            self._discussion_id, round_num,
                        )
                        break

                    self._broadcast_discussion_event(f"第{round_num}轮讨论完成")

                # Final decision
                self._broadcast_discussion_event("正在生成最终决策文档...")
                self._broadcast_status(self._lead_planner.role, AgentStatus.THINKING)
                final_context = self._build_windowed_context(
                    topic, opening, current_round_msgs,
                    last_summary=last_summary,
                    summary_window=5,
                    for_lead_planner=True,
                )
                final_decision = self._lead_planner_final_decision_sync(topic, final_context)
                self._broadcast_status(self._lead_planner.role, AgentStatus.SPEAKING)
                self._broadcast_message(self._lead_planner.role, final_decision)
                self._record_message(self._lead_planner.role, final_decision)
                self._broadcast_status(self._lead_planner.role, AgentStatus.IDLE)

                self._finalize_trace(trace_span, result=final_decision)

            self._save_discussion(summary=final_decision)

            try:
                self._save_decisions(final_decision, topic)
            except Exception as e:
                logger.warning("Failed to save decisions: %s", e)

            set_discussion_state(self._discussion_id, DiscussionState.FINISHED)
            cleanup_discussion_state(self._discussion_id)

            for agent in self._agents:
                self._broadcast_status(agent.role, AgentStatus.IDLE)
            self._broadcast_discussion_event("discussion_completed")

            return final_decision

        except Exception as exc:
            self._finalize_trace(trace_span, error=exc)
            self._broadcast_error(str(exc))
            self._broadcast_discussion_event("discussion_failed")
            self._save_discussion()
            cleanup_discussion_state(self._discussion_id)
            for agent in self._agents:
                self._broadcast_status(agent.role, AgentStatus.IDLE)
            raise

    def extend_document_centric(
        self,
        topic: str,
        follow_up: str = "",
        additional_rounds: int = 10,
    ) -> str:
        """Extend a document-centric discussion with additional rounds.

        Restores saved doc_plan and continues discussing pending sections.

        Args:
            topic: The original discussion topic.
            follow_up: Optional user follow-up direction.
            additional_rounds: Number of additional rounds.

        Returns:
            Result string (may start with "STOPPED:" if rounds exhausted again).
        """
        from src.models.doc_plan import DocPlan
        from src.agents.doc_writer import DocWriter
        from src.crew.mention_parser import parse_next_speakers

        # Load existing discussion from memory
        stored = self._discussion_memory.load(self._discussion_id)
        if stored is None:
            raise ValueError(f"Discussion {self._discussion_id} not found in memory")

        # Restore state
        self._current_discussion = stored
        self._messages = list(stored.messages)
        self._message_sequence = len(self._messages)
        self._unsaved_message_count = 0

        # Restore doc_plan
        if not stored.doc_plan:
            raise ValueError(f"Discussion {self._discussion_id} has no doc_plan, cannot extend as document-centric")
        doc_plan = DocPlan.from_dict(stored.doc_plan)
        self._doc_plan = doc_plan

        # Restore DocWriter
        docs_dir = Path(self._data_dir) / self._project_id / self._discussion_id / "docs"
        self._doc_writer = DocWriter(llm=self._llm, docs_dir=docs_dir)

        # Set up state
        self._auto_pause_interval = 0
        self._total_rounds = additional_rounds
        set_discussion_state(self._discussion_id, DiscussionState.RUNNING)
        self._abort_reason = None

        # Inject follow-up if provided — both as a visible message
        # and into _producer_digest_pending so that _build_section_context
        # includes it in the next round's agent prompt.
        if follow_up:
            self._record_message("User", follow_up)
            self._broadcast_message("User", follow_up)
            self._broadcast_discussion_event(f"用户追加方向：{follow_up[:100]}")
            self._producer_digest_pending = f"制作人追加方向：{follow_up}"

        trace_metadata = self._prepare_trace_metadata(topic, additional_rounds)
        trace_span: Any | None = None

        try:
            with start_trace_context(
                name="discussion_extend_document_centric",
                session_id=self._discussion_id,
                metadata=trace_metadata,
            ) as span:
                trace_span = span

                self._broadcast_doc_plan_event(doc_plan)

                # Main loop: section-by-section
                for round_num in range(1, additional_rounds + 1):
                    self._current_round = round_num

                    # Pick next section
                    file_plan, section = self._pick_next_section(doc_plan)
                    if file_plan is None or section is None:
                        logger.info("All sections completed at extend round %d", round_num)
                        break

                    section.status = "in_progress"
                    doc_plan.current_section_id = section.id
                    self._broadcast_section_focus(section.id, section.title, file_plan.filename)
                    self._broadcast_discussion_event(
                        f"追加第{round_num}轮：聚焦章节「{section.title}」({file_plan.filename})"
                    )

                    # Read current section content
                    section_content = self._doc_writer.read_section(file_plan.filename, section.id)

                    # Lead Planner opens section discussion
                    self._broadcast_status(self._lead_planner.role, AgentStatus.THINKING)
                    opening = self._lead_planner_section_opening(section, section_content, round_num)
                    opening = sanitize_speakers_in_text(opening, known_roles=[a.role for a in self._discussion_agents])
                    self._broadcast_status(self._lead_planner.role, AgentStatus.SPEAKING)
                    self._broadcast_message(self._lead_planner.role, opening)
                    self._record_message(self._lead_planner.role, opening)
                    self._broadcast_status(self._lead_planner.role, AgentStatus.IDLE)

                    # Determine speakers
                    next_speakers = parse_next_speakers(opening, known_roles=[a.role for a in self._discussion_agents])
                    agents_to_call = (
                        [a for a in self._discussion_agents if a.role in next_speakers]
                        if next_speakers else list(self._discussion_agents)
                    )
                    if not agents_to_call:
                        agents_to_call = list(self._discussion_agents)

                    # Agents discuss in parallel
                    context = self._build_section_context(topic, doc_plan, section, section_content, opening)
                    round_responses, _ = self._run_agents_parallel_sync(agents_to_call, context)

                    discussion_content = f"主策划：{opening}\n\n"
                    for role, resp in round_responses:
                        discussion_content += f"{role}：{resp}\n\n"

                    # Lead Planner summarizes
                    self._broadcast_status(self._lead_planner.role, AgentStatus.THINKING)
                    summary = self._lead_planner_section_summary(section.title, round_num, discussion_content)
                    self._broadcast_status(self._lead_planner.role, AgentStatus.SPEAKING)
                    self._broadcast_message(self._lead_planner.role, summary)
                    self._record_message(self._lead_planner.role, summary)
                    self._broadcast_status(self._lead_planner.role, AgentStatus.IDLE)

                    # Update sliding window of summaries
                    self._section_summaries.append(f"追加第{round_num}轮({section.title}): {summary[:500]}")
                    if len(self._section_summaries) > 2:
                        self._section_summaries.pop(0)

                    # Accumulate per-section decisions for compact agent context
                    if summary:
                        self._section_decisions.setdefault(section.id, []).append(
                            f"追加第{round_num}轮: {summary[:500]}"
                        )

                    # Process agenda directives from summary
                    self._process_agenda_directives(summary, section)
                    self._process_doc_restructure(summary, doc_plan, section)

                    # Check section still exists after possible restructure
                    f_check, s_check = doc_plan.get_section(section.id)
                    if f_check is None:
                        logger.info("Section %s removed after restructure, skipping update", section.id)
                        if self._current_discussion:
                            self._current_discussion.doc_plan = doc_plan.to_dict()
                            self._incremental_save()
                        self._broadcast_doc_plan_event(doc_plan)
                        continue

                    if "章节完成" in summary:
                        section.status = "completed"

                    # DocWriter updates the section
                    self._broadcast_status(self._lead_planner.role, AgentStatus.WRITING, f"正在更新「{section.title}」")
                    updated = self._doc_writer.update_section(
                        file_plan.filename, section.id, discussion_content, section.title,
                    )
                    self._broadcast_section_update(file_plan.filename, section.id, updated)
                    self._broadcast_status(self._lead_planner.role, AgentStatus.IDLE)

                    # Round summary
                    round_summary = self._generate_round_summary(round_num, summary)
                    self._save_round_summary(round_summary)
                    self._broadcast_round_summary(round_summary)

                    # Pause/intervention check
                    injected = self._check_pause_and_wait()
                    if self._abort_reason:
                        raise DiscussionTimeoutError(self._abort_reason)
                    if injected:
                        self._inject_user_messages(injected)
                        for msg in injected:
                            content = msg.get("content", "")
                            if content.startswith("focus:"):
                                sid = content.split(":", 1)[1].strip()
                                doc_plan.current_section_id = sid
                        digest = self._lead_planner_digest_intervention(injected, section)
                        assessment = self._assess_intervention_impact(digest, doc_plan, section)
                        self._execute_assessment_actions(assessment, doc_plan)
                        self._lead_planner_post_intervention_guidance(digest, assessment)

                    self._broadcast_discussion_event(f"追加第{round_num}轮讨论完成")

                    # Save doc_plan state
                    if self._current_discussion:
                        self._current_discussion.doc_plan = doc_plan.to_dict()
                        self._incremental_save()
                    self._broadcast_doc_plan_event(doc_plan)

                # Check result
                all_done = doc_plan.all_sections_completed()

                if all_done:
                    # Run holistic review
                    for review_round in range(2):
                        review = self._lead_planner_holistic_review(doc_plan, self._agenda)
                        conclusion = review.get("conclusion", "APPROVED")
                        if conclusion == "APPROVED":
                            break
                        if conclusion in ("NEEDS_REVISION", "NEEDS_NEW_TOPIC", "NEEDS_RESTRUCTURE"):
                            self._execute_review_actions(review, doc_plan, self._agenda)
                        else:
                            break

                # Save doc_plan final state
                if self._current_discussion:
                    self._current_discussion.doc_plan = doc_plan.to_dict()

                if all_done:
                    self._finalize_trace(trace_span, result="文档驱动讨论完成")
                else:
                    pending = sum(1 for f in doc_plan.files for s in f.sections if s.status != "completed")
                    completed = sum(1 for f in doc_plan.files for s in f.sections if s.status == "completed")
                    self._finalize_trace(trace_span, result=f"轮次耗尽：已完成{completed}，待讨论{pending}")

            # Save discussion
            if all_done:
                self._save_discussion(summary="文档驱动讨论完成")
            else:
                pending = sum(1 for f in doc_plan.files for s in f.sections if s.status != "completed")
                completed = sum(1 for f in doc_plan.files for s in f.sections if s.status == "completed")
                stop_msg = f"已完成 {completed} 个章节的讨论，仍有 {pending} 个章节待讨论。可继续讨论以完成剩余章节。"
                self._broadcast_discussion_event(stop_msg)
                self._save_discussion(summary=stop_msg)

            set_discussion_state(self._discussion_id, DiscussionState.FINISHED)
            cleanup_discussion_state(self._discussion_id)

            for agent in self._agents:
                self._broadcast_status(agent.role, AgentStatus.IDLE)
            self._broadcast_discussion_event("discussion_completed")

            if all_done:
                return "文档驱动讨论完成"
            else:
                return f"STOPPED:{stop_msg}"

        except DiscussionTimeoutError:
            self._save_discussion()
            cleanup_discussion_state(self._discussion_id)
            for agent in self._agents:
                self._broadcast_status(agent.role, AgentStatus.IDLE)
            self._broadcast_discussion_event("discussion_completed")
            return "讨论因暂停超时结束"
        except Exception as exc:
            self._finalize_trace(trace_span, error=exc)
            self._broadcast_error(str(exc))
            self._broadcast_discussion_event("discussion_failed")
            self._save_discussion()
            cleanup_discussion_state(self._discussion_id)
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
        opening_prompt = self._lead_planner.create_opening_prompt(
            topic, attachment, agent_list=[(a.role, a.goal) for a in self._discussion_agents]
        )
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
            context: Windowed discussion context (not full history).

        Returns:
            The Lead Planner's summary for this round.
        """
        summary_prompt = self._lead_planner.create_round_summary_prompt(
            round_num, topic, agent_list=[(a.role, a.goal) for a in self._discussion_agents]
        )
        full_prompt = f"{summary_prompt}\n\n---\n讨论上下文：\n{context}"

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
            context: Windowed discussion context (not full history).

        Returns:
            The Lead Planner's final decision document.
        """
        final_prompt = self._lead_planner.create_final_decision_prompt(
            topic, agent_list=[(a.role, a.goal) for a in self._discussion_agents]
        )
        full_prompt = f"{final_prompt}\n\n---\n讨论上下文：\n{context}"

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
                opening = sanitize_speakers_in_text(opening, known_roles=[a.role for a in self._discussion_agents])

                self._broadcast_status(self._lead_planner.role, AgentStatus.SPEAKING)
                self._broadcast_message(self._lead_planner.role, opening)
                self._record_message(self._lead_planner.role, opening)
                self._broadcast_status(self._lead_planner.role, AgentStatus.IDLE)

                # Windowed context: track current round messages instead of
                # accumulating all history into a single growing string.
                round_num = 0
                last_summary: str | None = None
                current_round_msgs: list[tuple[str, str]] = []
                pending_injected: list[dict] = []
                pending_producer: list[tuple[str, str]] = []

                # Phase 1-N: Dynamic discussion rounds
                while round_num < max_rounds:
                    round_num += 1
                    self._current_round = round_num
                    current_round_msgs = []
                    pending_injected = []
                    pending_producer = []

                    # Parse mentioned roles (from latest summary or opening)
                    source_text = opening if round_num == 1 else (last_summary or opening)
                    mentioned_roles = parse_mentioned_roles(source_text)

                    # Build windowed context for agents
                    agent_context = self._build_windowed_context(
                        topic, opening, current_round_msgs,
                        last_summary=last_summary,
                        summary_window=3,
                    )

                    # Run parallel responses from mentioned agents
                    responses = await self._run_parallel_responses(mentioned_roles, agent_context)

                    # Record and broadcast responses
                    for role, response in responses:
                        self._broadcast_status(role, AgentStatus.SPEAKING)
                        self._broadcast_message(role, response)
                        self._record_message(role, response)
                        self._broadcast_status(role, AgentStatus.IDLE)
                        current_round_msgs.append((role, response))

                    # Check for pause/intervention
                    injected_messages = self._check_pause_and_wait()
                    if self._abort_reason:
                        raise DiscussionTimeoutError(self._abort_reason)
                    if injected_messages:
                        self._inject_user_messages(injected_messages)
                        pending_injected.extend(injected_messages)

                    # Check for producer messages (制作人即时消息)
                    producer_msgs = self._check_producer_messages()
                    if producer_msgs:
                        self._broadcast_status(self._lead_planner.role, AgentStatus.THINKING)
                        # Use windowed context for digest (replaces old ctx_tail approach)
                        digest_context = self._build_windowed_context(
                            topic, opening, current_round_msgs,
                            last_summary=last_summary,
                            summary_window=2,
                        )
                        digest = self._digest_producer_messages_dynamic(producer_msgs, digest_context)
                        self._broadcast_status(self._lead_planner.role, AgentStatus.IDLE)

                        for msg in producer_msgs:
                            pending_producer.append((msg["content"], digest["digest_summary"]))

                        # Broadcast digest event
                        try:
                            from src.api.websocket.events import create_producer_digest_event
                            digest_event = create_producer_digest_event(
                                self._discussion_id,
                                digest_summary=digest["digest_summary"],
                                action=digest["action"],
                                guidance=digest["guidance"],
                            )
                            broadcast_sync(digest_event.to_dict(), discussion_id=self._discussion_id)
                        except Exception:
                            pass

                    # Lead Planner summarizes this round (larger context window)
                    self._broadcast_status(self._lead_planner.role, AgentStatus.THINKING)
                    lp_context = self._build_windowed_context(
                        topic, opening, current_round_msgs,
                        last_summary=last_summary,
                        injected_messages=pending_injected or None,
                        producer_messages=pending_producer or None,
                        summary_window=3,
                        for_lead_planner=True,
                    )
                    summary = await self._lead_planner_summary(round_num, topic, lp_context)
                    last_summary = summary

                    self._broadcast_status(self._lead_planner.role, AgentStatus.SPEAKING)
                    self._broadcast_message(self._lead_planner.role, summary)
                    self._record_message(self._lead_planner.role, summary)
                    self._broadcast_status(self._lead_planner.role, AgentStatus.IDLE)

                    # Save round summary (used by _build_windowed_context for history)
                    round_summary_data = self._generate_round_summary(round_num, summary)
                    self._save_round_summary(round_summary_data)
                    self._broadcast_round_summary(round_summary_data)

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
                final_context = self._build_windowed_context(
                    topic, opening, current_round_msgs,
                    last_summary=last_summary,
                    injected_messages=pending_injected or None,
                    producer_messages=pending_producer or None,
                    summary_window=5,
                    for_lead_planner=True,
                )
                final_decision = await self._lead_planner_final_decision(topic, final_context)

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

    # ------------------------------------------------------------------
    # Document-centric mode
    # ------------------------------------------------------------------

    def _generate_doc_plan(self, topic: str, attachment: str | None = None):
        """Generate a DocPlan via LLM."""
        from src.models.doc_plan import DocPlan, FilePlan, SectionPlan

        prompt = self._lead_planner.create_doc_plan_prompt(topic, attachment)

        task = Task(
            description=prompt,
            expected_output="JSON 格式的文档规划",
            agent=self._lead_planner.build_agent(),
        )
        crew = Crew(
            agents=[self._lead_planner.build_agent()],
            tasks=[task],
            process=Process.sequential,
        )
        result = crew.kickoff()
        raw = str(result)

        # Extract JSON from response
        json_match = re.search(r"```json\s*\n(.*?)\n```", raw, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find bare JSON object
            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            json_str = json_match.group(0) if json_match else raw

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning("Failed to parse doc plan JSON, creating fallback plan")
            data = {
                "files": [{
                    "filename": f"{topic[:20]}.md",
                    "title": topic,
                    "sections": [
                        {"id": "s1", "title": "概述", "description": "系统总体概述"},
                        {"id": "s2", "title": "核心设计", "description": "核心设计方案"},
                        {"id": "s3", "title": "实现细节", "description": "具体实现细节"},
                    ],
                }],
            }

        # Build DocPlan from parsed data
        files = []
        section_counter = 0
        for f_data in data.get("files", []):
            sections = []
            for s_data in f_data.get("sections", []):
                section_counter += 1
                sid = s_data.get("id", f"s{section_counter}")
                sections.append(SectionPlan(
                    id=sid,
                    title=s_data.get("title", f"章节{section_counter}"),
                    description=s_data.get("description", ""),
                ))
            files.append(FilePlan(
                filename=f_data.get("filename", f"文档{section_counter}.md"),
                title=f_data.get("title", "未命名文档"),
                sections=sections,
            ))

        doc_plan = DocPlan(
            discussion_id=self._discussion_id,
            topic=topic,
            files=files,
        )
        logger.info("Generated doc plan: %d files, %d sections",
                     len(files), sum(len(f.sections) for f in files))
        return doc_plan

    def _broadcast_doc_plan_event(self, doc_plan) -> None:
        """Broadcast doc_plan via WebSocket."""
        if self._discussion_id is None:
            return
        try:
            from src.api.websocket.events import create_doc_plan_event
            event = create_doc_plan_event(self._discussion_id, doc_plan.to_dict())
            broadcast_sync(event.to_dict(), discussion_id=self._discussion_id)
        except Exception as exc:
            logger.debug("Failed to broadcast doc plan: %s", exc)

    def _broadcast_section_focus(self, section_id: str, section_title: str, filename: str) -> None:
        """Broadcast section focus event."""
        if self._discussion_id is None:
            return
        try:
            from src.api.websocket.events import create_section_focus_event
            event = create_section_focus_event(self._discussion_id, section_id, section_title, filename)
            broadcast_sync(event.to_dict(), discussion_id=self._discussion_id)
        except Exception as exc:
            logger.debug("Failed to broadcast section focus: %s", exc)

    def _broadcast_section_update(self, filename: str, section_id: str, content: str) -> None:
        """Broadcast section update event."""
        if self._discussion_id is None:
            return
        try:
            from src.api.websocket.events import create_section_update_event
            event = create_section_update_event(self._discussion_id, filename, section_id, content)
            broadcast_sync(event.to_dict(), discussion_id=self._discussion_id)
        except Exception as exc:
            logger.debug("Failed to broadcast section update: %s", exc)

    def _pick_next_section(self, doc_plan):
        """Pick the next section to discuss."""
        # If current_section_id is set (user override), use it
        if doc_plan.current_section_id:
            f, s = doc_plan.get_section(doc_plan.current_section_id)
            if f and s and s.status != "completed":
                return f, s
            # Clear override if invalid or completed
            doc_plan.current_section_id = None

        return doc_plan.get_next_pending_section()

    def _lead_planner_section_opening(self, section, section_content: str, round_num: int) -> str:
        """Generate Lead Planner's opening for a section discussion."""
        # Use decisions summary instead of full content for later rounds
        decisions = self._section_decisions.get(section.id)
        if decisions and len(section_content or "") > 1500:
            content_for_prompt = (
                f"（章节已有 {len(section_content)} 字，以下是各轮关键决策）\n"
                + "\n".join(decisions[-5:])
            )
        else:
            content_for_prompt = section_content
        prompt = self._lead_planner.create_section_discussion_prompt(
            section.title, section.description, content_for_prompt, round_num,
            agent_list=[(a.role, a.goal) for a in self._discussion_agents],
        )

        # Add recent summaries context
        if self._section_summaries:
            prompt += "\n\n---\n最近讨论摘要：\n" + "\n".join(self._section_summaries) + "\n---"

        # Inject pending producer feedback so the opening addresses it.
        # NOTE: Do NOT clear _producer_digest_pending here — let
        # _build_section_context also inject it into agents' context so
        # they see the feedback directly, not only via the opening text.
        if self._producer_digest_pending:
            prompt += (
                f"\n\n⚠️ 制作人反馈（你必须在开场中回应并纳入讨论）：\n"
                f"{self._producer_digest_pending}"
            )

        task = Task(
            description=prompt,
            expected_output=f"引导讨论章节「{section.title}」的问题和发言人指定",
            agent=self._lead_planner.build_agent(),
        )
        crew = Crew(
            agents=[self._lead_planner.build_agent()],
            tasks=[task],
            process=Process.sequential,
        )
        result = crew.kickoff()
        output = self._sanitize_crew_output(str(result), "lead_planner_section_opening")
        return output or f"请大家讨论章节「{section.title}」：{section.description}"

    def _lead_planner_section_summary(self, section_title: str, round_num: int, discussion_content: str) -> str:
        """Generate section discussion summary via Lead Planner."""
        summary_prompt = self._lead_planner.create_section_summary_prompt(
            section_title, round_num,
            agent_list=[(a.role, a.goal) for a in self._discussion_agents],
        )
        full_prompt = f"{summary_prompt}\n\n---\n讨论记录：\n{discussion_content}"

        task = Task(
            description=full_prompt,
            expected_output=f"章节「{section_title}」第{round_num}轮总结",
            agent=self._lead_planner.build_agent(),
        )
        crew = Crew(
            agents=[self._lead_planner.build_agent()],
            tasks=[task],
            process=Process.sequential,
        )
        result = crew.kickoff()
        output = self._sanitize_crew_output(str(result), "lead_planner_section_summary")
        return output or f"第{round_num}轮讨论已完成，暂无法生成总结。"

    def _get_section_context_for_agents(self, section, section_content: str) -> str:
        """Return compact section context for agent prompts.

        For short sections (<=1500 chars), returns the full content.
        For longer sections, returns the accumulated per-section decision
        summaries instead — preserving semantics without prompt bloat.
        """
        if not section_content:
            return ""
        if len(section_content) <= 1500:
            return f"\n当前章节内容：\n{section_content}"
        # Use accumulated decisions if available
        decisions = self._section_decisions.get(section.id)
        if decisions:
            decisions_text = "\n".join(decisions[-5:])  # keep last 5 rounds
            return (
                f"\n本章节已有 {len(section_content)} 字文档内容，以下是各轮关键决策：\n"
                f"{decisions_text}"
            )
        # Fallback: first time seeing a long section (e.g. pre-populated doc)
        return f"\n当前章节内容：\n{section_content}"

    def _build_section_context(self, topic: str, doc_plan, section, section_content: str, opening: str) -> str:
        """Build context string for agent discussion of a section."""
        parts = [
            f"议题：{topic}",
            f"\n当前讨论章节：{section.title}",
            f"章节目标：{section.description}",
        ]
        section_ctx = self._get_section_context_for_agents(section, section_content)
        if section_ctx:
            parts.append(section_ctx)
        if self._section_summaries:
            parts.append("\n最近讨论摘要：")
            parts.extend(self._section_summaries)
        # Inject pending producer message digest from previous round
        if self._producer_digest_pending:
            parts.append(f"\n⚠️ 制作人反馈（请务必回应）：\n{self._producer_digest_pending}")
            self._producer_digest_pending = None
        parts.append(f"\n主策划引导：\n{opening}")
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Checkpoint 系统
    # ------------------------------------------------------------------

    def _build_briefing_context(self, topic: str, briefing: str, attachment: str | None) -> str:
        """构建包含 briefing 的讨论上下文。

        Args:
            topic: 讨论主题。
            briefing: 制作人 briefing。
            attachment: 可选附件。

        Returns:
            组合后的上下文字符串。
        """
        parts = [f"## 讨论主题\n{topic}"]
        if briefing:
            parts.append(f"\n## 制作人简报\n{briefing}")
        if attachment:
            parts.append(f"\n## 附件内容\n{attachment}")
        return "\n".join(parts)

    def _next_checkpoint_id(self) -> str:
        """生成下一个 checkpoint ID。"""
        self._checkpoint_counter += 1
        return f"cp_{self._checkpoint_counter:03d}"

    def _generate_checkpoint(
        self,
        round_num: int,
        section: Any,
        round_responses: list[tuple[str, str]],
        briefing: str = "",
    ) -> Any:
        """调用 LLM 生成 Checkpoint，解析输出。

        Args:
            round_num: 当前轮次。
            section: 当前 section 对象（需有 title, description）。
            round_responses: 本轮 agent 发言列表 [(role, content), ...]。
            briefing: 制作人 briefing。

        Returns:
            Checkpoint 实例。
        """
        from src.models.checkpoint import Checkpoint, CheckpointType, DecisionOption

        recent_messages = [f"{role}: {content[:200]}" for role, content in round_responses]

        # Build discussion context from section summaries
        discussion_context = "\n".join(self._section_summaries[-5:]) if self._section_summaries else "(尚无先前讨论摘要)"

        # Collect pending decisions
        pending_decisions = []
        with self._checkpoint_lock:
            for cp in self._pending_decision_checkpoints.values():
                if cp.response is None:
                    pending_decisions.append(cp.question)

        prompt = self._lead_planner.create_checkpoint_prompt(
            round_num=round_num,
            section_title=section.title,
            section_description=section.description,
            recent_messages=recent_messages,
            discussion_context=discussion_context,
            briefing=briefing,
            pending_decisions=pending_decisions,
        )

        full_prompt = f"{prompt}"

        try:
            task = Task(
                description=full_prompt,
                expected_output="Checkpoint 判断结果",
                agent=self._lead_planner.build_agent(),
            )
            crew = Crew(
                agents=[self._lead_planner.build_agent()],
                tasks=[task],
                process=Process.sequential,
            )
            result = crew.kickoff()
            output = self._sanitize_crew_output(str(result), "checkpoint_generation")
        except Exception as e:
            logger.warning("Checkpoint generation failed: %s, defaulting to SILENT", e)
            output = ""

        # Parse checkpoint output
        checkpoint = self._parse_checkpoint_output(output, round_num, section)
        return checkpoint

    def _parse_checkpoint_output(self, output: str, round_num: int, section: Any) -> Any:
        """解析 LLM 输出中的 checkpoint 代码块。

        Args:
            output: LLM 输出文本。
            round_num: 轮次。
            section: 章节对象。

        Returns:
            Checkpoint 实例。
        """
        import re
        import yaml
        from src.models.checkpoint import Checkpoint, CheckpointType, DecisionOption

        cp_id = self._next_checkpoint_id()

        # Extract ```checkpoint block
        match = re.search(r"```checkpoint\s*\n(.*?)\n```", output, re.DOTALL)
        if not match:
            # Default to SILENT
            return Checkpoint(
                id=cp_id,
                discussion_id=self._discussion_id,
                type=CheckpointType.SILENT,
                round_num=round_num,
                section_id=getattr(section, "id", None),
            )

        block = match.group(1).strip()
        try:
            data = yaml.safe_load(block)
        except Exception:
            return Checkpoint(
                id=cp_id,
                discussion_id=self._discussion_id,
                type=CheckpointType.SILENT,
                round_num=round_num,
                section_id=getattr(section, "id", None),
            )

        if not isinstance(data, dict):
            return Checkpoint(
                id=cp_id,
                discussion_id=self._discussion_id,
                type=CheckpointType.SILENT,
                round_num=round_num,
                section_id=getattr(section, "id", None),
            )

        cp_type_str = str(data.get("type", "SILENT")).upper()
        try:
            cp_type = CheckpointType(cp_type_str.lower())
        except ValueError:
            cp_type = CheckpointType.SILENT

        options = []
        if cp_type == CheckpointType.DECISION:
            for opt_data in data.get("options", []):
                if isinstance(opt_data, dict):
                    options.append(DecisionOption(
                        id=str(opt_data.get("id", "")),
                        label=str(opt_data.get("label", "")),
                        description=str(opt_data.get("description", "")),
                    ))

        return Checkpoint(
            id=cp_id,
            discussion_id=self._discussion_id,
            type=cp_type,
            round_num=round_num,
            section_id=getattr(section, "id", None),
            title=str(data.get("title", "")),
            summary=str(data.get("summary", "")),
            key_points=data.get("key_points", []) if isinstance(data.get("key_points"), list) else [],
            question=str(data.get("question", "")),
            context=str(data.get("context", "")),
            options=options,
            allow_free_input=bool(data.get("allow_free_input", True)),
        )

    def _broadcast_checkpoint_event(self, checkpoint: Any) -> None:
        """广播 checkpoint 事件到 WebSocket。"""
        from src.api.websocket.events import (
            create_checkpoint_progress_event,
            create_checkpoint_decision_event,
        )
        from src.models.checkpoint import CheckpointType

        if self._discussion_id is None:
            return

        try:
            cp_data = checkpoint.model_dump(mode="json")
            if checkpoint.type == CheckpointType.PROGRESS:
                event = create_checkpoint_progress_event(self._discussion_id, cp_data)
            elif checkpoint.type == CheckpointType.DECISION:
                event = create_checkpoint_decision_event(self._discussion_id, cp_data)
            else:
                return  # SILENT produces no event

            broadcast_sync(event.to_dict(), discussion_id=self._discussion_id)
        except Exception as exc:
            logger.debug("Failed to broadcast checkpoint event: %s", exc)

    def _persist_checkpoint(self, checkpoint: Any) -> None:
        """持久化 checkpoint 到讨论记录。"""
        if self._current_discussion is None:
            return
        try:
            cp_data = checkpoint.model_dump(mode="json")
            self._current_discussion.checkpoints.append(cp_data)
            self._discussion_memory.save(self._current_discussion)
        except Exception as exc:
            logger.debug("Failed to persist checkpoint: %s", exc)

    def _wait_for_decision_response(self, checkpoint_id: str) -> dict:
        """轮询等待用户对 DECISION checkpoint 的回答。

        类似 _check_pause_and_wait 的轮询模式。
        在等待期间释放并发信号量槽，允许其他讨论在此期间启动。

        Args:
            checkpoint_id: 等待回答的 checkpoint ID。

        Returns:
            响应数据 dict，包含 option_id 和 free_input。
        """
        # Release the concurrency semaphore while waiting for user input,
        # so other discussions can start while we're blocked on a human decision.
        released_semaphore = False
        if self._concurrency_semaphore is not None:
            try:
                self._concurrency_semaphore.release()
                released_semaphore = True
                logger.debug(
                    "Released concurrency slot for discussion %s during WAITING_DECISION",
                    self._discussion_id,
                )
            except Exception as exc:
                logger.warning("Failed to release concurrency semaphore: %s", exc)

        start_time = time.time()
        try:
            while True:
                # Check if discussion was aborted
                state_info = get_discussion_state(self._discussion_id)
                if state_info is not None and state_info.get("state") == DiscussionState.FINISHED:
                    raise DiscussionTimeoutError("Discussion finished while waiting for decision")

                # Check if response arrived
                with self._checkpoint_lock:
                    cp = self._pending_decision_checkpoints.get(checkpoint_id)
                    if cp and cp.response is not None:
                        return {
                            "option_id": cp.response,
                            "free_input": cp.response_text or "",
                        }

                # Timeout check
                if time.time() - start_time > self._pause_timeout:
                    logger.warning(
                        "Decision wait timeout for checkpoint %s in discussion %s",
                        checkpoint_id, self._discussion_id,
                    )
                    raise DiscussionTimeoutError(f"Decision wait timeout for checkpoint {checkpoint_id}")

                time.sleep(self._pause_check_interval)
        finally:
            # Re-acquire the semaphore slot before continuing discussion execution
            if released_semaphore and self._concurrency_semaphore is not None:
                self._concurrency_semaphore.acquire()
                logger.debug(
                    "Re-acquired concurrency slot for discussion %s after decision response",
                    self._discussion_id,
                )

    def _lead_planner_announce_decision(self, checkpoint: Any) -> str:
        """主策划公开宣布决策内容。

        Args:
            checkpoint: 已有响应的 Checkpoint。

        Returns:
            宣布消息文本。
        """
        options_summary = "\n".join(
            f"  {opt.id}. {opt.label}: {opt.description}"
            for opt in checkpoint.options
        ) if checkpoint.options else "(无选项)"

        prompt = self._lead_planner.create_decision_announcement_prompt(
            question=checkpoint.question,
            user_response=checkpoint.response or "",
            user_response_text=checkpoint.response_text or "",
            options_summary=options_summary,
        )

        try:
            task = Task(
                description=prompt,
                expected_output="决策宣布消息",
                agent=self._lead_planner.build_agent(),
            )
            crew = Crew(
                agents=[self._lead_planner.build_agent()],
                tasks=[task],
                process=Process.sequential,
            )
            result = crew.kickoff()
            output = self._sanitize_crew_output(str(result), "decision_announcement")
            return output or "制作人已做出决策，讨论继续。"
        except Exception as e:
            logger.warning("Decision announcement failed: %s", e)
            return "制作人已做出决策，讨论继续。"

    def _check_producer_messages(self) -> list[dict]:
        """检查并获取待处理的制作人消息。

        Returns:
            制作人消息列表，每项包含 content 和 timestamp。
        """
        with self._producer_message_lock:
            if not self._pending_producer_messages:
                return []
            messages = list(self._pending_producer_messages)
            self._pending_producer_messages.clear()
            logger.info(
                "Discussion %s: dequeued %d producer message(s) for processing",
                self._discussion_id,
                len(messages),
            )
            return messages

    def _has_pending_producer_messages(self) -> bool:
        """Non-destructive check for pending producer messages.

        Used as interrupt_check callback during parallel agent execution.
        """
        with self._producer_message_lock:
            return len(self._pending_producer_messages) > 0

    def add_producer_message(self, content: str) -> None:
        """API 层调用，向队列添加制作人消息。

        Args:
            content: 消息内容。
        """
        from datetime import datetime
        with self._producer_message_lock:
            self._pending_producer_messages.append({
                "content": content,
                "timestamp": datetime.utcnow().isoformat(),
            })
            logger.info(
                "Discussion %s: producer message queued (queue_size=%d): %s",
                self._discussion_id,
                len(self._pending_producer_messages),
                content[:80],
            )

        # Persist producer message so it survives page refresh
        message = Message(
            id=str(uuid4()),
            agent_id="producer",
            agent_role="制作人",
            content=content,
            timestamp=datetime.now(),
        )
        self._messages.append(message)
        self._unsaved_message_count += 1
        if self._unsaved_message_count >= self._INCREMENTAL_SAVE_INTERVAL:
            self._incremental_save()

    def respond_to_checkpoint(self, checkpoint_id: str, option_id: str | None, free_input: str | None) -> bool:
        """API 层调用，提交对 DECISION checkpoint 的响应。

        Args:
            checkpoint_id: checkpoint ID。
            option_id: 选择的选项 ID（可选）。
            free_input: 自由输入文本（可选）。

        Returns:
            是否成功提交。
        """
        from datetime import datetime
        with self._checkpoint_lock:
            cp = self._pending_decision_checkpoints.get(checkpoint_id)
            if cp is None:
                return False
            cp.response = option_id or free_input or ""
            cp.response_text = free_input or ""
            cp.responded_at = datetime.utcnow().isoformat()
            return True

    def _lead_planner_digest_producer_message(
        self,
        messages: list[dict],
        section: Any,
        doc_plan: Any,
    ) -> dict:
        """主策划消化制作人消息。

        Args:
            messages: 制作人消息列表。
            section: 当前 section。
            doc_plan: 文档规划。

        Returns:
            消化结果 dict，包含 digest_summary, action, guidance。
        """
        user_messages = [m["content"] for m in messages]
        discussion_context = "\n".join(self._section_summaries[-5:]) if self._section_summaries else "(无)"
        section_title = getattr(section, "title", "未知章节")

        prompt = self._lead_planner.create_producer_digest_prompt(
            user_messages=user_messages,
            current_section=section_title,
            discussion_context=discussion_context,
        )

        try:
            task = Task(
                description=prompt,
                expected_output="制作人消息消化结果",
                agent=self._lead_planner.build_agent(),
            )
            crew = Crew(
                agents=[self._lead_planner.build_agent()],
                tasks=[task],
                process=Process.sequential,
            )
            result = crew.kickoff()
            output = self._sanitize_crew_output(str(result), "producer_digest")
        except Exception as e:
            logger.warning("Producer digest failed: %s", e)
            output = ""

        # Parse action from output
        action = "acknowledged"
        if output:
            output_lower = output.lower()
            if "**adjust**" in output_lower or "adjust" in output_lower.split("行动判断")[1:2]:
                action = "adjust"
            elif "**follow_up_decision**" in output_lower:
                action = "follow_up_decision"

        return {
            "digest_summary": output or "已收到制作人消息。",
            "action": action,
            "guidance": "",
        }

    def _digest_producer_messages_dynamic(
        self,
        messages: list[dict],
        discussion_context: str,
    ) -> dict:
        """在 run_dynamic 模式下消化制作人消息。

        与 _lead_planner_digest_producer_message 类似，但不依赖 section/doc_plan。

        Args:
            messages: 制作人消息列表。
            discussion_context: 当前讨论上下文。

        Returns:
            消化结果 dict，包含 digest_summary, action, guidance。
        """
        user_messages = [m["content"] for m in messages]
        messages_block = "\n".join(
            f"- 制作人消息 {i+1}: {msg}" for i, msg in enumerate(user_messages)
        )

        # 截取最近的上下文（避免太长）
        ctx_tail = discussion_context[-3000:] if len(discussion_context) > 3000 else discussion_context

        prompt = f"""作为主策划，你收到了制作人（项目负责人）的实时消息。请认真消化并融入后续讨论。

**讨论上下文（最近部分）**:
{ctx_tail}

**制作人消息**:
{messages_block}

请按以下格式输出你的分析和引导：

### 理解确认
- 用你自己的话复述制作人的核心意图

### 行动判断
选择以下之一：
- **adjust** — 制作人的意见需要调整当前讨论方向
- **follow_up_decision** — 需要向制作人追问确认
- **acknowledged** — 已知悉，纳入后续讨论

### 后续引导
- 下一轮讨论应如何回应制作人的意见
- 哪些团队成员需要重点关注制作人提出的问题"""

        try:
            task = Task(
                description=prompt,
                expected_output="制作人消息消化分析",
                agent=self._lead_planner.build_agent(),
            )
            crew = Crew(
                agents=[self._lead_planner.build_agent()],
                tasks=[task],
                process=Process.sequential,
            )
            result = crew.kickoff()
            output = self._sanitize_crew_output(str(result), "producer_digest_dynamic")
        except Exception as e:
            logger.warning("Producer digest (dynamic) failed: %s", e)
            output = ""

        # Parse action
        action = "acknowledged"
        if output:
            output_lower = output.lower()
            if "**adjust**" in output_lower:
                action = "adjust"
            elif "**follow_up_decision**" in output_lower:
                action = "follow_up_decision"

        return {
            "digest_summary": output or "已收到制作人消息，将在后续讨论中纳入考虑。",
            "action": action,
            "guidance": "",
        }

    def _trigger_auto_pause(self, round_num: int) -> None:
        """Trigger auto-pause at a round boundary."""
        logger.info(
            "Auto-pausing discussion %s at round %d (interval=%d)",
            self._discussion_id, round_num, self._auto_pause_interval,
        )
        set_discussion_state(self._discussion_id, DiscussionState.PAUSED)
        self._broadcast_discussion_event(
            f"discussion_auto_paused:已完成第{round_num}轮讨论，等待继续"
        )

    # ------------------------------------------------------------------
    # DYN-1.2: 议题初始生成与章节映射
    # ------------------------------------------------------------------

    def _generate_initial_agenda(self, topic: str, attachment: str | None = None) -> list[AgendaItem]:
        """Generate initial agenda items via LLM and initialize the agenda.

        Args:
            topic: The discussion topic.
            attachment: Optional attachment content.

        Returns:
            List of created AgendaItem objects.
        """
        prompt = self._lead_planner.create_agenda_prompt(topic, attachment)

        task = Task(
            description=prompt,
            expected_output="3-5 个讨论议题",
            agent=self._lead_planner.build_agent(),
        )
        crew = Crew(
            agents=[self._lead_planner.build_agent()],
            tasks=[task],
            process=Process.sequential,
        )
        result = crew.kickoff()
        raw = str(result)

        # Parse agenda items
        items_data = parse_agenda_output(raw)
        if not items_data:
            logger.warning("Failed to parse agenda output, creating fallback agenda")
            items_data = [{"title": topic, "description": "主议题"}]

        self._init_agenda(items_data)
        assert self._agenda is not None

        # Broadcast agenda initialization
        self._broadcast_agenda_event("agenda_init", {
            "items": [item.to_dict() for item in self._agenda.items],
        })

        logger.info("Generated initial agenda: %d items", len(self._agenda.items))
        return list(self._agenda.items)

    def _establish_agenda_section_mapping(
        self,
        agenda_items: list[AgendaItem],
        doc_plan,
    ) -> None:
        """Establish initial mapping between agenda items and doc sections via keyword matching.

        Sets bidirectional associations: AgendaItem.related_sections and SectionPlan.related_agenda_items.

        Args:
            agenda_items: The agenda items to map.
            doc_plan: The DocPlan to map sections from.
        """
        for item in agenda_items:
            # Build keywords from title and description
            keywords = set(item.title)
            if item.description:
                keywords.update(item.description)

            for f in doc_plan.files:
                for section in f.sections:
                    section_text = section.title + " " + section.description
                    # Simple keyword overlap check
                    overlap = sum(1 for kw in item.title.split() if kw in section_text)
                    if item.description:
                        overlap += sum(1 for kw in item.description.split() if kw in section_text)
                    if overlap > 0:
                        if section.id not in item.related_sections:
                            item.related_sections.append(section.id)
                        if item.id not in section.related_agenda_items:
                            section.related_agenda_items.append(item.id)

        # Broadcast mapping update
        mapping = {
            item.id: item.related_sections for item in agenda_items
        }
        self._broadcast_agenda_event("mapping_update", {"mapping": mapping})
        logger.info("Established agenda-section mapping for %d items", len(agenda_items))

    # ------------------------------------------------------------------
    # DYN-1.3: 议题管理指令解析
    # ------------------------------------------------------------------

    def _process_agenda_directives(self, summary: str, section) -> None:
        """Parse and execute ```agenda_update``` directives from a summary.

        Supports: complete, add, priority directives.

        Args:
            summary: The Lead Planner's section summary text.
            section: The current SectionPlan being discussed.
        """
        if self._agenda is None:
            return

        match = AGENDA_DIRECTIVE_PATTERN.search(summary)
        if not match:
            return

        block = match.group(1)
        for line in block.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            if line.startswith("complete:"):
                item_id = line.split(":", 1)[1].strip()
                item = self._agenda.get_item_by_id(item_id)
                if item and item.status != AgendaItemStatus.COMPLETED:
                    item.complete(f"由主策划在讨论章节「{section.title}」时标记完结")
                    self._broadcast_agenda_event("item_complete", {
                        "item_id": item.id,
                        "title": item.title,
                    })
                    logger.info("Agenda directive: completed item %s", item_id)

            elif line.startswith("add:"):
                rest = line.split(":", 1)[1].strip()
                # Format: [标题] - 描述
                title_match = re.match(r"\[(.+?)\]\s*-\s*(.+)", rest)
                if title_match:
                    title = title_match.group(1).strip()
                    description = title_match.group(2).strip()
                else:
                    title = rest
                    description = ""
                new_item = self._agenda.add_item(title, description)
                new_item.source = "discovered"
                # Link to current section
                if section and section.id not in new_item.related_sections:
                    new_item.related_sections.append(section.id)
                self._broadcast_agenda_event("item_added", {
                    "item": new_item.to_dict(),
                })
                logger.info("Agenda directive: added new item '%s'", title)

            elif line.startswith("priority:"):
                rest = line.split(":", 1)[1].strip()
                parts = rest.rsplit(None, 1)
                if len(parts) == 2:
                    item_id, level = parts
                    item = self._agenda.get_item_by_id(item_id.strip())
                    if item:
                        item.priority = 1 if level.strip().lower() == "high" else -1
                        self._broadcast_agenda_event("item_priority", {
                            "item_id": item.id,
                            "priority": item.priority,
                        })
                        logger.info("Agenda directive: set item %s priority to %s", item_id, level)

    # ------------------------------------------------------------------
    # DYN-2.4: 文档结构重规划 (Replan)
    # ------------------------------------------------------------------

    def _replan_doc_structure(self, doc_plan, reason: str) -> bool:
        """对文档结构进行完整重规划，保留已讨论的内容。

        流程：快照现有内容 → LLM 生成新规划 → 内容迁移 → 文件操作 → 状态更新

        Args:
            doc_plan: 当前 DocPlan。
            reason: 重规划原因。

        Returns:
            是否成功完成重规划。
        """
        from src.models.doc_plan import FilePlan, SectionPlan

        self._broadcast_discussion_event("正在执行文档结构重规划...")

        # Step 1: 快照现有内容
        old_contents: dict[str, dict] = {}  # {section_id: {title, content, filename}}
        all_file_contents: list[dict] = []
        for f in doc_plan.files:
            sections_data = {}
            if self._doc_writer:
                file_sections = self._doc_writer.read_all_sections(f.filename)
                for s in f.sections:
                    content = file_sections.get(s.id, "")
                    old_contents[s.id] = {
                        "title": s.title,
                        "content": content,
                        "filename": f.filename,
                    }
                    sections_data[s.id] = {"title": s.title, "content": content}
            all_file_contents.append({
                "filename": f.filename,
                "title": f.title,
                "sections": sections_data,
            })

        # Build current plan summary
        current_plan_summary = ", ".join(
            f"{f.filename}: [{', '.join(s.title for s in f.sections)}]"
            for f in doc_plan.files
        )

        # Step 2: LLM 生成新规划
        self._broadcast_status(self._lead_planner.role, AgentStatus.THINKING)
        prompt = self._lead_planner.create_replan_prompt(
            doc_plan.topic, all_file_contents, current_plan_summary, reason,
        )

        task = Task(
            description=prompt,
            expected_output="JSON 格式的新文档规划",
            agent=self._lead_planner.build_agent(),
        )
        crew = Crew(
            agents=[self._lead_planner.build_agent()],
            tasks=[task],
            process=Process.sequential,
        )
        result = crew.kickoff()
        raw = str(result)
        self._broadcast_status(self._lead_planner.role, AgentStatus.IDLE)

        # Parse JSON
        json_match = re.search(r"```json\s*\n(.*?)\n```", raw, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            json_str = json_match.group(0) if json_match else raw

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning("Replan: failed to parse JSON, aborting replan")
            self._broadcast_discussion_event("重规划失败：无法解析 LLM 输出，保持原结构")
            return False

        # Step 3: 构建新文件结构并迁移内容
        section_counter = 0
        new_files: list[FilePlan] = []
        new_file_write_data: list[dict] = []  # 用于写入文件

        for f_data in data.get("files", []):
            sections: list[SectionPlan] = []
            file_sections_write: list[dict] = []

            for s_data in f_data.get("sections", []):
                section_counter += 1
                sid = s_data.get("id", f"s{section_counter}")
                title = s_data.get("title", f"章节{section_counter}")
                description = s_data.get("description", "")
                source_sids = s_data.get("source_sections", [])

                sections.append(SectionPlan(id=sid, title=title, description=description))

                # 内容迁移
                migrated_content = ""
                valid_sources = [s for s in source_sids if s in old_contents]

                if not valid_sources:
                    # 无来源 → 空骨架
                    migrated_content = f"*{description}*"
                elif len(valid_sources) == 1:
                    # 单一来源 → 直接复制
                    migrated_content = old_contents[valid_sources[0]]["content"]
                else:
                    # 多来源 → LLM 重组
                    source_data = [
                        {"title": old_contents[s]["title"], "content": old_contents[s]["content"]}
                        for s in valid_sources
                    ]
                    try:
                        migration_prompt = self._lead_planner.create_content_migration_prompt(
                            title, description, source_data,
                        )
                        migration_task = Task(
                            description=migration_prompt,
                            expected_output="重组后的章节内容",
                            agent=self._lead_planner.build_agent(),
                        )
                        migration_crew = Crew(
                            agents=[self._lead_planner.build_agent()],
                            tasks=[migration_task],
                            process=Process.sequential,
                        )
                        migration_result = migration_crew.kickoff()
                        migrated_content = str(migration_result).strip()
                    except Exception as e:
                        logger.warning("Replan: migration failed for %s, using concatenation: %s", sid, e)
                        # 回退：拼接原内容
                        migrated_content = "\n\n".join(
                            old_contents[s]["content"] for s in valid_sources if old_contents[s]["content"]
                        )

                file_sections_write.append({
                    "id": sid,
                    "title": title,
                    "content": migrated_content,
                })

            new_files.append(FilePlan(
                filename=f_data.get("filename", f"文档{len(new_files) + 1}.md"),
                title=f_data.get("title", "未命名文档"),
                sections=sections,
            ))
            new_file_write_data.append({
                "filename": f_data.get("filename", f"文档{len(new_files)}.md"),
                "title": f_data.get("title", "未命名文档"),
                "sections": file_sections_write,
            })

        if not new_files:
            logger.warning("Replan: LLM output has no files, aborting")
            self._broadcast_discussion_event("重规划失败：LLM 未输出有效文件结构")
            return False

        # Step 4: 文件操作
        if self._doc_writer:
            # 删除所有旧文件
            for f in doc_plan.files:
                self._doc_writer.remove_file(f.filename)

            # 写入新文件
            for fw in new_file_write_data:
                self._doc_writer.write_full_file(
                    fw["filename"], fw["title"], fw["sections"],
                )

        # Step 5: 状态更新
        old_files = doc_plan.replace_plan(new_files)

        # 重建 agenda-section 映射
        if self._agenda:
            # 清除旧映射
            for item in self._agenda.items:
                item.related_sections.clear()
            self._establish_agenda_section_mapping(self._agenda.items, doc_plan)

        # 广播更新
        self._broadcast_doc_plan_event(doc_plan)
        self._broadcast_discussion_event(
            f"文档结构重规划完成：{len(old_files)} 个旧文件 → {len(new_files)} 个新文件"
        )

        # 持久化
        if self._current_discussion:
            self._current_discussion.doc_plan = doc_plan.to_dict()
            self._incremental_save()

        logger.info("Replan complete: %d old files -> %d new files", len(old_files), len(new_files))
        return True

    # ------------------------------------------------------------------
    # DYN-2.3: 文档结构变更指令解析
    # ------------------------------------------------------------------

    def _process_doc_restructure(self, summary: str, doc_plan, section) -> None:
        """Parse and execute ```doc_restructure``` directives from a summary.

        Supports: split, merge, add_section, add_file directives.

        Args:
            summary: The Lead Planner's section summary text.
            doc_plan: The current DocPlan.
            section: The current SectionPlan being discussed.
        """
        from src.models.doc_plan import SectionPlan, FilePlan

        match = DOC_RESTRUCTURE_PATTERN.search(summary)
        if not match:
            return

        block = match.group(1)
        section_counter = max(
            (int(s.id.lstrip("s")) for f in doc_plan.files for s in f.sections if s.id.startswith("s") and s.id[1:].isdigit()),
            default=0,
        )

        for line in block.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            try:
                if line.startswith("replan:"):
                    reason = line.split(":", 1)[1].strip()
                    if reason:
                        self._broadcast_discussion_event(f"文档结构重规划：{reason}")
                        logger.info("Doc restructure: replan triggered — %s", reason)
                        self._replan_doc_structure(doc_plan, reason)
                    continue

                if line.startswith("split:"):
                    # split: <section_id> -> [新标题1](新描述1), [新标题2](新描述2)
                    rest = line.split(":", 1)[1].strip()
                    parts = rest.split("->", 1)
                    if len(parts) != 2:
                        continue
                    old_sid = parts[0].strip()
                    new_specs = re.findall(r"\[(.+?)\]\((.+?)\)", parts[1])
                    if not new_specs:
                        continue

                    new_sections = []
                    new_section_dicts = []
                    for title, desc in new_specs:
                        section_counter += 1
                        new_sid = f"s{section_counter}"
                        new_sections.append(SectionPlan(id=new_sid, title=title, description=desc))
                        new_section_dicts.append({"id": new_sid, "title": title, "description": desc})

                    # Update DocPlan
                    if doc_plan.split_section(old_sid, new_sections):
                        # Update file via DocWriter
                        f, _ = doc_plan.get_section(new_sections[0].id)
                        if f and self._doc_writer:
                            self._doc_writer.split_section_content(f.filename, old_sid, new_section_dicts)
                        # Update agenda mapping
                        if self._agenda:
                            for item in self._agenda.items:
                                if old_sid in item.related_sections:
                                    item.related_sections.remove(old_sid)
                                    item.related_sections.extend(s.id for s in new_sections)
                        self._broadcast_discussion_event(f"文档结构调整：拆分章节 {old_sid} 为 {len(new_sections)} 个新章节")
                        logger.info("Doc restructure: split %s into %d sections", old_sid, len(new_sections))

                elif line.startswith("merge:"):
                    # merge: <sid1>, <sid2> -> [合并后标题]
                    rest = line.split(":", 1)[1].strip()
                    parts = rest.split("->", 1)
                    if len(parts) != 2:
                        continue
                    sids = [s.strip() for s in parts[0].split(",")]
                    title_match = re.search(r"\[(.+?)\]", parts[1])
                    merged_title = title_match.group(1) if title_match else "合并章节"

                    section_counter += 1
                    merged_sid = f"s{section_counter}"
                    merged_section = SectionPlan(id=merged_sid, title=merged_title, description="合并章节")

                    if doc_plan.merge_sections(sids, merged_section):
                        # Update file
                        f, _ = doc_plan.get_section(merged_sid)
                        if f and self._doc_writer:
                            self._doc_writer.merge_section_content(f.filename, sids, merged_sid, merged_title)
                        # Update agenda mapping
                        if self._agenda:
                            for item in self._agenda.items:
                                changed = False
                                for old_sid in sids:
                                    if old_sid in item.related_sections:
                                        item.related_sections.remove(old_sid)
                                        changed = True
                                if changed and merged_sid not in item.related_sections:
                                    item.related_sections.append(merged_sid)
                        self._broadcast_discussion_event(f"文档结构调整：合并章节 {', '.join(sids)} 为「{merged_title}」")
                        logger.info("Doc restructure: merged %s into %s", sids, merged_sid)

                elif line.startswith("add_section:"):
                    # add_section: <file_index>:<after_section_id> [新章节标题](新章节描述)
                    rest = line.split(":", 2)[2].strip() if line.count(":") >= 2 else line.split(":", 1)[1].strip()
                    # Parse file_index:after_sid
                    loc_match = re.match(r"(\d+):(\S+)\s+\[(.+?)\]\((.+?)\)", rest)
                    if not loc_match:
                        continue
                    file_idx = int(loc_match.group(1))
                    after_sid = loc_match.group(2)
                    new_title = loc_match.group(3)
                    new_desc = loc_match.group(4)

                    section_counter += 1
                    new_sid = f"s{section_counter}"
                    new_section = SectionPlan(id=new_sid, title=new_title, description=new_desc)

                    after_sid_val = after_sid if after_sid != "start" else None
                    if doc_plan.add_section(file_idx, new_section, after_sid_val):
                        # Add marker in file
                        if self._doc_writer and file_idx < len(doc_plan.files):
                            self._doc_writer.add_section_marker(
                                doc_plan.files[file_idx].filename,
                                new_sid, new_title, new_desc,
                                after_section_id=after_sid_val,
                            )
                        self._broadcast_discussion_event(f"文档结构调整：新增章节「{new_title}」")
                        logger.info("Doc restructure: added section %s '%s'", new_sid, new_title)

                elif line.startswith("add_file:"):
                    # add_file: [文件名.md](文件标题) sections: [标题1](描述1), [标题2](描述2)
                    rest = line.split(":", 1)[1].strip()
                    file_match = re.match(r"\[(.+?)\]\((.+?)\)\s*sections:\s*(.+)", rest)
                    if not file_match:
                        continue
                    new_filename = file_match.group(1)
                    new_file_title = file_match.group(2)
                    sections_str = file_match.group(3)
                    sec_specs = re.findall(r"\[(.+?)\]\((.+?)\)", sections_str)

                    new_file_sections = []
                    for title, desc in sec_specs:
                        section_counter += 1
                        new_file_sections.append(SectionPlan(
                            id=f"s{section_counter}", title=title, description=desc,
                        ))

                    new_fp = FilePlan(filename=new_filename, title=new_file_title, sections=new_file_sections)
                    if not doc_plan.add_file(new_fp):
                        logger.warning("Doc restructure: filename conflict '%s'", new_filename)
                        continue
                    if self._doc_writer:
                        self._doc_writer.create_new_file(new_fp)
                    self._broadcast_discussion_event(f"文档结构调整：新增文件「{new_filename}」")
                    logger.info("Doc restructure: added file %s with %d sections", new_filename, len(new_file_sections))

            except Exception as exc:
                logger.warning("Failed to process doc_restructure directive '%s': %s", line, exc)

    # ------------------------------------------------------------------
    # DYN-3.2: 干预消化与影响评估
    # ------------------------------------------------------------------

    def _lead_planner_digest_intervention(
        self,
        injected: list[dict],
        section,
    ) -> dict:
        """Digest user intervention messages via Lead Planner LLM call.

        Args:
            injected: List of injected message dicts.
            section: The current SectionPlan being discussed.

        Returns:
            Dict with "raw" (full LLM output) and "user_messages" (original messages).
        """
        user_messages = [msg.get("content", "") for msg in injected]
        discussion_context = "\n".join(
            f"- {s}" for s in self._section_summaries
        ) if self._section_summaries else "(暂无上下文)"

        section_title = section.title if section else "未知章节"
        prompt = self._lead_planner.create_intervention_digest_prompt(
            user_messages, section_title, discussion_context,
        )

        task = Task(
            description=prompt,
            expected_output="制作人消息消化分析",
            agent=self._lead_planner.build_agent(),
        )
        crew = Crew(
            agents=[self._lead_planner.build_agent()],
            tasks=[task],
            process=Process.sequential,
        )
        result = crew.kickoff()
        digest_raw = str(result)

        # Broadcast digest event
        self._broadcast_discussion_event("主策划正在消化制作人消息...")
        self._broadcast_message(self._lead_planner.role, digest_raw)
        self._record_message(self._lead_planner.role, digest_raw)

        # Write to memory
        self._record_message("System", f"[干预消化] {digest_raw[:500]}")

        logger.info("Intervention digest completed for %d messages", len(user_messages))
        return {"raw": digest_raw, "user_messages": user_messages}

    def _assess_intervention_impact(
        self,
        digest: dict,
        doc_plan,
        section,
    ) -> dict:
        """Assess the impact of user intervention via Lead Planner LLM call.

        Args:
            digest: The digest dict from _lead_planner_digest_intervention.
            doc_plan: The current DocPlan.
            section: The current SectionPlan.

        Returns:
            Dict with parsed assessment including impact_level, reopen_sections, new_topics.
        """
        # Build completed sections info
        completed_sections = []
        for f, s in doc_plan.get_completed_sections():
            completed_sections.append({
                "id": s.id,
                "title": s.title,
                "summary": f"(来自 {f.filename})",
            })

        # Build doc plan summary
        doc_plan_summary = ", ".join(
            f"{f.filename}: [{', '.join(s.title for s in f.sections)}]"
            for f in doc_plan.files
        )

        section_title = section.title if section else "未知章节"
        prompt = self._lead_planner.create_intervention_assessment_prompt(
            digest["raw"], section_title, completed_sections, doc_plan_summary,
        )

        task = Task(
            description=prompt,
            expected_output="干预影响评估",
            agent=self._lead_planner.build_agent(),
        )
        crew = Crew(
            agents=[self._lead_planner.build_agent()],
            tasks=[task],
            process=Process.sequential,
        )
        result = crew.kickoff()
        raw = str(result)

        # Parse assessment block
        assessment = {
            "raw": raw,
            "impact_level": "CURRENT_ONLY",
            "summary": "",
            "reopen_sections": [],
            "new_topics": [],
        }

        match = INTERVENTION_ASSESSMENT_PATTERN.search(raw)
        if match:
            block = match.group(1)
            # Parse impact_level
            level_match = re.search(r"impact_level:\s*(\S+)", block)
            if level_match:
                assessment["impact_level"] = level_match.group(1).strip()
            # Parse summary
            summary_match = re.search(r"summary:\s*(.+)", block)
            if summary_match:
                assessment["summary"] = summary_match.group(1).strip()
            # Parse reopen_sections
            reopen_pattern = re.findall(r"section_id:\s*(\S+)\s*\n\s*reason:\s*(.+?)(?:\n\s*focus:\s*(.+?))?(?=\n\s*-|\Z)", block, re.DOTALL)
            for sid, reason, focus in reopen_pattern:
                assessment["reopen_sections"].append({
                    "section_id": sid.strip(),
                    "reason": reason.strip(),
                    "focus": focus.strip() if focus else "",
                })
            # Parse new_topics
            topic_pattern = re.findall(r"title:\s*(.+?)\n\s*description:\s*(.+?)(?:\n\s*priority:\s*(\S+))?(?=\n\s*-|\Z)", block, re.DOTALL)
            for title, desc, priority in topic_pattern:
                assessment["new_topics"].append({
                    "title": title.strip(),
                    "description": desc.strip(),
                    "priority": priority.strip() if priority else "medium",
                })

        # Broadcast assessment
        self._broadcast_discussion_event(
            f"干预影响评估：{assessment['impact_level']} - {assessment['summary']}"
        )
        self._broadcast_message(self._lead_planner.role, raw)
        self._record_message(self._lead_planner.role, raw)

        logger.info("Intervention assessment: %s", assessment["impact_level"])
        return assessment

    def _execute_assessment_actions(self, assessment: dict, doc_plan) -> None:
        """Execute actions from an intervention assessment.

        Handles REOPEN (reopen completed sections) and NEW_TOPIC (add agenda items).

        Args:
            assessment: The assessment dict from _assess_intervention_impact.
            doc_plan: The current DocPlan.
        """
        impact = assessment.get("impact_level", "CURRENT_ONLY")

        if impact == "REOPEN" or impact == "NEW_TOPIC":
            # Reopen sections
            for reopen in assessment.get("reopen_sections", []):
                sid = reopen["section_id"]
                reason = reopen["reason"]
                if doc_plan.reopen_section(sid, reason):
                    self._broadcast_discussion_event(f"回溯重开章节 {sid}：{reason}")
                    logger.info("Reopened section %s: %s", sid, reason)

        if impact == "NEW_TOPIC":
            # Add new agenda topics
            if self._agenda:
                for topic_info in assessment.get("new_topics", []):
                    new_item = self._agenda.add_item(
                        topic_info["title"],
                        topic_info.get("description"),
                    )
                    new_item.source = "intervention"
                    new_item.priority = 1 if topic_info.get("priority") == "high" else 0
                    self._broadcast_agenda_event("item_added", {
                        "item": new_item.to_dict(),
                    })
                    logger.info("Added intervention topic: %s", topic_info["title"])

    def _lead_planner_post_intervention_guidance(self, digest: dict, assessment: dict) -> None:
        """Output discussion guidance after processing an intervention.

        Args:
            digest: The digest dict.
            assessment: The assessment dict.
        """
        impact = assessment.get("impact_level", "CURRENT_ONLY")
        summary = assessment.get("summary", "")

        if impact == "CURRENT_ONLY":
            guidance = f"制作人意见已纳入考虑。{summary}。请大家在当前章节讨论中融入这些意见。"
        elif impact == "REOPEN":
            reopened = [r["section_id"] for r in assessment.get("reopen_sections", [])]
            guidance = f"制作人意见影响较大：{summary}。已重开章节 {', '.join(reopened)}，稍后会回溯讨论。"
        else:
            new_titles = [t["title"] for t in assessment.get("new_topics", [])]
            guidance = f"制作人意见引入新议题：{summary}。新增议题：{', '.join(new_titles)}。"

        self._broadcast_message(self._lead_planner.role, guidance)
        self._record_message(self._lead_planner.role, guidance)
        logger.info("Post-intervention guidance: %s", guidance[:100])

    # ------------------------------------------------------------------
    # DYN-4.2: 整体审视
    # ------------------------------------------------------------------

    def _lead_planner_holistic_review(self, doc_plan, agenda) -> dict:
        """Perform holistic review of all documents after all sections are complete.

        Args:
            doc_plan: The DocPlan with all sections.
            agenda: The Agenda (may be None).

        Returns:
            Dict with parsed review including conclusion, quality_score, actions.
        """
        # Read all file contents
        all_file_contents = []
        for f in doc_plan.files:
            content = self._doc_writer.read_file(f.filename) if self._doc_writer else ""
            all_file_contents.append({
                "filename": f.filename,
                "title": f.title,
                "content": content or "(无内容)",
            })

        # Build doc plan summary
        doc_plan_summary = ", ".join(
            f"{f.filename}: [{', '.join(s.title for s in f.sections)}]"
            for f in doc_plan.files
        )

        # Get pending agenda items
        pending_items = []
        if agenda:
            for item in agenda.items:
                if item.status not in (AgendaItemStatus.COMPLETED, AgendaItemStatus.SKIPPED):
                    pending_items.append(f"{item.title} ({item.description or ''})")

        # Build discussion summary from recent section summaries
        discussion_summary = "\n".join(self._section_summaries) if self._section_summaries else "(暂无摘要)"

        prompt = self._lead_planner.create_holistic_review_prompt(
            all_file_contents, doc_plan_summary, pending_items, discussion_summary,
        )

        self._broadcast_discussion_event("主策划正在进行整体审视...")
        self._broadcast_status(self._lead_planner.role, AgentStatus.THINKING)

        task = Task(
            description=prompt,
            expected_output="文档整体审视结果",
            agent=self._lead_planner.build_agent(),
        )
        crew = Crew(
            agents=[self._lead_planner.build_agent()],
            tasks=[task],
            process=Process.sequential,
        )
        result = crew.kickoff()
        raw = str(result)

        self._broadcast_status(self._lead_planner.role, AgentStatus.SPEAKING)
        self._broadcast_message(self._lead_planner.role, raw)
        self._record_message(self._lead_planner.role, raw)
        self._broadcast_status(self._lead_planner.role, AgentStatus.IDLE)

        # Parse review block
        review = {
            "raw": raw,
            "conclusion": "APPROVED",
            "quality_score": 7,
            "summary": "",
            "revision_actions": [],
            "new_topics": [],
            "restructure_reason": "",
        }

        match = HOLISTIC_REVIEW_PATTERN.search(raw)
        if match:
            block = match.group(1)
            # Parse conclusion
            conclusion_match = re.search(r"conclusion:\s*(\S+)", block)
            if conclusion_match:
                review["conclusion"] = conclusion_match.group(1).strip()
            # Parse quality_score
            score_match = re.search(r"quality_score:\s*(\d+)", block)
            if score_match:
                review["quality_score"] = int(score_match.group(1))
            # Parse summary
            summary_match = re.search(r"summary:\s*(.+)", block)
            if summary_match:
                review["summary"] = summary_match.group(1).strip()
            # Parse revision_actions
            revision_pattern = re.findall(
                r"section_id:\s*(\S+)\s*\n\s*file:\s*(.+?)\n\s*action:\s*(.+?)(?=\n\s*-|\Z)",
                block, re.DOTALL,
            )
            for sid, fname, action in revision_pattern:
                review["revision_actions"].append({
                    "section_id": sid.strip(),
                    "file": fname.strip(),
                    "action": action.strip(),
                })
            # Parse new_topics
            topic_pattern = re.findall(r"title:\s*(.+?)\n\s*reason:\s*(.+?)(?=\n\s*-|\Z)", block, re.DOTALL)
            for title, reason in topic_pattern:
                review["new_topics"].append({
                    "title": title.strip(),
                    "reason": reason.strip(),
                })
            # Parse restructure_reason
            restructure_match = re.search(r"restructure_reason:\s*(.+)", block)
            if restructure_match:
                review["restructure_reason"] = restructure_match.group(1).strip()

        self._broadcast_discussion_event(
            f"整体审视结论：{review['conclusion']}（质量分 {review['quality_score']}/10）"
        )
        logger.info("Holistic review: %s (score=%d)", review["conclusion"], review["quality_score"])
        return review

    def _execute_review_actions(self, review: dict, doc_plan, agenda) -> bool:
        """Execute actions from a holistic review.

        NEEDS_REVISION: reopen sections. NEEDS_NEW_TOPIC: add agenda items.
        NEEDS_RESTRUCTURE: replan document structure.

        Args:
            review: The review dict from _lead_planner_holistic_review.
            doc_plan: The current DocPlan.
            agenda: The current Agenda (may be None).

        Returns:
            True if a restructure was performed (caller should re-enter section loop).
        """
        conclusion = review.get("conclusion", "APPROVED")

        if conclusion == "NEEDS_RESTRUCTURE":
            reason = review.get("restructure_reason") or review.get("summary", "整体审视要求重规划")
            self._replan_doc_structure(doc_plan, reason)
            return True

        if conclusion == "NEEDS_REVISION":
            for action in review.get("revision_actions", []):
                sid = action["section_id"]
                reason = action.get("action", "整体审视要求修订")
                if doc_plan.reopen_section(sid, reason):
                    self._broadcast_discussion_event(f"整体审视：重开章节 {sid}")
                    logger.info("Review: reopened section %s", sid)

        elif conclusion == "NEEDS_NEW_TOPIC":
            # Reopen sections if any
            for action in review.get("revision_actions", []):
                sid = action["section_id"]
                reason = action.get("action", "整体审视要求修订")
                if doc_plan.reopen_section(sid, reason):
                    logger.info("Review: reopened section %s", sid)

            # Add new topics
            if agenda:
                for topic_info in review.get("new_topics", []):
                    new_item = agenda.add_item(
                        topic_info["title"],
                        topic_info.get("reason", ""),
                    )
                    new_item.source = "discovered"
                    self._broadcast_agenda_event("item_added", {
                        "item": new_item.to_dict(),
                    })
                    logger.info("Review: added topic '%s'", topic_info["title"])

        return False

    def _force_complete_with_notes(self, review: dict) -> None:
        """Force complete the discussion with review notes appended.

        Args:
            review: The review dict with notes to append.
        """
        notes = review.get("summary", "")
        conclusion = review.get("conclusion", "APPROVED")
        score = review.get("quality_score", 0)

        msg = (
            f"整体审视完成（{conclusion}，质量分 {score}/10）。"
            f"{notes}"
            f"\n\n注意：已达到最大审视轮次，以当前状态完成。"
        )
        self._broadcast_message(self._lead_planner.role, msg)
        self._record_message(self._lead_planner.role, msg)
        logger.info("Force complete with notes: %s", conclusion)

    def run_document_centric(
        self,
        topic: str,
        max_rounds: int = 10,
        attachment: str | None = None,
        auto_pause_interval: int = 5,
        briefing: str = "",
        producer_stance: str = "",
        agenda_items: list[str] | None = None,
    ) -> str:
        """Run a document-centric discussion.

        Each round focuses on a specific document section. The Lead Planner
        decides which section to discuss, agents discuss it, then DocWriter
        updates the section in the actual .md file.

        Args:
            topic: The discussion topic.
            max_rounds: Maximum rounds of discussion.
            attachment: Optional attachment content.
            auto_pause_interval: Auto-pause every N rounds (0=disabled).
            briefing: Producer briefing with background, constraints, expected output.
            producer_stance: 制作人预设立场，优先级高于 briefing，作为讨论方向约束。

        Returns:
            Final result string.
        """
        # 将制作人立场合并到 briefing 开头（高优先级展示）
        combined_briefing = briefing
        if producer_stance:
            stance_block = f"## ⚠️ 制作人立场（所有讨论必须围绕此方向展开）\n{producer_stance}"
            combined_briefing = f"{stance_block}\n\n{briefing}".strip() if briefing else stance_block

        # 注入预设议程
        if agenda_items:
            agenda_block = "## 📋 讨论议程（请按顺序推进）\n" + "\n".join(
                f"{i}. {item}" for i, item in enumerate(agenda_items, 1)
            )
            combined_briefing = f"{combined_briefing}\n\n{agenda_block}".strip() if combined_briefing else agenda_block

        # 注入跨项目 Agent 记忆
        try:
            from pathlib import Path as _Path
            import json as _json
            _memory_dir = _Path("data/agent_memory")
            agent_memories: list[str] = []
            for role in (self._agents or []):
                mem_file = _memory_dir / f"{role}.json"
                if mem_file.exists():
                    try:
                        mdata = _json.loads(mem_file.read_text(encoding="utf-8"))
                        recent = mdata.get("memories", [])[-3:]
                        for m in recent:
                            agent_memories.append(f"- [{role}] {m.get('insight', '')[:100]}")
                    except Exception:
                        pass
            if agent_memories:
                mem_block = "## 🧠 Agent 历史经验（来自其他项目）\n" + "\n".join(agent_memories)
                combined_briefing = f"{combined_briefing}\n\n{mem_block}".strip() if combined_briefing else mem_block
        except Exception:
            pass
        from src.models.doc_plan import DocPlan
        from src.agents.doc_writer import DocWriter
        from src.crew.mention_parser import parse_next_speakers

        self._init_discussion(topic)
        self._auto_pause_interval = auto_pause_interval
        self._total_rounds = max_rounds
        self._briefing = combined_briefing
        set_discussion_state(self._discussion_id, DiscussionState.RUNNING)
        self._abort_reason = None

        # Initialize DocWriter
        docs_dir = Path(self._data_dir) / self._project_id / self._discussion_id / "docs"
        self._doc_writer = DocWriter(llm=self._llm, docs_dir=docs_dir)

        trace_metadata = self._prepare_trace_metadata(topic, max_rounds)
        trace_span: Any | None = None

        try:
            with start_trace_context(
                name="discussion_document_centric",
                session_id=self._discussion_id,
                metadata=trace_metadata,
            ) as span:
                trace_span = span

                # Phase 0: Generate document plan
                self._broadcast_discussion_event("正在规划文档结构...")
                self._broadcast_status(self._lead_planner.role, AgentStatus.THINKING)
                doc_plan = self._generate_doc_plan(topic, attachment)
                self._doc_plan = doc_plan
                self._doc_writer.create_skeleton(doc_plan)
                self._broadcast_doc_plan_event(doc_plan)

                # Generate initial agenda and establish mapping
                self._broadcast_discussion_event("正在生成讨论议题...")
                agenda_items = self._generate_initial_agenda(topic, attachment)
                self._establish_agenda_section_mapping(agenda_items, doc_plan)
                self._broadcast_status(self._lead_planner.role, AgentStatus.IDLE)

                # Save doc_plan to discussion record
                if self._current_discussion:
                    self._current_discussion.doc_plan = doc_plan.to_dict()
                    self._incremental_save()

                # Phase 1-N: Section-by-section discussion
                for round_num in range(1, max_rounds + 1):
                    self._current_round = round_num

                    # ── Check for producer messages at round start ──
                    # Messages can arrive during checkpoint / DocWriter /
                    # pause-check of the previous round.  Capture them
                    # now so _lead_planner_section_opening sees them.
                    early_producer_msgs = self._check_producer_messages()
                    if early_producer_msgs:
                        producer_text = "\n".join(
                            m["content"] for m in early_producer_msgs
                        )
                        self._producer_digest_pending = (
                            f"制作人消息：{producer_text}"
                        )
                        logger.info(
                            "Discussion %s round %d: captured %d early "
                            "producer message(s) for opening injection",
                            self._discussion_id,
                            round_num,
                            len(early_producer_msgs),
                        )

                    # Pick next section
                    file_plan, section = self._pick_next_section(doc_plan)
                    if file_plan is None or section is None:
                        logger.info("All sections completed at round %d", round_num)
                        break

                    section.status = "in_progress"
                    doc_plan.current_section_id = section.id
                    self._broadcast_section_focus(section.id, section.title, file_plan.filename)
                    self._broadcast_discussion_event(
                        f"第{round_num}轮：聚焦章节「{section.title}」({file_plan.filename})"
                    )

                    # Read current section content
                    section_content = self._doc_writer.read_section(file_plan.filename, section.id)

                    # Last-chance check for producer messages before opening
                    late_msgs = self._check_producer_messages()
                    if late_msgs:
                        extra = "\n".join(m["content"] for m in late_msgs)
                        prev = self._producer_digest_pending or ""
                        self._producer_digest_pending = (
                            f"{prev}\n制作人消息：{extra}" if prev
                            else f"制作人消息：{extra}"
                        )

                    # Lead Planner opens section discussion
                    # (_producer_digest_pending is consumed inside if set)
                    self._broadcast_status(self._lead_planner.role, AgentStatus.THINKING)
                    opening = self._lead_planner_section_opening(section, section_content, round_num)
                    opening = sanitize_speakers_in_text(opening, known_roles=[a.role for a in self._discussion_agents])
                    self._broadcast_status(self._lead_planner.role, AgentStatus.SPEAKING)
                    self._broadcast_message(self._lead_planner.role, opening)
                    self._record_message(self._lead_planner.role, opening)
                    self._broadcast_status(self._lead_planner.role, AgentStatus.IDLE)

                    # Determine speakers
                    next_speakers = parse_next_speakers(opening, known_roles=[a.role for a in self._discussion_agents])

                    # Pause if the speakers block requests producer turn
                    if PRODUCER_ROLE in (next_speakers or []):
                        self._wait_for_producer_turn()
                        if self._abort_reason:
                            raise DiscussionTimeoutError(self._abort_reason)
                        next_speakers = [s for s in next_speakers if s != PRODUCER_ROLE] or None

                    agents_to_call = (
                        [a for a in self._discussion_agents if a.role in next_speakers]
                        if next_speakers else list(self._discussion_agents)
                    )
                    if not agents_to_call:
                        agents_to_call = list(self._discussion_agents)

                    participating = [a.role for a in agents_to_call]
                    logger.info("Discussion %s round %d section %s: speakers=%s",
                                self._discussion_id, round_num, section.id, participating)

                    # Agents discuss in parallel (with producer interrupt detection)
                    context = self._build_section_context(topic, doc_plan, section, section_content, opening)
                    used_decisions = bool(
                        self._section_decisions.get(section.id)
                        and len(section_content or "") > 1500
                    )
                    logger.info(
                        "Discussion %s round %d: section_content=%d chars, "
                        "agent_context=%d chars, mode=%s",
                        self._discussion_id, round_num,
                        len(section_content or ""), len(context),
                        "decisions_summary" if used_decisions else "full_content",
                    )
                    round_responses, was_interrupted = self._run_agents_parallel_sync(
                        agents_to_call, context,
                        interrupt_check=self._has_pending_producer_messages,
                    )

                    # Build discussion content for summary and doc update
                    discussion_content = f"主策划：{opening}\n\n"
                    for role, resp in round_responses:
                        discussion_content += f"{role}：{resp}\n\n"

                    # --- Process producer messages (before checkpoint) ---
                    producer_msgs = self._check_producer_messages()
                    if producer_msgs:
                        if was_interrupted:
                            self._broadcast_discussion_event(
                                "收到制作人消息，中断当前讨论，主策划正在分析..."
                            )
                        self._broadcast_status(self._lead_planner.role, AgentStatus.THINKING)
                        digest = self._lead_planner_digest_producer_message(
                            producer_msgs, section, doc_plan,
                        )
                        digest_text = digest["digest_summary"]

                        # Broadcast lead planner's response to producer
                        self._broadcast_status(self._lead_planner.role, AgentStatus.SPEAKING)
                        self._broadcast_message(
                            self._lead_planner.role,
                            f"[回应制作人] {digest_text}",
                        )
                        self._record_message(
                            self._lead_planner.role,
                            f"[回应制作人] {digest_text}",
                        )
                        self._broadcast_status(self._lead_planner.role, AgentStatus.IDLE)

                        # Inject into discussion content so checkpoint sees it
                        for msg in producer_msgs:
                            discussion_content += f"制作人：{msg['content']}\n\n"
                        discussion_content += f"主策划回应：{digest_text}\n\n"

                        # Broadcast digest event for frontend
                        try:
                            from src.api.websocket.events import create_producer_digest_event
                            digest_event = create_producer_digest_event(
                                self._discussion_id,
                                digest_summary=digest_text,
                                action=digest["action"],
                                guidance=digest["guidance"],
                            )
                            broadcast_sync(digest_event.to_dict(), discussion_id=self._discussion_id)
                        except Exception:
                            pass

                    # Generate Checkpoint (replaces section summary)
                    self._broadcast_status(self._lead_planner.role, AgentStatus.THINKING)
                    checkpoint = self._generate_checkpoint(
                        round_num, section, round_responses,
                        briefing=self._briefing,
                    )

                    from src.models.checkpoint import CheckpointType
                    from src.api.websocket.events import (
                        create_checkpoint_responded_event,
                        create_decision_announced_event,
                        create_producer_digest_event,
                    )

                    if checkpoint.type == CheckpointType.SILENT:
                        # SILENT: no notification, generate fallback summary for internal use
                        summary = self._lead_planner_section_summary(section.title, round_num, discussion_content)
                        self._broadcast_status(self._lead_planner.role, AgentStatus.SPEAKING)
                        self._broadcast_message(self._lead_planner.role, summary)
                        self._record_message(self._lead_planner.role, summary)
                    elif checkpoint.type == CheckpointType.PROGRESS:
                        # PROGRESS: non-blocking notice
                        self._broadcast_checkpoint_event(checkpoint)
                        self._persist_checkpoint(checkpoint)
                        summary_text = f"[进展通报] {checkpoint.title}: {checkpoint.summary}"
                        self._broadcast_status(self._lead_planner.role, AgentStatus.SPEAKING)
                        self._broadcast_message(self._lead_planner.role, summary_text)
                        self._record_message(self._lead_planner.role, summary_text)
                        summary = summary_text
                    elif checkpoint.type == CheckpointType.DECISION:
                        # DECISION: blocking, wait for user response
                        with self._checkpoint_lock:
                            self._pending_decision_checkpoints[checkpoint.id] = checkpoint
                        self._broadcast_checkpoint_event(checkpoint)
                        self._persist_checkpoint(checkpoint)

                        # Set WAITING_DECISION status
                        from src.api.routes.discussion import (
                            DiscussionStatus as APIDiscussionStatus,
                            get_discussion_state as get_api_state,
                            save_discussion_state,
                            get_current_discussion,
                            set_current_discussion,
                        )
                        api_state = get_api_state(self._discussion_id)
                        if api_state:
                            api_state.status = APIDiscussionStatus.WAITING_DECISION
                            save_discussion_state(api_state)
                            current = get_current_discussion()
                            if current and current.id == self._discussion_id:
                                set_current_discussion(api_state)

                        self._broadcast_discussion_event(f"等待制作人决策：{checkpoint.question}")

                        # Wait for user response
                        response = self._wait_for_decision_response(checkpoint.id)
                        checkpoint.response = response["option_id"]
                        checkpoint.response_text = response["free_input"]
                        checkpoint.responded_at = datetime.utcnow().isoformat()

                        # Broadcast responded event
                        try:
                            resp_event = create_checkpoint_responded_event(
                                self._discussion_id,
                                checkpoint.id,
                                checkpoint.response,
                                checkpoint.response_text,
                                checkpoint.responded_at,
                            )
                            broadcast_sync(resp_event.to_dict(), discussion_id=self._discussion_id)
                        except Exception:
                            pass

                        # Lead planner announces decision
                        self._broadcast_status(self._lead_planner.role, AgentStatus.THINKING)
                        announcement = self._lead_planner_announce_decision(checkpoint)
                        self._broadcast_status(self._lead_planner.role, AgentStatus.SPEAKING)
                        self._broadcast_message(self._lead_planner.role, announcement)
                        self._record_message(self._lead_planner.role, announcement)
                        checkpoint.announced = True
                        self._persist_checkpoint(checkpoint)

                        # Broadcast announced event
                        try:
                            ann_event = create_decision_announced_event(
                                self._discussion_id,
                                checkpoint.id,
                                announcement,
                            )
                            broadcast_sync(ann_event.to_dict(), discussion_id=self._discussion_id)
                        except Exception:
                            pass

                        # Restore RUNNING status
                        if api_state:
                            api_state.status = APIDiscussionStatus.RUNNING
                            save_discussion_state(api_state)
                            current = get_current_discussion()
                            if current and current.id == self._discussion_id:
                                set_current_discussion(api_state)

                        summary = f"[决策] {checkpoint.question} → {checkpoint.response}"
                    else:
                        summary = ""

                    self._broadcast_status(self._lead_planner.role, AgentStatus.IDLE)

                    # Update sliding window of summaries (keep last 2)
                    self._section_summaries.append(f"第{round_num}轮({section.title}): {summary[:500]}")
                    if len(self._section_summaries) > 2:
                        self._section_summaries.pop(0)

                    # Accumulate per-section decisions for compact agent context
                    if summary:
                        self._section_decisions.setdefault(section.id, []).append(
                            f"第{round_num}轮: {summary[:500]}"
                        )

                    # Process agenda directives from summary
                    self._process_agenda_directives(summary, section)

                    # Process document restructure directives from summary
                    self._process_doc_restructure(summary, doc_plan, section)

                    # After replan, current section may no longer exist — skip update
                    f_check, s_check = doc_plan.get_section(section.id)
                    if f_check is None:
                        logger.info("Section %s no longer exists after restructure, skipping update", section.id)
                        self._broadcast_discussion_event(f"第{round_num}轮讨论完成（结构已重规划）")
                        if self._current_discussion:
                            self._current_discussion.doc_plan = doc_plan.to_dict()
                            self._incremental_save()
                        self._broadcast_doc_plan_event(doc_plan)
                        continue

                    # Check if section is done
                    if "章节完成" in summary:
                        section.status = "completed"

                    # DocWriter updates the section — show writing status on lead planner
                    self._broadcast_status(self._lead_planner.role, AgentStatus.WRITING, f"正在更新「{section.title}」")
                    updated = self._doc_writer.update_section(
                        file_plan.filename, section.id, discussion_content, section.title,
                    )
                    self._broadcast_section_update(file_plan.filename, section.id, updated)
                    self._broadcast_status(self._lead_planner.role, AgentStatus.IDLE)

                    # Generate and save round summary
                    round_summary = self._generate_round_summary(round_num, summary)
                    self._save_round_summary(round_summary)
                    self._broadcast_round_summary(round_summary)

                    # Check for pause/intervention (legacy mechanism, kept for compatibility)
                    injected = self._check_pause_and_wait()
                    if self._abort_reason:
                        raise DiscussionTimeoutError(self._abort_reason)
                    # Handle user intervention with digest/assessment pipeline
                    if injected:
                        self._inject_user_messages(injected)
                        # Check for section jump commands first
                        for msg in injected:
                            content = msg.get("content", "")
                            if content.startswith("focus:"):
                                sid = content.split(":", 1)[1].strip()
                                doc_plan.current_section_id = sid
                        # Run intervention digest and assessment pipeline
                        digest = self._lead_planner_digest_intervention(injected, section)
                        assessment = self._assess_intervention_impact(digest, doc_plan, section)
                        self._execute_assessment_actions(assessment, doc_plan)
                        self._lead_planner_post_intervention_guidance(digest, assessment)

                    # Auto-pause
                    if (
                        self._auto_pause_interval > 0
                        and round_num % self._auto_pause_interval == 0
                        and round_num < max_rounds
                    ):
                        self._trigger_auto_pause(round_num)
                        injected = self._check_pause_and_wait()
                        if self._abort_reason:
                            raise DiscussionTimeoutError(self._abort_reason)
                        if injected:
                            self._inject_user_messages(injected)
                            for msg in injected:
                                content = msg.get("content", "")
                                if content.startswith("focus:"):
                                    sid = content.split(":", 1)[1].strip()
                                    doc_plan.current_section_id = sid
                            # Run intervention pipeline for auto-pause injections too
                            digest = self._lead_planner_digest_intervention(injected, section)
                            assessment = self._assess_intervention_impact(digest, doc_plan, section)
                            self._execute_assessment_actions(assessment, doc_plan)
                            self._lead_planner_post_intervention_guidance(digest, assessment)

                    self._broadcast_discussion_event(f"第{round_num}轮讨论完成")

                    # Save doc_plan state after each round (section statuses may have changed)
                    if self._current_discussion:
                        self._current_discussion.doc_plan = doc_plan.to_dict()
                        self._incremental_save()
                    # Broadcast updated doc_plan so frontend sees section status changes
                    self._broadcast_doc_plan_event(doc_plan)

                # Check if all sections are done or rounds exhausted
                all_done = doc_plan.all_sections_completed()

                if all_done:
                    # All sections completed — run holistic review
                    for review_round in range(2):
                        review = self._lead_planner_holistic_review(doc_plan, self._agenda)
                        conclusion = review.get("conclusion", "APPROVED")

                        if conclusion == "APPROVED":
                            logger.info("Holistic review approved on round %d", review_round + 1)
                            break

                        if conclusion in ("NEEDS_REVISION", "NEEDS_NEW_TOPIC", "NEEDS_RESTRUCTURE"):
                            did_restructure = self._execute_review_actions(review, doc_plan, self._agenda)
                            extra_round = 0
                            while extra_round < 3:
                                file_plan, sect = self._pick_next_section(doc_plan)
                                if file_plan is None or sect is None:
                                    break
                                extra_round += 1
                                self._current_round += 1
                                sect.status = "in_progress"
                                doc_plan.current_section_id = sect.id
                                self._broadcast_section_focus(sect.id, sect.title, file_plan.filename)
                                self._broadcast_discussion_event(
                                    f"审视修订轮：聚焦章节「{sect.title}」({file_plan.filename})"
                                )
                                sect_content = self._doc_writer.read_section(file_plan.filename, sect.id)
                                self._broadcast_status(self._lead_planner.role, AgentStatus.THINKING)
                                opening = self._lead_planner_section_opening(sect, sect_content, self._current_round)
                                opening = sanitize_speakers_in_text(opening, known_roles=[a.role for a in self._discussion_agents])
                                self._broadcast_status(self._lead_planner.role, AgentStatus.SPEAKING)
                                self._broadcast_message(self._lead_planner.role, opening)
                                self._record_message(self._lead_planner.role, opening)
                                self._broadcast_status(self._lead_planner.role, AgentStatus.IDLE)

                                next_speakers = parse_next_speakers(opening, known_roles=[a.role for a in self._discussion_agents])

                                # Pause if the speakers block requests producer turn
                                if PRODUCER_ROLE in (next_speakers or []):
                                    self._wait_for_producer_turn()
                                    if self._abort_reason:
                                        raise DiscussionTimeoutError(self._abort_reason)
                                    next_speakers = [s for s in next_speakers if s != PRODUCER_ROLE] or None

                                agents_to_call = (
                                    [a for a in self._discussion_agents if a.role in next_speakers]
                                    if next_speakers else list(self._discussion_agents)
                                )
                                if not agents_to_call:
                                    agents_to_call = list(self._discussion_agents)

                                ctx = self._build_section_context(topic, doc_plan, sect, sect_content, opening)
                                rr, _ = self._run_agents_parallel_sync(agents_to_call, ctx)
                                disc_content = f"主策划：{opening}\n\n"
                                for role, resp in rr:
                                    disc_content += f"{role}：{resp}\n\n"

                                self._broadcast_status(self._lead_planner.role, AgentStatus.THINKING)
                                rev_summary = self._lead_planner_section_summary(sect.title, self._current_round, disc_content)
                                self._broadcast_status(self._lead_planner.role, AgentStatus.SPEAKING)
                                self._broadcast_message(self._lead_planner.role, rev_summary)
                                self._record_message(self._lead_planner.role, rev_summary)
                                self._broadcast_status(self._lead_planner.role, AgentStatus.IDLE)

                                if "章节完成" in rev_summary:
                                    sect.status = "completed"

                                self._broadcast_status(self._lead_planner.role, AgentStatus.WRITING, f"正在更新「{sect.title}」")
                                updated = self._doc_writer.update_section(
                                    file_plan.filename, sect.id, disc_content, sect.title,
                                )
                                self._broadcast_section_update(file_plan.filename, sect.id, updated)
                                self._broadcast_status(self._lead_planner.role, AgentStatus.IDLE)
                        else:
                            break
                    else:
                        # Reached max review iterations without APPROVED
                        self._force_complete_with_notes(review)

                # Save doc_plan final state
                if self._current_discussion:
                    self._current_discussion.doc_plan = doc_plan.to_dict()

                if all_done:
                    self._finalize_trace(trace_span, result="文档驱动讨论完成")
                else:
                    pending = sum(1 for f in doc_plan.files for s in f.sections if s.status != "completed")
                    completed = sum(1 for f in doc_plan.files for s in f.sections if s.status == "completed")
                    self._finalize_trace(trace_span, result=f"轮次耗尽：已完成{completed}，待讨论{pending}")

            # Save discussion
            if all_done:
                self._save_discussion(summary="文档驱动讨论完成")
            else:
                pending = sum(1 for f in doc_plan.files for s in f.sections if s.status != "completed")
                completed = sum(1 for f in doc_plan.files for s in f.sections if s.status == "completed")
                stop_msg = f"已完成 {completed} 个章节的讨论，仍有 {pending} 个章节待讨论。可继续讨论以完成剩余章节。"
                self._broadcast_discussion_event(stop_msg)
                self._save_discussion(summary=stop_msg)

            # Cleanup
            set_discussion_state(self._discussion_id, DiscussionState.FINISHED)
            cleanup_discussion_state(self._discussion_id)

            for agent in self._agents:
                self._broadcast_status(agent.role, AgentStatus.IDLE)
            self._broadcast_discussion_event("discussion_completed")

            if all_done:
                return "文档驱动讨论完成"
            else:
                return f"STOPPED:{stop_msg}"

        except DiscussionTimeoutError:
            self._save_discussion()
            cleanup_discussion_state(self._discussion_id)
            for agent in self._agents:
                self._broadcast_status(agent.role, AgentStatus.IDLE)
            self._broadcast_discussion_event("discussion_completed")
            return "讨论因暂停超时结束"
        except Exception as exc:
            self._finalize_trace(trace_span, error=exc)
            self._broadcast_error(str(exc))
            self._broadcast_discussion_event("discussion_failed")
            self._save_discussion()
            cleanup_discussion_state(self._discussion_id)
            for agent in self._agents:
                self._broadcast_status(agent.role, AgentStatus.IDLE)
            raise
