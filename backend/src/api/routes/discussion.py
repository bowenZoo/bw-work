"""Discussion API routes."""
import asyncio
import hashlib
import hmac
import json
import logging
import os
import threading
import time
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from crewai import Crew, Process
from fastapi import Depends, APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.agents import Summarizer
from src.api.websocket.events import AgentStatus, create_error_event, create_status_event
from src.api.websocket.manager import broadcast_sync
from src.crew.discussion_crew import DiscussionCrew
from src.memory.base import Discussion, Message
from src.memory.discussion_memory import DiscussionMemory
from src.api.routes.auth import get_optional_user, get_current_user as get_auth_user
from src.models.agenda import Agenda, AgendaItem, AgendaItemStatus, AgendaSummaryDetails

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/discussions", tags=["discussions"])

# Memory storage for summaries
_discussion_memory = DiscussionMemory(data_dir="data/projects")

# @超级制作人 questions pending producer response: discussion_id → list of {from_agent, question}
_producer_pending_questions: dict[str, list[dict]] = {}


def push_producer_questions(discussion_id: str, questions: list[dict]) -> None:
    """Store @超级制作人 questions from an agent message (called by WebSocket handler)."""
    if discussion_id not in _producer_pending_questions:
        _producer_pending_questions[discussion_id] = []
    _producer_pending_questions[discussion_id].extend(questions)


def pop_producer_questions(discussion_id: str) -> list[dict]:
    """Retrieve and clear pending @超级制作人 questions for a discussion."""
    return _producer_pending_questions.pop(discussion_id, [])


def has_producer_questions(discussion_id: str) -> bool:
    """Check if there are pending @超级制作人 questions without consuming them."""
    return bool(_producer_pending_questions.get(discussion_id))


class DiscussionStatus(str, Enum):
    """Status of a discussion."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_DECISION = "waiting_decision"  # 等待用户决策
    COMPLETED = "completed"
    STOPPED = "stopped"  # 轮次用完但仍有未讨论 section
    FAILED = "failed"


class AttachmentInfo(BaseModel):
    """Attachment file info."""

    filename: str = Field(..., description="Original filename")
    content: str = Field(..., description="File content")


class CreateDiscussionRequest(BaseModel):
    """Request body for creating a discussion."""

    topic: str = Field(..., min_length=1, description="The discussion topic")
    rounds: int = Field(default=10, ge=1, le=50, description="Number of discussion rounds")
    auto_pause_interval: int = Field(default=5, ge=0, le=50, description="Auto-pause every N rounds (0=disabled)")
    attachment: AttachmentInfo | None = Field(default=None, description="Optional markdown attachment")
    project_id: str = Field(default="default", description="Project this discussion belongs to")
    target_type: str | None = Field(default=None, description="Target type (e.g. 'stage')")
    target_id: str | None = Field(default=None, description="Target ID (e.g. stage ID)")
    agents: list[str] = Field(default_factory=list, description="Agent role names to participate")
    briefing: str = Field(default="", description="Producer briefing / context for AI agents")
    moderator_role: str = Field(default="", description="Moderator agent role (default: lead_planner)")
    producer_stance: str = Field(default="", description="制作人预设立场，引导讨论方向")
    template_id: str = Field(default="", description="讨论模板 ID（可选）")
    agenda_items: list[str] = Field(default_factory=list, description="预设议程条目列表")
    parent_discussion_id: str | None = Field(default=None, description="父讨论 ID（分支讨论用）")
    branch_direction: str = Field(default="", description="分支方向说明")


class CreateDiscussionResponse(BaseModel):
    """Response for creating a discussion."""

    id: str = Field(..., description="Discussion ID")
    topic: str = Field(..., description="The discussion topic")
    rounds: int = Field(..., description="Number of rounds")
    status: DiscussionStatus = Field(..., description="Current status")
    created_at: str = Field(..., description="Creation timestamp")


class DiscussionState(BaseModel):
    """Internal state of a discussion."""

    id: str
    topic: str
    rounds: int
    auto_pause_interval: int = 5
    status: DiscussionStatus
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    result: str | None = None
    error: str | None = None
    attachment: AttachmentInfo | None = None
    continued_from: str | None = None  # 原讨论 ID（如果是续前讨论）
    agents: list[str] = Field(default_factory=list)  # 参与的 agent role_name 列表
    agent_configs: dict = Field(default_factory=dict)  # role_name -> config 覆盖
    discussion_style: str = ""  # 讨论风格 (socratic/directive/debate)
    password_hash: str = ""  # 空字符串表示无密码
    briefing: str = ""  # 制作人 briefing
    project_id: str = "default"  # 所属项目
    target_type: str | None = None  # 关联类型（如 "stage"）
    target_id: str | None = None  # 关联 ID（如 stage ID）
    moderator_role: str = ""  # 主持 agent（留空=lead_planner）
    quality_score: dict | None = None  # 讨论质量评分 {completeness, executability, consensus, overall}
    dependency_hints: list[str] = Field(default_factory=list)  # 跨阶段依赖提示
    producer_stance: str = ""  # 制作人预设立场（比 briefing 更聚焦的方向指引）
    viewer_questions: list[dict] = Field(default_factory=list)  # 观众提问队列
    agenda_items: list[str] = Field(default_factory=list)  # 预设议程条目
    votes: dict = Field(default_factory=dict)  # {role: {support/oppose/neutral: count}}
    number_validation: list[dict] | None = None  # 数值校验结果
    parent_discussion_id: str | None = None  # 父讨论 ID（分支讨论）
    branch_direction: str = ""  # 分支方向说明
    synced_document_id: str | None = None  # 已同步到的文档 ID
    decisions: list[dict] = Field(default_factory=list)  # 决策日志 [{text, round, timestamp}]
    tags: list[str] = Field(default_factory=list)  # 自动打标签
    agenda_progress: list[dict] = Field(default_factory=list)  # 议程进度 [{item, done}]


class GetDiscussionResponse(BaseModel):
    """Response for getting discussion status."""

    id: str
    topic: str
    rounds: int
    status: DiscussionStatus
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    result: str | None = None
    error: str | None = None
    attachment: AttachmentInfo | None = None
    continued_from: str | None = None  # 原讨论 ID
    is_continuation: bool = False  # 是否是续前讨论
    discussion_style: str = ""  # 讨论风格
    has_password: bool = False  # 是否有密码保护
    briefing: str = ""  # 制作人 briefing
    project_id: str = "default"  # 所属项目
    target_type: str | None = None  # 关联类型
    target_id: str | None = None  # 关联 ID
    moderator_role: str = ""  # 主持 agent
    agents: list[str] = Field(default_factory=list, description="参与讨论的 agent 角色列表")
    quality_score: dict | None = None  # 讨论质量评分
    dependency_hints: list[str] = Field(default_factory=list)  # 跨阶段依赖提示
    producer_stance: str = ""  # 制作人预设立场
    viewer_questions: list[dict] = Field(default_factory=list)  # 观众提问
    agenda_items: list[str] = Field(default_factory=list)  # 预设议程
    votes: dict = Field(default_factory=dict)  # Agent 投票结果
    number_validation: list[dict] | None = None  # 数值自动校验结果
    parent_discussion_id: str | None = None  # 父讨论（分支）
    branch_direction: str = ""  # 分支方向
    synced_document_id: str | None = None  # 已同步到的文档 ID
    decisions: list[dict] = Field(default_factory=list)  # 决策日志
    tags: list[str] = Field(default_factory=list)  # 自动标签
    agenda_progress: list[dict] = Field(default_factory=list)  # 议程进度


class StartDiscussionResponse(BaseModel):
    """Response for starting a discussion."""

    id: str
    status: DiscussionStatus
    message: str


class SummarizeRequest(BaseModel):
    """Request body for generating a summary."""

    regenerate: bool = Field(default=False, description="Force regenerate summary even if one exists")


class ContinueDiscussionRequest(BaseModel):
    """Request body for continuing a discussion."""

    follow_up: str = Field(default="", description="Follow-up topic or question to continue discussing (optional)")
    rounds: int = Field(default=2, ge=1, le=10, description="Number of additional discussion rounds")


class ContinueDiscussionResponse(BaseModel):
    """Response for continuing a discussion."""

    new_discussion_id: str = Field(..., description="ID of the new continuation discussion")
    original_discussion_id: str = Field(..., description="ID of the original discussion")
    topic: str = Field(..., description="Combined topic for the continuation")
    status: DiscussionStatus = Field(..., description="Current status")
    message: str = Field(..., description="Status message")


class VerifyPasswordRequest(BaseModel):
    """Request body for verifying a discussion password."""

    password: str = Field(..., description="Password to verify")


class VerifyPasswordResponse(BaseModel):
    """Response for verifying a discussion password."""

    verified: bool


class ExtendDiscussionRequest(BaseModel):
    """Request body for extending a completed discussion with more rounds."""

    follow_up: str = Field(default="", description="Follow-up topic or question")
    additional_rounds: int = Field(default=10, ge=1, le=100, description="Additional rounds to discuss")
    discussion_style: str = Field(default="", description="Discussion style override (socratic, directive, debate)")
    agent_configs: dict = Field(default_factory=dict, description="Agent config overrides")


class ExtendDiscussionResponse(BaseModel):
    """Response for extending a discussion."""

    id: str = Field(..., description="Discussion ID (same as original)")
    topic: str = Field(..., description="Discussion topic")
    status: DiscussionStatus = Field(..., description="Current status")
    message: str = Field(..., description="Status message")


class SummaryResponse(BaseModel):
    """Response containing discussion summary."""

    discussion_id: str
    topic: str
    summary: str
    key_points: list[str] = Field(default_factory=list)
    agreements: list[str] = Field(default_factory=list)
    disagreements: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    generated_at: str


class DiscussionSummaryItem(BaseModel):
    """Summary item for discussion list."""

    id: str
    project_id: str
    topic: str
    summary: str | None = None
    message_count: int = 0
    doc_count: int = 0
    status: str | None = None
    created_at: str
    updated_at: str
    owner_id: int | None = None
    owner_name: str | None = None
    owner_avatar: str | None = None


class DiscussionListResponse(BaseModel):
    """Response for listing discussions."""

    items: list[DiscussionSummaryItem]
    hasMore: bool = Field(default=False, alias="hasMore")


class MessageResponse(BaseModel):
    """Response for a message."""

    id: str
    agent_id: str
    agent_role: str
    content: str
    timestamp: str


class DiscussionMessagesResponse(BaseModel):
    """Response for discussion messages."""

    discussion: DiscussionSummaryItem
    messages: list[MessageResponse]


class CreateCurrentDiscussionRequest(BaseModel):
    """Request body for creating a new global discussion."""

    topic: str = Field(..., min_length=1, description="The discussion topic")
    project_id: str = Field(default="default", description="Project to create discussion in")
    rounds: int = Field(default=10, ge=1, le=50, description="Number of discussion rounds")
    auto_pause_interval: int = Field(default=5, ge=0, le=50, description="Auto-pause every N rounds (0=disabled)")
    attachment: AttachmentInfo | None = Field(default=None, description="Optional markdown attachment")
    agents: list[str] = Field(default_factory=list, description="Agent role names to participate")
    agent_configs: dict = Field(default_factory=dict, description="Per-agent config overrides")
    discussion_style: str = Field(default="", description="Discussion style (socratic, directive, debate)")
    password: str = Field(default="", description="Discussion password (empty string for no password)")
    briefing: str = Field(default="", description="Producer briefing: background, constraints, expected output")


class CreateCurrentDiscussionResponse(BaseModel):
    """Response for creating a global discussion."""

    id: str = Field(..., description="Discussion ID")
    topic: str = Field(..., description="The discussion topic")
    rounds: int = Field(..., description="Number of rounds")
    status: DiscussionStatus = Field(..., description="Current status")
    created_at: str = Field(..., description="Creation timestamp")
    message: str | None = Field(default=None, description="Optional status message")


class JoinDiscussionResponse(BaseModel):
    """Response for joining the current discussion."""

    discussion: GetDiscussionResponse | None = Field(None, description="Current discussion if exists")
    messages: list[MessageResponse] = Field(default_factory=list, description="Historical messages")


# Discussion state persistence
_STATE_DIR = Path(os.environ.get("DISCUSSION_STATUS_DIR", "data/projects/.discussion_state"))
_state_lock = threading.Lock()
_DISCUSSION_EXECUTOR = ThreadPoolExecutor(
    max_workers=int(os.environ.get("DISCUSSION_MAX_WORKERS", "8"))
)

# In-memory cache for quick reads (also persisted to disk)
_discussions: dict[str, DiscussionState] = {}

# Hold references to background tasks to prevent GC before completion
_background_tasks: set[asyncio.Task] = set()

# Store generated summaries
_summaries: dict[str, SummaryResponse] = {}

# Running crew instances (for API access to agenda/doc_plan)
_running_crews: dict[str, "DiscussionCrew"] = {}

# Global discussion state (single active discussion for all users)
_current_discussion: DiscussionState | None = None
_current_discussion_lock = threading.RLock()

# Per-discussion agent statuses: discussion_id -> {agent_id -> status}
_per_discussion_agent_statuses: dict[str, dict[str, str]] = {}

# Per-discussion agent status started_at timestamps: discussion_id -> {agent_id -> ISO timestamp}
_per_discussion_agent_started_at: dict[str, dict[str, str]] = {}

# Discussion concurrency control
_discussion_semaphore: threading.Semaphore | None = None
_semaphore_lock = threading.Lock()


def _get_discussion_semaphore() -> threading.Semaphore:
    """Get or create the discussion concurrency semaphore.

    Reads max_concurrent from admin config (discussion category).
    Default is 2 if not configured.
    """
    global _discussion_semaphore
    with _semaphore_lock:
        if _discussion_semaphore is None:
            try:
                from src.admin.config_store import ConfigStore
                store = ConfigStore()
                max_concurrent = int(store.get_raw("discussion", "max_concurrent") or "2")
            except Exception:
                max_concurrent = 2
            _discussion_semaphore = threading.Semaphore(max_concurrent)
            logger.info("Discussion semaphore initialized: max_concurrent=%d", max_concurrent)
    return _discussion_semaphore


def reset_discussion_semaphore() -> None:
    """Reset the semaphore so it re-reads config on next access."""
    global _discussion_semaphore
    with _semaphore_lock:
        _discussion_semaphore = None
    logger.info("Discussion semaphore reset")


def get_current_discussion() -> DiscussionState | None:
    """Get the current global discussion.

    Returns:
        The current discussion state, or None if no discussion is active.
    """
    with _current_discussion_lock:
        return _current_discussion


def get_agent_statuses(discussion_id: str | None = None) -> dict[str, str]:
    """Get current agent statuses for a discussion."""
    if discussion_id:
        return dict(_per_discussion_agent_statuses.get(discussion_id, {}))
    return {}


def get_agent_started_at(discussion_id: str | None = None) -> dict[str, str]:
    """Get timestamps for when each agent entered their current active status."""
    if discussion_id:
        return dict(_per_discussion_agent_started_at.get(discussion_id, {}))
    return {}


def set_agent_status(discussion_id: str, agent_id: str, status: str) -> None:
    """Update a single agent's status for a discussion."""
    from datetime import datetime, timezone

    old_status = _per_discussion_agent_statuses.get(discussion_id, {}).get(agent_id)
    _per_discussion_agent_statuses.setdefault(discussion_id, {})[agent_id] = status

    active_statuses = {"thinking", "speaking", "writing"}
    if status in active_statuses and old_status != status:
        _per_discussion_agent_started_at.setdefault(discussion_id, {})[agent_id] = (
            datetime.now(timezone.utc).isoformat()
        )
    elif status not in active_statuses:
        _per_discussion_agent_started_at.get(discussion_id, {}).pop(agent_id, None)


def reset_agent_statuses(discussion_id: str | None = None) -> None:
    """Reset agent statuses. If discussion_id given, reset only that discussion."""
    if discussion_id:
        _per_discussion_agent_statuses.pop(discussion_id, None)
        _per_discussion_agent_started_at.pop(discussion_id, None)
    else:
        _per_discussion_agent_statuses.clear()
        _per_discussion_agent_started_at.clear()


def cleanup_stale_discussions() -> int:
    """Clean up stale 'running' discussions on server startup.

    Any discussion stuck in 'running' state is marked as 'failed'
    since the background task cannot survive a server restart.
    Also ensures the discussion exists in DiscussionMemory so it
    appears in the discussion list.

    Returns:
        Number of discussions cleaned up.
    """
    cleaned = 0
    if not _STATE_DIR.exists():
        return cleaned

    for path in _STATE_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("status") in (DiscussionStatus.RUNNING, DiscussionStatus.QUEUED, "queued"):
                data["status"] = DiscussionStatus.FAILED
                data["error"] = "服务器重启，讨论中断"
                data["completed_at"] = datetime.utcnow().isoformat()
                path.write_text(
                    json.dumps(data, ensure_ascii=False), encoding="utf-8"
                )

                # Ensure the discussion exists in DiscussionMemory
                disc_id = data.get("id")
                if disc_id:
                    stored = _discussion_memory.load(disc_id)
                    if stored is None:
                        # Discussion was never saved to DiscussionMemory
                        # Create a minimal entry so it appears in list
                        from src.memory.base import Discussion as DiscussionRecord
                        created_at_str = data.get("created_at", datetime.utcnow().isoformat())
                        try:
                            created_at = datetime.fromisoformat(created_at_str)
                        except (ValueError, TypeError):
                            created_at = datetime.utcnow()
                        disc_record = DiscussionRecord(
                            id=disc_id,
                            project_id="default",
                            topic=data.get("topic", "未知话题"),
                            messages=[],
                            summary="讨论因服务器重启中断",
                            created_at=created_at,
                            updated_at=datetime.now(),
                        )
                        _discussion_memory.save(disc_record)
                        logger.info("Saved stale discussion to DiscussionMemory: %s", disc_id)

                logger.info("Cleaned up stale discussion: %s", data.get("id"))
                cleaned += 1
        except Exception as e:
            logger.warning("Failed to clean up %s: %s", path, e)

    # Also clear the in-memory current discussion
    global _current_discussion
    with _current_discussion_lock:
        if _current_discussion and _current_discussion.status in (DiscussionStatus.RUNNING, DiscussionStatus.QUEUED):
            _current_discussion = None

    return cleaned


def restore_latest_discussion() -> None:
    """Restore the most recent discussion as the current discussion on startup.

    Scans persisted state files and loads the newest one, so that clients
    connecting via WebSocket can see the last discussion's topic and messages.
    Only restores if no current discussion is set (avoids overwriting a valid one).

    Should be called from lifespan handler after cleanup_stale_discussions().
    """
    global _current_discussion
    with _current_discussion_lock:
        if _current_discussion is not None:
            return  # Don't overwrite an existing (e.g. completed) discussion

    if not _STATE_DIR.exists():
        logger.info("No state directory found at %s, nothing to restore", _STATE_DIR.resolve())
        return

    latest: DiscussionState | None = None
    latest_time = ""
    file_count = 0

    for path in _STATE_DIR.glob("*.json"):
        file_count += 1
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            created_at = data.get("created_at", "")
            if created_at > latest_time:
                latest_time = created_at
                latest = DiscussionState(**data)
        except Exception as e:
            logger.warning("Failed to parse state file %s: %s", path, e)

    if latest is not None:
        with _current_discussion_lock:
            _current_discussion = latest
        logger.info(
            "Restored latest discussion on startup: id=%s, status=%s, topic=%s",
            latest.id, latest.status, latest.topic[:50],
        )
    else:
        logger.info("No restorable discussion found (%d state files scanned)", file_count)


def set_current_discussion(discussion: DiscussionState | None) -> None:
    """Set the current global discussion.

    Args:
        discussion: The discussion to set as current, or None to clear.
    """
    global _current_discussion
    with _current_discussion_lock:
        _current_discussion = discussion


def _validate_discussion_id(discussion_id: str) -> bool:
    """Validate discussion_id is a safe filename (UUID or alphanumeric with hyphens)."""
    import re
    return bool(re.match(r'^[a-zA-Z0-9_-]+$', discussion_id))


def _state_path(discussion_id: str) -> Path:
    if not _validate_discussion_id(discussion_id):
        raise ValueError(f"Invalid discussion_id: {discussion_id}")
    path = _STATE_DIR / f"{discussion_id}.json"
    # Ensure resolved path is still under _STATE_DIR
    if not path.resolve().is_relative_to(_STATE_DIR.resolve()):
        raise ValueError(f"Invalid discussion_id: {discussion_id}")
    return path


def _persist_discussion_state(discussion: DiscussionState) -> None:
    try:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        _state_path(discussion.id).write_text(
            json.dumps(discussion.model_dump(), ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as e:
        logger.warning("Failed to persist discussion state %s: %s", discussion.id, e)


def _load_discussion_state(discussion_id: str) -> DiscussionState | None:
    path = _state_path(discussion_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return DiscussionState(**data)
    except Exception:
        return None


def get_discussion_state(discussion_id: str) -> DiscussionState | None:
    with _state_lock:
        discussion = _discussions.get(discussion_id)
        if discussion is not None:
            return discussion
        discussion = _load_discussion_state(discussion_id)
        if discussion is not None:
            _discussions[discussion_id] = discussion
        return discussion


def save_discussion_state(discussion: DiscussionState) -> None:
    with _state_lock:
        _discussions[discussion.id] = discussion
        _persist_discussion_state(discussion)


def _get_llm_from_config() -> Any | None:
    """Get LLM instance from admin config store (active profile).

    Supports both OpenAI-compatible and Anthropic-native providers.
    For Anthropic: set base_url to the proxy (e.g. https://anyrouter.top)
    and model to a claude-* name (without anthropic/ prefix).

    Returns:
        LLM instance if configured, None otherwise.
    """
    try:
        from src.admin.config_store import ConfigStore

        store = ConfigStore()
        config = store.get_active_llm_config()

        if not config or not config.get("api_key"):
            logger.warning("No active LLM profile configured in admin store")
            return None

        api_key = config["api_key"]
        base_url = config.get("base_url") or ""
        model = config.get("model") or "gpt-4"

        # Strip provider prefix if present (e.g. "anthropic/claude-opus-4-6" -> "claude-opus-4-6")
        raw_model = model.split("/", 1)[-1] if "/" in model else model

        # Detect if this is an Anthropic model
        is_anthropic = raw_model.startswith("claude")

        if is_anthropic:
            # Use ChatAnthropic for native Anthropic API support
            from langchain_anthropic import ChatAnthropic
            import anthropic as _anthropic

            # Set env vars for CrewAI compatibility
            os.environ["ANTHROPIC_API_KEY"] = api_key
            if base_url:
                os.environ["ANTHROPIC_BASE_URL"] = base_url

            # Patch user_agent so ALL Anthropic SDK instances in this process
            # (including CrewAI's own AnthropicCompletion) send the allowed UA.
            _anthropic._base_client.BaseClient.user_agent = property(
                lambda self: "claude-code/1.0"
            )

            llm_kwargs: dict[str, Any] = {
                "model": raw_model,
                "anthropic_api_key": api_key,
                "timeout": 180,
                "max_retries": 5,
                "default_headers": {
                    "anthropic-version": "2023-06-01",
                    "User-Agent": "claude-code/1.0",
                },
            }
            if base_url:
                llm_kwargs["anthropic_api_url"] = base_url

            logger.info("Creating ChatAnthropic: model=%s, base_url=%s, profile=%s", raw_model, base_url, config.get("name", ""))
            return ChatAnthropic(**llm_kwargs)
        else:
            # Use ChatOpenAI for OpenAI-compatible providers
            from langchain_openai import ChatOpenAI

            os.environ["OPENAI_API_KEY"] = api_key
            if base_url:
                os.environ["OPENAI_API_BASE"] = base_url
                os.environ["OPENAI_BASE_URL"] = base_url
            os.environ["OPENAI_MODEL_NAME"] = model

            llm_kwargs = {
                "model": model,
                "api_key": api_key,
                "timeout": 180,
                "max_retries": 5,
            }
            if base_url:
                llm_kwargs["base_url"] = base_url

            logger.info("Creating ChatOpenAI: model=%s, base_url=%s, profile=%s", model, base_url, config.get("name", ""))
            return ChatOpenAI(**llm_kwargs)
    except ImportError as e:
        logger.error("Error importing LLM provider: %s", e)
        return None
    except Exception as e:
        logger.error("Error creating LLM from config: %s", e)
        return None


def _compute_dependency_hints(project_id: str, current_stage_id: str) -> list[str]:
    """从已完成的阶段讨论中提取关键决策，作为当前阶段的依赖提示。

    Args:
        project_id: 项目 ID
        current_stage_id: 当前阶段 ID（跳过本阶段自身）

    Returns:
        最多 5 条依赖提示字符串列表
    """
    hints: list[str] = []
    # 从 _discussions 内存字典中找同项目的已完成 stage 讨论
    for disc_id, disc_state in list(_discussions.items()):
        if disc_state.project_id != project_id:
            continue
        if disc_state.status not in (DiscussionStatus.COMPLETED, DiscussionStatus.STOPPED):
            continue
        if disc_state.target_id == current_stage_id:
            continue  # 跳过本阶段
        if not disc_state.result:
            continue
        # 从结果中提取最重要的一句话（结果前 200 字）
        snippet = disc_state.result[:200].replace("\n", " ").strip()
        stage_label = disc_state.target_id or disc_state.topic
        hint = f"【{stage_label}】{snippet}…"
        hints.append(hint)
        if len(hints) >= 5:
            break

    # 如果内存中没有，从持久化文件中查
    if not hints:
        state_dir = _STATE_DIR
        if state_dir.exists():
            for state_file in sorted(state_dir.glob("*.json"), reverse=True)[:50]:
                try:
                    disc_state = _load_discussion_state(state_file.stem)
                    if not disc_state:
                        continue
                    if disc_state.project_id != project_id:
                        continue
                    if disc_state.status not in (DiscussionStatus.COMPLETED, DiscussionStatus.STOPPED):
                        continue
                    if disc_state.target_id == current_stage_id:
                        continue
                    if not disc_state.result:
                        continue
                    snippet = disc_state.result[:200].replace("\n", " ").strip()
                    stage_label = disc_state.target_id or disc_state.topic
                    hint = f"【{stage_label}】{snippet}…"
                    hints.append(hint)
                    if len(hints) >= 5:
                        break
                except Exception:
                    continue
    return hints


def _compute_quality_score(discussion_id: str) -> dict | None:
    """根据讨论消息内容计算三维度质量评分。

    三个维度（各 1-10 分）：
    - completeness（完整性）：话题覆盖率、是否有明确结论
    - executability（可执行性）：具体决策数量、行动项明确度
    - consensus（共识度）：团队一致性程度

    Returns:
        Dict with completeness, executability, consensus, overall (各 1-10)，失败返回 None。
    """
    stored = _discussion_memory.load(discussion_id)
    if stored is None or not stored.messages:
        return None

    full_text = "\n".join(m.content for m in stored.messages)
    msg_count = len(stored.messages)

    # --- 完整性：有结论区块、议题数量 ---
    conclusion_keywords = ["最终决策", "关键决策", "设计概述", "决策点", "结论", "总结", "已确定"]
    conclusion_hits = sum(1 for kw in conclusion_keywords if kw in full_text)
    completeness = min(10, max(1, 2 + conclusion_hits * 1.5 + (1 if msg_count >= 10 else 0)))

    # --- 可执行性：行动项、优先级、具体方案 ---
    action_keywords = ["P0", "P1", "P2", "实现", "方案", "决定", "采用", "具体", "执行", "落地", "负责", "下一步"]
    action_hits = sum(full_text.count(kw) for kw in action_keywords)
    executability = min(10, max(1, 1 + action_hits * 0.3))

    # --- 共识度：同意 vs 分歧 ---
    agree_keywords = ["同意", "支持", "赞同", "确实", "对的", "没问题", "可以", "好的"]
    disagree_keywords = ["但是", "不同意", "反对", "问题", "风险", "待定", "不确定", "存疑"]
    agree_count = sum(full_text.count(kw) for kw in agree_keywords)
    disagree_count = sum(full_text.count(kw) for kw in disagree_keywords)
    total = agree_count + disagree_count + 1  # 防除零
    consensus = min(10, max(1, round(1 + 9 * (agree_count / total))))

    overall = round((completeness + executability + consensus) / 3, 1)
    return {
        "completeness": round(completeness, 1),
        "executability": round(executability, 1),
        "consensus": round(consensus, 1),
        "overall": overall,
        "message_count": msg_count,
    }


def _auto_organize_docs(discussion_id: str) -> None:
    """Auto-organize discussion results into design documents.

    Called after discussion completes. Failures are logged but do not
    affect the discussion state.
    """
    from src.agents.doc_organizer import DocOrganizer

    stored = _discussion_memory.load(discussion_id)
    if stored is None or not stored.messages:
        logger.info("Skipping auto-organize for %s: no messages found", discussion_id)
        return

    llm = _get_llm_from_config()
    if llm is None:
        logger.warning("Skipping auto-organize for %s: LLM not configured", discussion_id)
        return

    organizer = DocOrganizer(llm=llm)
    result = organizer.run_organize(stored)
    logger.info(
        "Auto-organized %s: %d documents generated",
        discussion_id,
        len(result.files),
    )


def _run_discussion_sync(discussion_id: str) -> None:
    """Run a discussion synchronously (for background task).

    Project discussions (with project_id) bypass the global semaphore and run
    immediately in parallel.  Only standalone lobby discussions are throttled by
    the concurrency semaphore.
    """
    logger.info("Starting discussion %s in background thread", discussion_id)
    discussion = get_discussion_state(discussion_id)
    if discussion is None:
        logger.error("Discussion %s not found, aborting", discussion_id)
        return

    # Project discussions run in parallel — skip the global semaphore
    is_project_discussion = bool(discussion.project_id)

    if is_project_discussion:
        semaphore = None
        _do_run_discussion(discussion_id, discussion, semaphore)
        return

    # Lobby/standalone discussions: throttle via semaphore
    semaphore = _get_discussion_semaphore()

    # Mark as queued while waiting for a slot
    discussion.status = DiscussionStatus.QUEUED
    save_discussion_state(discussion)
    current = get_current_discussion()
    if current and current.id == discussion_id:
        set_current_discussion(discussion)
    broadcast_sync(
        {
            "type": "status",
            "data": {
                "discussion_id": discussion_id,
                "agent_id": "discussion",
                "agent_role": "discussion",
                "content": "discussion_queued",
                "status": "queued",
                "timestamp": datetime.utcnow().isoformat(),
            },
        },
        lobby_event=True,
    )

    semaphore.acquire()
    try:
        _do_run_discussion(discussion_id, get_discussion_state(discussion_id), semaphore)
    finally:
        semaphore.release()


def _do_run_discussion(
    discussion_id: str,
    discussion: "DiscussionState | None",
    semaphore: "threading.Semaphore | None",
) -> None:
    """Core discussion runner. Called after semaphore is acquired (or bypassed)."""
    if discussion is None:
        return

    try:
        # Transition to running
        discussion.status = DiscussionStatus.RUNNING
        if discussion.started_at is None:
            discussion.started_at = datetime.utcnow().isoformat()
        save_discussion_state(discussion)

        current = get_current_discussion()
        if current and current.id == discussion_id:
            set_current_discussion(discussion)
        broadcast_sync(
            {
                "type": "status",
                "data": {
                    "discussion_id": discussion_id,
                    "agent_id": "discussion",
                    "agent_role": "discussion",
                    "content": "discussion_running",
                    "status": "running",
                    "timestamp": datetime.utcnow().isoformat(),
                },
            },
            lobby_event=True,
        )

        # Get LLM from admin config store
        llm = _get_llm_from_config()
        if llm is None:
            raise RuntimeError("LLM not configured. Please configure OpenAI API key in admin panel.")

        crew = DiscussionCrew(
            discussion_id=discussion_id,
            llm=llm,
            enable_visual_concept=True,
            agent_roles=discussion.agents or None,
            agent_configs=discussion.agent_configs or None,
            project_id=discussion.project_id,
            moderator_role=discussion.moderator_role or None,
        )
        # Share semaphore with crew so it can release/re-acquire during
        # WAITING_DECISION, allowing other discussions to run concurrently.
        crew._concurrency_semaphore = semaphore
        _running_crews[discussion_id] = crew
        result = crew.run_document_centric(
            topic=discussion.topic,
            max_rounds=discussion.rounds,
            attachment=discussion.attachment.content if discussion.attachment else None,
            auto_pause_interval=discussion.auto_pause_interval,
            briefing=discussion.briefing or "",
            producer_stance=discussion.producer_stance or "",
            agenda_items=discussion.agenda_items or [],
        )

        if result.startswith("STOPPED:"):
            discussion.result = result[len("STOPPED:"):]
            discussion.status = DiscussionStatus.STOPPED
        else:
            discussion.result = result
            discussion.status = DiscussionStatus.COMPLETED
        discussion.completed_at = datetime.utcnow().isoformat()
        save_discussion_state(discussion)

        # Update global discussion state if this is the current discussion
        current = get_current_discussion()
        if current and current.id == discussion_id:
            set_current_discussion(discussion)

        # Compute quality score
        try:
            score = _compute_quality_score(discussion_id)
            if score:
                discussion.quality_score = score
                save_discussion_state(discussion)
        except Exception as score_err:
            logger.warning("Quality score failed for %s: %s", discussion_id, score_err)

        # Save agent opinions archive
        try:
            _save_agent_opinions(discussion.project_id, discussion_id, discussion)
        except Exception as op_err:
            logger.warning("Agent opinions archive failed for %s: %s", discussion_id, op_err)

        # Compute agent votes
        try:
            votes = _compute_agent_votes(discussion_id)
            if votes:
                discussion.votes = votes
                save_discussion_state(discussion)
        except Exception as vote_err:
            logger.warning("Agent votes failed for %s: %s", discussion_id, vote_err)

        # Number validation
        try:
            validation = _validate_numbers(discussion_id)
            if validation is not None:
                discussion.number_validation = validation
                save_discussion_state(discussion)
        except Exception as num_err:
            logger.warning("Number validation failed for %s: %s", discussion_id, num_err)

        # Update cross-project agent memory
        try:
            _update_agent_cross_memory(discussion_id, discussion)
        except Exception as mem_err:
            logger.warning("Cross-project memory update failed for %s: %s", discussion_id, mem_err)

        # Extract decisions and auto-tag
        try:
            _extract_decisions(discussion_id, discussion)
            _auto_tag_discussion(discussion_id, discussion)
        except Exception as tag_err:
            logger.warning("Decision/tag extraction failed for %s: %s", discussion_id, tag_err)

        # Auto-organize discussion into design documents
        try:
            _auto_organize_docs(discussion_id)
        except Exception as org_err:
            logger.warning("Auto-organize failed for %s: %s", discussion_id, org_err)

    except Exception as e:
        logger.error("Discussion %s failed: %s", discussion_id, e)
        discussion.status = DiscussionStatus.FAILED
        discussion.error = str(e)
        discussion.completed_at = datetime.utcnow().isoformat()
        save_discussion_state(discussion)

        # Broadcast failure to WebSocket clients
        try:
            error_event = create_error_event(
                discussion_id=discussion_id,
                content=str(e),
            )
            broadcast_sync(error_event.to_dict(), discussion_id=discussion_id)
            status_event = create_status_event(
                discussion_id=discussion_id,
                agent_id="discussion",
                agent_role="discussion",
                status=AgentStatus.IDLE,
                content="discussion_failed",
            )
            broadcast_sync(status_event.to_dict(), discussion_id=discussion_id)
        except Exception:
            logger.debug("Failed to broadcast discussion failure event")

        # Update global discussion state if this is the current discussion
        current = get_current_discussion()
        if current and current.id == discussion_id:
            set_current_discussion(discussion)
    finally:
        _running_crews.pop(discussion_id, None)


async def _run_discussion_async(discussion_id: str) -> None:
    """Run discussion in a dedicated thread pool to avoid blocking the event loop."""
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(_DISCUSSION_EXECUTOR, _run_discussion_sync, discussion_id)
    except Exception as e:
        logger.error("Discussion async wrapper failed for %s: %s", discussion_id, e, exc_info=True)


def _run_discussion_extend_sync(
    discussion_id: str,
    follow_up: str,
    additional_rounds: int,
) -> None:
    """Run discussion extension synchronously (for background task).

    Acquires the concurrency semaphore before running.  While waiting,
    the discussion is in QUEUED state.
    """
    logger.info("Extending discussion %s (+%d rounds)", discussion_id, additional_rounds)
    discussion = get_discussion_state(discussion_id)
    if discussion is None:
        logger.error("Discussion %s not found for extend", discussion_id)
        return

    semaphore = _get_discussion_semaphore()

    # Mark as queued while waiting for a slot
    discussion.status = DiscussionStatus.QUEUED
    save_discussion_state(discussion)
    current = get_current_discussion()
    if current and current.id == discussion_id:
        set_current_discussion(discussion)
    broadcast_sync(
        {
            "type": "status",
            "data": {
                "discussion_id": discussion_id,
                "agent_id": "discussion",
                "agent_role": "discussion",
                "content": "discussion_queued",
                "status": "queued",
                "timestamp": datetime.utcnow().isoformat(),
            },
        },
        discussion_id=discussion_id,
        lobby_event=True,
    )

    # Block until a concurrency slot is available
    semaphore.acquire()
    try:
        # Re-read state in case it was cancelled while queued
        discussion = get_discussion_state(discussion_id)
        if discussion is None:
            return

        # Transition from queued to running
        discussion.status = DiscussionStatus.RUNNING
        save_discussion_state(discussion)
        current = get_current_discussion()
        if current and current.id == discussion_id:
            set_current_discussion(discussion)
        broadcast_sync(
            {
                "type": "status",
                "data": {
                    "discussion_id": discussion_id,
                    "agent_id": "discussion",
                    "agent_role": "discussion",
                    "content": "discussion_running",
                    "status": "running",
                    "timestamp": datetime.utcnow().isoformat(),
                },
            },
            discussion_id=discussion_id,
            lobby_event=True,
        )

        try:
            llm = _get_llm_from_config()
            if llm is None:
                raise RuntimeError("LLM not configured.")

            # Merge old agent list with any newly added agents so that
            # continuing old discussions automatically includes new roles
            # (e.g. operations_analyst added after the discussion was created).
            extend_roles = discussion.agents or None
            if extend_roles is not None:
                all_available = set(DiscussionCrew.AVAILABLE_AGENTS.keys())
                extend_roles = list(set(extend_roles) | all_available)

            crew = DiscussionCrew(
                discussion_id=discussion_id,
                llm=llm,
                enable_visual_concept=True,
                agent_roles=extend_roles,
                agent_configs=discussion.agent_configs or None,
                project_id=discussion.project_id,
            )
            crew._concurrency_semaphore = semaphore
            _running_crews[discussion_id] = crew

            # Choose extend method based on whether discussion has a doc_plan
            stored = _discussion_memory.load(discussion_id)
            if stored and stored.doc_plan:
                result = crew.extend_document_centric(
                    topic=discussion.topic,
                    follow_up=follow_up,
                    additional_rounds=additional_rounds,
                )
            else:
                result = crew.extend_orchestrated(
                    topic=discussion.topic,
                    follow_up=follow_up,
                    additional_rounds=additional_rounds,
                )

            if result.startswith("STOPPED:"):
                discussion.result = result[len("STOPPED:"):]
                discussion.status = DiscussionStatus.STOPPED
            else:
                discussion.result = result
                discussion.status = DiscussionStatus.COMPLETED
            discussion.completed_at = datetime.utcnow().isoformat()
            save_discussion_state(discussion)

            current = get_current_discussion()
            if current and current.id == discussion_id:
                set_current_discussion(discussion)

            try:
                _auto_organize_docs(discussion_id)
            except Exception as org_err:
                logger.warning("Auto-organize failed for extend %s: %s", discussion_id, org_err)

        except Exception as e:
            logger.error("Discussion extend %s failed: %s", discussion_id, e)
            discussion.status = DiscussionStatus.FAILED
            discussion.error = str(e)
            discussion.completed_at = datetime.utcnow().isoformat()
            save_discussion_state(discussion)

            try:
                error_event = create_error_event(
                    discussion_id=discussion_id, content=str(e)
                )
                broadcast_sync(error_event.to_dict(), discussion_id=discussion_id)
                status_event = create_status_event(
                    discussion_id=discussion_id,
                    agent_id="discussion",
                    agent_role="discussion",
                    status=AgentStatus.IDLE,
                    content="discussion_failed",
                )
                broadcast_sync(status_event.to_dict(), discussion_id=discussion_id)
            except Exception:
                logger.debug("Failed to broadcast extend failure event")

            current = get_current_discussion()
            if current and current.id == discussion_id:
                set_current_discussion(discussion)
    finally:
        _running_crews.pop(discussion_id, None)
        semaphore.release()


async def _run_discussion_extend_async(
    discussion_id: str,
    follow_up: str,
    additional_rounds: int,
) -> None:
    """Run discussion extension in thread pool."""
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            _DISCUSSION_EXECUTOR,
            _run_discussion_extend_sync,
            discussion_id,
            follow_up,
            additional_rounds,
        )
    except Exception as e:
        logger.error("Extend async wrapper failed for %s: %s", discussion_id, e, exc_info=True)


def _get_doc_count(discussion_id: str, project_id: str = "default") -> int:
    """Get the number of design documents for a discussion.

    Checks real-time docs directory first (DocWriter output during discussion),
    then falls back to DocOrganizer index.
    """
    # Check real-time docs directory first
    try:
        rt_dir = Path("data/projects") / project_id / discussion_id / "docs"
        if rt_dir.exists():
            count = len(list(rt_dir.glob("*.md")))
            if count > 0:
                return count
    except Exception:
        pass

    # Fallback to DocOrganizer index
    try:
        from src.agents.doc_organizer import DocOrganizer
        organizer = DocOrganizer()
        index = organizer.load_index(project_id, discussion_id)
        if index and "files" in index:
            return len(index["files"])
    except Exception:
        pass
    return 0



@router.post("/migrate-project", tags=["projects"])
async def migrate_discussions_to_project(
    from_project: str = "default",
    to_project: str = "default",
    user: dict = Depends(get_auth_user),
):
    """Migrate all discussions from one project to another. Superadmin only."""
    if user.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin only")
    all_discs = _discussion_memory.list_all(offset=0, limit=10000)
    migrated = 0
    for disc in all_discs:
        if disc.project_id == from_project:
            _discussion_memory.set_project_id(disc.id, to_project)
            migrated += 1
    return {"migrated": migrated, "from": from_project, "to": to_project}


@router.get("/count-by-project", tags=["projects"])
async def count_discussions_by_project(project_id: str):
    """Get discussion count for a project."""
    count = _discussion_memory.count_by_project(project_id)
    return {"project_id": project_id, "count": count}


@router.get("", response_model=DiscussionListResponse)
async def list_discussions(
    page: int = 1,
    limit: int = 20,
    all: bool = False,
    project_id: str = None,
    user: dict = Depends(get_optional_user),
) -> DiscussionListResponse:
    """List all discussions with pagination.

    Returns a paginated list of discussions sorted by creation time (newest first).
    """
    offset = (page - 1) * limit

    # If filtering by a specific project, show all discussions in that project (for public spaces like lobby)
    # Otherwise filter by owner for personal views
    if project_id:
        # Show all discussions in this project regardless of owner
        memory_discussions = _discussion_memory.list_all(offset=offset, limit=limit + 1)
    elif user and not all:
        memory_discussions = _discussion_memory.list_by_owner(user["id"], offset=offset, limit=limit + 1)
    elif user and all and user.get("role") == "superadmin":
        memory_discussions = _discussion_memory.list_all(offset=offset, limit=limit + 1)
    else:
        # Not authenticated: show all (backward compat)
        memory_discussions = _discussion_memory.list_all(offset=offset, limit=limit + 1)

    items = []
    for disc in memory_discussions[:limit]:
        # Look up status from DiscussionState (disk/memory)
        state = get_discussion_state(disc.id)
        status = state.status.value if state else "completed"
        owner_id = _discussion_memory.get_owner_id(disc.id)
        owner_name = None
        owner_avatar = None
        if owner_id:
            from ...admin.database import AdminDatabase
            _adb = AdminDatabase()
            with _adb.get_cursor() as cursor:
                cursor.execute("SELECT username, avatar FROM users WHERE id = ?", (owner_id,))
                row = cursor.fetchone()
                if row:
                    owner_name = row["username"]
                    owner_avatar = row["avatar"] if "avatar" in row.keys() else None
        items.append(
            DiscussionSummaryItem(
                id=disc.id,
                project_id=disc.project_id,
                topic=disc.topic,
                owner_id=owner_id,
                owner_name=owner_name,
                owner_avatar=owner_avatar,
                summary=disc.summary,
                message_count=len(disc.messages),
                doc_count=_get_doc_count(disc.id, disc.project_id),
                status=status,
                created_at=disc.created_at.isoformat(),
                updated_at=disc.updated_at.isoformat(),
            )
        )

    # If memory has no results, also check in-memory state
    if not items:
        state_items = []
        with _state_lock:
            for disc_id, disc in _discussions.items():
                state_items.append(
                    DiscussionSummaryItem(
                        id=disc.id,
                        project_id=getattr(disc, 'project_id', 'default'),
                        topic=disc.topic,
                        summary=disc.result[:200] if disc.result else None,
                        message_count=0,
                        status=disc.status.value,
                        created_at=disc.created_at,
                        updated_at=disc.completed_at or disc.started_at or disc.created_at,
                    )
                )
        # Sort by created_at descending
        state_items.sort(key=lambda x: x.created_at, reverse=True)
        items = state_items[offset : offset + limit]

    # Also include running discussions from in-memory state that aren't in memory store yet
    seen_ids = {i.id for i in items}
    with _state_lock:
        for disc_id, disc in _discussions.items():
            if disc_id not in seen_ids and disc.status in (DiscussionStatus.RUNNING, DiscussionStatus.QUEUED, DiscussionStatus.PENDING):
                owner_id = _discussion_memory.get_owner_id(disc_id)
                owner_name = None
                if owner_id:
                    from ...admin.database import AdminDatabase
                    _adb = AdminDatabase()
                    with _adb.get_cursor() as cursor:
                        cursor.execute("SELECT username FROM users WHERE id = ?", (owner_id,))
                        row = cursor.fetchone()
                        if row:
                            owner_name = row["username"]
                items.append(
                    DiscussionSummaryItem(
                        id=disc.id,
                        project_id=getattr(disc, 'project_id', 'default'),
                        topic=disc.topic,
                        owner_id=owner_id,
                        owner_name=owner_name,
                        summary=None,
                        message_count=0,
                        status=disc.status.value,
                        created_at=disc.created_at,
                        updated_at=disc.completed_at or disc.started_at or disc.created_at,
                    )
                )

    # Filter by project_id if specified
    if project_id:
        items = [i for i in items if i.project_id == project_id]

    has_more = len(memory_discussions) > limit or (not memory_discussions and len(items) == limit)

    return DiscussionListResponse(items=items, hasMore=has_more)


# ==============================================================================
# Global Discussion API (single active discussion for all users)
# ==============================================================================


@router.get("/current", response_model=GetDiscussionResponse | None)
async def get_current_discussion_api() -> GetDiscussionResponse | None:
    """Get the current global active discussion.

    Returns the current discussion if one exists, or None if no discussion is active.
    """
    discussion = get_current_discussion()
    if discussion is None:
        return None

    return GetDiscussionResponse(
        id=discussion.id,
        topic=discussion.topic,
        rounds=discussion.rounds,
        status=discussion.status,
        created_at=discussion.created_at,
        started_at=discussion.started_at,
        completed_at=discussion.completed_at,
        result=discussion.result,
        error=discussion.error,
        attachment=discussion.attachment,
        continued_from=discussion.continued_from,
        is_continuation=discussion.continued_from is not None,
        discussion_style=discussion.discussion_style,
        has_password=bool(discussion.password_hash),
        briefing=discussion.briefing,
    )


@router.post("/current", response_model=CreateCurrentDiscussionResponse)
async def create_current_discussion(
    request: CreateCurrentDiscussionRequest,
) -> CreateCurrentDiscussionResponse:
    """Create a new global discussion (replacing the current one).

    If a discussion is already running, returns it instead of creating a new one.
    The discussion is automatically started after creation.
    """
    with _current_discussion_lock:
        # Always allow creating new discussions (no longer block if one is running)
        # Create new discussion
        discussion_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        # Merge discussion style into agent_configs
        agent_configs = dict(request.agent_configs) if request.agent_configs else {}
        if request.discussion_style:
            from src.config.settings import get_discussion_style_overrides
            style_overrides = get_discussion_style_overrides(request.discussion_style)
            if style_overrides is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"未知的讨论风格: {request.discussion_style}",
                )
            lead_config = dict(agent_configs.get("lead_planner", {}))
            lead_config.update(style_overrides)
            agent_configs["lead_planner"] = lead_config

        # 计算密码哈希（使用 discussion_id 作为盐值）
        pwd = request.password or ""
        password_hash = hashlib.sha256(f"{discussion_id}:{pwd}".encode()).hexdigest() if pwd else ""

        discussion = DiscussionState(
            id=discussion_id,
            topic=request.topic,
            rounds=request.rounds,
            auto_pause_interval=request.auto_pause_interval,
            status=DiscussionStatus.RUNNING,
            created_at=now,
            started_at=now,
            attachment=request.attachment,
            agents=request.agents or [],
            agent_configs=agent_configs,
            discussion_style=request.discussion_style or "",
            password_hash=password_hash,
            briefing=request.briefing or "",
            project_id=request.project_id or "default",
        )

        # _current_discussion points to the most recently created discussion
        set_current_discussion(discussion)
        save_discussion_state(discussion)

    # Run in background (outside the lock)
    task = asyncio.create_task(_run_discussion_async(discussion_id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    # Notify lobby WebSocket clients about the new discussion
    broadcast_sync(
        {
            "type": "status",
            "data": {
                "discussion_id": discussion_id,
                "agent_id": "discussion",
                "agent_role": "discussion",
                "content": "discussion_created",
                "topic": request.topic,
                "rounds": request.rounds,
                "status": "running",
                "agents": request.agents or [],
                "timestamp": now,
            },
        },
        lobby_event=True,
    )

    return CreateCurrentDiscussionResponse(
        id=discussion_id,
        topic=request.topic,
        rounds=request.rounds,
        status=DiscussionStatus.RUNNING,
        created_at=now,
        message=None,
    )


@router.post("/current/join", response_model=JoinDiscussionResponse)
async def join_current_discussion() -> JoinDiscussionResponse:
    """Join the current global discussion and get historical messages.

    Returns the current discussion state and all historical messages.
    If no discussion is active, returns empty data.
    """
    discussion = get_current_discussion()
    if discussion is None:
        return JoinDiscussionResponse(discussion=None, messages=[])

    # Load historical messages from memory
    stored = _discussion_memory.load(discussion.id)
    messages: list[MessageResponse] = []
    if stored and stored.messages:
        messages = [
            MessageResponse(
                id=msg.id,
                agent_id=msg.agent_id,
                agent_role=msg.agent_role,
                content=msg.content,
                timestamp=msg.timestamp.isoformat(),
            )
            for msg in stored.messages
        ]

    return JoinDiscussionResponse(
        discussion=GetDiscussionResponse(
            id=discussion.id,
            topic=discussion.topic,
            rounds=discussion.rounds,
            status=discussion.status,
            created_at=discussion.created_at,
            started_at=discussion.started_at,
            completed_at=discussion.completed_at,
            result=discussion.result,
            error=discussion.error,
            attachment=discussion.attachment,
            continued_from=discussion.continued_from,
            is_continuation=discussion.continued_from is not None,
            discussion_style=discussion.discussion_style,
            has_password=bool(discussion.password_hash),
            briefing=discussion.briefing,
        ),
        messages=messages,
    )


# ==============================================================================
# Original Discussion API (per-discussion operations)
# ==============================================================================


@router.post("", response_model=CreateDiscussionResponse)
async def create_discussion(
    request: CreateDiscussionRequest,
    user: dict = Depends(get_optional_user),
) -> CreateDiscussionResponse:
    """Create a new discussion.

    This creates a discussion in PENDING state. Call /start to begin the discussion.
    """
    discussion_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    discussion = DiscussionState(
        id=discussion_id,
        topic=request.topic,
        rounds=request.rounds,
        auto_pause_interval=request.auto_pause_interval,
        status=DiscussionStatus.PENDING,
        created_at=now,
        attachment=request.attachment,
        project_id=request.project_id,
        target_type=request.target_type,
        target_id=request.target_id,
        agents=request.agents or [],
        briefing=request.briefing or "",
        moderator_role=request.moderator_role or "",
        producer_stance=request.producer_stance or "",
        agenda_items=request.agenda_items or [],
        parent_discussion_id=request.parent_discussion_id,
        branch_direction=request.branch_direction or "",
    )

    # 计算跨阶段依赖提示（只有 stage 讨论才触发）
    if request.target_type == "stage" and request.project_id and request.project_id != "default":
        try:
            discussion.dependency_hints = _compute_dependency_hints(
                request.project_id, request.target_id or ""
            )
        except Exception as dep_err:
            logger.warning("Dependency hints failed: %s", dep_err)

    save_discussion_state(discussion)

    # Set owner_id if user is authenticated
    if user:
        _discussion_memory.set_owner_id(discussion_id, user["id"])

    return CreateDiscussionResponse(
        id=discussion_id,
        topic=request.topic,
        rounds=request.rounds,
        status=DiscussionStatus.PENDING,
        created_at=now,
    )


@router.get("/styles")
async def get_discussion_styles():
    """获取可用的讨论风格列表（含完整 overrides）。"""
    from src.config.settings import load_discussion_styles
    data = load_discussion_styles()
    default_style = data.get("default", "socratic")
    styles = []
    for style_id, style_def in data.get("styles", {}).items():
        styles.append({
            "id": style_id,
            "name": style_def.get("name", style_id),
            "description": style_def.get("description", ""),
            "overrides": style_def.get("overrides", {}),
        })
    return {"default": default_style, "styles": styles}


@router.get("/active")
async def list_active_discussions():
    """返回所有 running/paused 状态的讨论。"""
    active = []
    seen_ids: set[str] = set()

    # Check in-memory cache
    with _state_lock:
        for did, state in _discussions.items():
            if state.status in (DiscussionStatus.RUNNING, DiscussionStatus.PENDING, DiscussionStatus.QUEUED):
                seen_ids.add(did)
                active.append({
                    "id": state.id,
                    "topic": state.topic,
                    "rounds": state.rounds,
                    "status": state.status.value,
                    "created_at": state.created_at,
                    "agents": state.agents,
                    "project_id": getattr(state, 'project_id', 'default'),
                })

    # Also check disk state files for any not yet in memory
    if _STATE_DIR.exists():
        for path in _STATE_DIR.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                did = data.get("id", "")
                if did in seen_ids:
                    continue
                if data.get("status") in ("running", "pending", "queued"):
                    seen_ids.add(did)
                    active.append({
                        "id": did,
                        "topic": data.get("topic", ""),
                        "rounds": data.get("rounds", 0),
                        "status": data.get("status", ""),
                        "created_at": data.get("created_at", ""),
                        "agents": data.get("agents", []),
                        "project_id": data.get("project_id", "default"),
                    })
            except Exception:
                pass

    return {"discussions": active}


@router.get("/available-agents")
async def list_available_agents():
    """返回所有可用 Agent 及其默认配置。"""
    from src.config.settings import load_role_config

    agents = {}
    for role_name in [
        "lead_planner",
        "system_designer",
        "number_designer",
        "player_advocate",
        "operations_analyst",
        "visual_concept",
    ]:
        try:
            config = load_role_config(role_name)
            agents[role_name] = {
                "role": config.get("role", ""),
                "goal": config.get("goal", ""),
                "backstory": config.get("backstory", ""),
                "focus_areas": config.get("focus_areas", []),
            }
        except Exception:
            pass
    return {"agents": agents}


# 密码验证速率限制: {discussion_id: [timestamps]}
_verify_attempts: dict[str, list[float]] = defaultdict(list)
_VERIFY_MAX_ATTEMPTS = 5  # 每分钟最多 5 次
_VERIFY_WINDOW = 60  # 60 秒窗口


@router.post("/{discussion_id}/verify", response_model=VerifyPasswordResponse)
async def verify_discussion_password(discussion_id: str, request: VerifyPasswordRequest):
    """验证讨论密码。

    如果讨论无密码保护，直接返回 verified=True。
    密码正确返回 verified=True，错误返回 403。
    """
    # 速率限制检查
    now = time.time()
    attempts = _verify_attempts[discussion_id]
    _verify_attempts[discussion_id] = [t for t in attempts if now - t < _VERIFY_WINDOW]
    if len(_verify_attempts[discussion_id]) >= _VERIFY_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="尝试次数过多，请稍后再试")
    _verify_attempts[discussion_id].append(now)

    discussion = get_discussion_state(discussion_id)
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")

    if not discussion.password_hash:
        return VerifyPasswordResponse(verified=True)

    input_hash = hashlib.sha256(f"{discussion_id}:{request.password}".encode()).hexdigest()
    if hmac.compare_digest(input_hash, discussion.password_hash):
        return VerifyPasswordResponse(verified=True)
    else:
        raise HTTPException(status_code=403, detail="密码错误")


# NOTE: /templates, /search, /compare, /batch must be registered BEFORE /{discussion_id} to avoid route shadowing
@router.get("/templates")
async def get_discussion_templates_early(
    stage: str | None = None,
    user=Depends(get_optional_user),
):
    """获取讨论模板列表。可按 stage 过滤。"""
    templates = _DISCUSSION_TEMPLATES
    if stage:
        templates = [t for t in templates if t.get("stage") == stage]
    return {"templates": templates}


@router.get("/search")
async def search_discussions_early(
    q: str = "",
    project_id: str = "",
    limit: int = 20,
    user=Depends(get_optional_user),
):
    """全文搜索讨论（提前注册，防止被 /{discussion_id} 遮盖）。"""
    if not q.strip():
        return {"results": [], "total": 0, "query": q}
    q_lower = q.lower()
    results = []
    for disc_id, disc in list(_discussions.items()):
        if project_id and disc.project_id != project_id:
            continue
        matched_topic = q_lower in disc.topic.lower()
        matched_messages: list[dict] = []
        try:
            for msg in _discussion_memory.get_messages(disc_id):
                content = getattr(msg, "content", "") or ""
                if q_lower in content.lower():
                    idx = content.lower().find(q_lower)
                    start, end = max(0, idx - 40), min(len(content), idx + len(q) + 40)
                    snippet = ("..." if start > 0 else "") + content[start:end] + ("..." if end < len(content) else "")
                    matched_messages.append({"agent_role": getattr(msg, "agent_role", ""), "snippet": snippet, "timestamp": getattr(msg, "timestamp", "")})
                    if len(matched_messages) >= 3:
                        break
        except Exception:
            pass
        if matched_topic or matched_messages:
            results.append({"discussion_id": disc_id, "topic": disc.topic, "project_id": disc.project_id, "status": disc.status, "created_at": disc.created_at, "tags": disc.tags, "matched_topic": matched_topic, "matched_messages": matched_messages, "match_count": len(matched_messages) + (1 if matched_topic else 0)})
    results.sort(key=lambda x: x["match_count"], reverse=True)
    return {"results": results[:limit], "total": len(results[:limit]), "query": q}


@router.get("/compare")
async def compare_discussions_early(
    id_a: str,
    id_b: str,
    user=Depends(get_optional_user),
):
    """讨论对比（提前注册）。"""
    disc_a = _discussions.get(id_a)
    disc_b = _discussions.get(id_b)
    if not disc_a or not disc_b:
        raise HTTPException(status_code=404, detail="One or both discussions not found")

    def _summary(disc: DiscussionState, disc_id: str) -> dict:
        s = _summaries.get(disc_id)
        return {"id": disc_id, "topic": disc.topic, "status": disc.status, "tags": disc.tags, "votes": disc.votes, "decisions": disc.decisions[:5], "quality_score": disc.quality_score, "parent_discussion_id": disc.parent_discussion_id, "branch_direction": disc.branch_direction, "summary": s.summary[:300] if s else None, "key_points": s.key_points[:5] if s else [], "agreements": s.agreements[:5] if s else []}

    return {"discussion_a": _summary(disc_a, id_a), "discussion_b": _summary(disc_b, id_b), "shared_tags": list(set(disc_a.tags) & set(disc_b.tags))}


@router.get("/{discussion_id}", response_model=GetDiscussionResponse)
async def get_discussion(discussion_id: str) -> GetDiscussionResponse:
    """Get the status and result of a discussion."""
    discussion = get_discussion_state(discussion_id)
    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    return GetDiscussionResponse(
        id=discussion.id,
        topic=discussion.topic,
        rounds=discussion.rounds,
        status=discussion.status,
        created_at=discussion.created_at,
        started_at=discussion.started_at,
        completed_at=discussion.completed_at,
        result=discussion.result,
        error=discussion.error,
        attachment=discussion.attachment,
        continued_from=discussion.continued_from,
        is_continuation=discussion.continued_from is not None,
        discussion_style=discussion.discussion_style,
        has_password=bool(discussion.password_hash),
        briefing=discussion.briefing,
        project_id=discussion.project_id,
        target_type=discussion.target_type,
        target_id=discussion.target_id,
        moderator_role=discussion.moderator_role or "",
        agents=discussion.agents or [],
        quality_score=discussion.quality_score,
        dependency_hints=discussion.dependency_hints,
        producer_stance=discussion.producer_stance,
        viewer_questions=discussion.viewer_questions,
        agenda_items=discussion.agenda_items,
        votes=discussion.votes,
        number_validation=discussion.number_validation,
        parent_discussion_id=discussion.parent_discussion_id,
        branch_direction=discussion.branch_direction,
        synced_document_id=discussion.synced_document_id,
        decisions=discussion.decisions,
        tags=discussion.tags,
        agenda_progress=discussion.agenda_progress,
    )


@router.post("/{discussion_id}/start", response_model=StartDiscussionResponse)
async def start_discussion(
    discussion_id: str,
) -> StartDiscussionResponse:
    """Start a discussion.

    The discussion will run in the background. Poll GET /discussions/{id}
    to check the status and get the result.
    """
    discussion = get_discussion_state(discussion_id)
    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    if discussion.status != DiscussionStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Discussion cannot be started: current status is {discussion.status}",
        )

    # Mark as running before enqueuing to avoid duplicate starts.
    discussion.status = DiscussionStatus.RUNNING
    discussion.started_at = datetime.utcnow().isoformat()
    save_discussion_state(discussion)

    # Run in background
    task = asyncio.create_task(_run_discussion_async(discussion_id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return StartDiscussionResponse(
        id=discussion_id,
        status=DiscussionStatus.RUNNING,
        message="Discussion started. Poll GET /api/discussions/{id} for status.",
    )


def _generate_summary_sync(discussion_id: str, discussion: DiscussionState) -> SummaryResponse:
    """Generate a summary for a discussion synchronously.

    Args:
        discussion_id: The discussion ID.
        discussion: The discussion state.

    Returns:
        Generated SummaryResponse.
    """
    # Try to load discussion from memory first
    stored_discussion = _discussion_memory.load(discussion_id)

    if stored_discussion and stored_discussion.messages:
        # Use stored messages
        messages = stored_discussion.messages
    else:
        # Create mock messages from result if available
        messages = []
        if discussion.result:
            messages = [
                Message(
                    id="result",
                    agent_id="discussion",
                    agent_role="Discussion",
                    content=discussion.result,
                    timestamp=datetime.now(),
                )
            ]

    # Create a Discussion object for the summarizer
    disc = Discussion(
        id=discussion_id,
        project_id="default",
        topic=discussion.topic,
        messages=messages,
        created_at=datetime.fromisoformat(discussion.created_at.replace("Z", "+00:00"))
        if discussion.created_at
        else datetime.now(),
    )

    # Use summarizer to generate summary
    summarizer = Summarizer()
    task = summarizer.create_summary_task(disc)

    # Run the summarization
    crew = Crew(
        agents=[summarizer.build_agent()],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )

    result = crew.kickoff()
    raw_summary = str(result)

    # Parse the summary
    parsed = summarizer.parse_summary(raw_summary, disc)

    now = datetime.utcnow().isoformat()

    return SummaryResponse(
        discussion_id=discussion_id,
        topic=discussion.topic,
        summary=raw_summary,
        key_points=parsed.key_points,
        agreements=parsed.agreements,
        disagreements=parsed.disagreements,
        open_questions=parsed.open_questions,
        next_steps=parsed.next_steps,
        generated_at=now,
    )


@router.post("/{discussion_id}/summarize", response_model=SummaryResponse)
async def summarize_discussion(
    discussion_id: str,
    request: SummarizeRequest | None = None,
) -> SummaryResponse:
    """Generate a summary for a completed discussion.

    The discussion must be in COMPLETED state. Summaries are cached
    and can be regenerated with the regenerate flag.
    """
    discussion = get_discussion_state(discussion_id)
    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    if discussion.status != DiscussionStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Discussion cannot be summarized: current status is {discussion.status}",
        )

    # Check for cached summary
    regenerate = request.regenerate if request else False
    if not regenerate and discussion_id in _summaries:
        return _summaries[discussion_id]

    # Generate summary in executor to avoid blocking event loop
    import asyncio
    loop = asyncio.get_event_loop()
    summary = await loop.run_in_executor(
        None, _generate_summary_sync, discussion_id, discussion
    )
    _summaries[discussion_id] = summary

    # Also save to discussion memory
    stored_discussion = _discussion_memory.load(discussion_id)
    if stored_discussion:
        stored_discussion.summary = summary.summary
        _discussion_memory.save(stored_discussion)

    return summary


def _build_continuation_context(
    original: DiscussionState,
    stored: Discussion,
    follow_up: str,
    max_messages_per_agent: int = 2,
) -> str:
    """构建继续讨论的上下文。

    Args:
        original: 原讨论状态
        stored: 存储的讨论数据
        follow_up: 用户的追加问题/方向
        max_messages_per_agent: 每个角色保留的最近消息数量

    Returns:
        格式化的上下文字符串
    """
    context_parts = [
        "## 前序讨论上下文",
        "",
        f"### 原始话题: {original.topic}",
        "",
    ]

    # 添加摘要
    if stored.summary:
        context_parts.extend([
            "### 讨论总结",
            stored.summary[:2000],  # 限制长度
            "",
        ])

    # 提取每个角色的最后几条消息
    if stored.messages:
        context_parts.append("### 关键讨论内容")
        agent_messages: dict[str, list[str]] = {}
        for msg in stored.messages:
            if msg.agent_role not in agent_messages:
                agent_messages[msg.agent_role] = []
            agent_messages[msg.agent_role].append(msg.content[:500])

        for role, contents in agent_messages.items():
            # 取最后 N 条
            recent = contents[-max_messages_per_agent:]
            for content in recent:
                context_parts.append(f"**{role}**: {content}...")
        context_parts.append("")

    # 添加继续讨论部分
    context_parts.extend([
        "---",
        "",
        "## 继续讨论",
        "",
    ])
    if follow_up:
        context_parts.extend([
            "用户希望在以上讨论基础上，继续探讨以下问题：",
            "",
            f"**{follow_up}**",
        ])
    else:
        context_parts.append("用户希望在以上讨论基础上，继续深入探讨原话题。")

    return "\n".join(context_parts)


@router.post("/{discussion_id}/continue", response_model=ContinueDiscussionResponse)
async def continue_discussion(
    discussion_id: str,
    request: ContinueDiscussionRequest,
) -> ContinueDiscussionResponse:
    """Continue a completed discussion with a follow-up topic.

    Creates a new discussion that builds upon the original discussion's context.
    The new discussion will include the previous discussion's summary and decisions
    as context for the agents.
    """
    # Check if original discussion exists and is completed
    original = get_discussion_state(discussion_id)
    if original is None:
        raise HTTPException(status_code=404, detail="Original discussion not found")

    if original.status not in (DiscussionStatus.COMPLETED, DiscussionStatus.STOPPED):
        raise HTTPException(
            status_code=400,
            detail=f"Can only continue completed or stopped discussions. Current status: {original.status}",
        )

    # Load the original discussion from memory to get full context
    stored_discussion = _discussion_memory.load(discussion_id)
    if stored_discussion is None:
        # Fall back to just using the result
        stored_discussion = Discussion(
            id=discussion_id,
            project_id="default",
            topic=original.topic,
            messages=[],
            summary=original.result,
            created_at=datetime.now(),
        )

    # 使用独立函数构建上下文
    combined_context = _build_continuation_context(
        original=original,
        stored=stored_discussion,
        follow_up=request.follow_up,
        max_messages_per_agent=2,
    )

    # Create new discussion with context
    new_discussion_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    if request.follow_up:
        combined_topic = f"[继续] {original.topic} - {request.follow_up[:50]}"
    else:
        combined_topic = f"[继续] {original.topic}"

    # Create attachment with context
    attachment = AttachmentInfo(
        filename="previous_discussion_context.md",
        content=combined_context,
    )

    new_discussion = DiscussionState(
        id=new_discussion_id,
        topic=combined_topic,
        rounds=request.rounds,
        status=DiscussionStatus.PENDING,
        created_at=now,
        attachment=attachment,
        continued_from=discussion_id,  # 记录原讨论 ID
    )
    save_discussion_state(new_discussion)

    # Auto-start the new discussion
    new_discussion.status = DiscussionStatus.RUNNING
    new_discussion.started_at = now
    save_discussion_state(new_discussion)

    # Run in background
    task = asyncio.create_task(_run_discussion_async(new_discussion_id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return ContinueDiscussionResponse(
        new_discussion_id=new_discussion_id,
        original_discussion_id=discussion_id,
        topic=combined_topic,
        status=DiscussionStatus.RUNNING,
        message="继续讨论已开始，新讨论将基于之前的上下文进行。",
    )


@router.post("/{discussion_id}/extend", response_model=ExtendDiscussionResponse)
async def extend_discussion(
    discussion_id: str,
    request: ExtendDiscussionRequest,
) -> ExtendDiscussionResponse:
    """Extend a completed discussion with additional rounds.

    Unlike /continue which creates a new discussion, /extend resumes the
    same discussion in-place, preserving the discussion ID and all history.
    """
    discussion = get_discussion_state(discussion_id)
    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    if discussion.status not in (DiscussionStatus.COMPLETED, DiscussionStatus.STOPPED, DiscussionStatus.FAILED):
        raise HTTPException(
            status_code=400,
            detail=f"Only completed, stopped, or failed discussions can be extended. Current: {discussion.status}",
        )

    # Merge request agent_configs into existing discussion agent_configs
    agent_configs = dict(discussion.agent_configs) if discussion.agent_configs else {}
    if request.agent_configs:
        agent_configs = {**agent_configs, **request.agent_configs}

    # Merge discussion style into agent_configs if provided
    if request.discussion_style:
        from src.config.settings import get_discussion_style_overrides
        style_overrides = get_discussion_style_overrides(request.discussion_style)
        if style_overrides is None:
            raise HTTPException(
                status_code=400,
                detail=f"未知的讨论风格: {request.discussion_style}",
            )
        lead_config = dict(agent_configs.get("lead_planner", {}))
        lead_config.update(style_overrides)
        agent_configs["lead_planner"] = lead_config
        discussion.discussion_style = request.discussion_style

    discussion.agent_configs = agent_configs

    # Re-activate the discussion (queued until semaphore slot available)
    discussion.status = DiscussionStatus.QUEUED
    discussion.completed_at = None
    discussion.error = None
    discussion.rounds += request.additional_rounds
    save_discussion_state(discussion)

    # Update global discussion state
    with _current_discussion_lock:
        set_current_discussion(discussion)

    # Run in background (sync function handles queued→running transition)
    task = asyncio.create_task(
        _run_discussion_extend_async(
            discussion_id, request.follow_up, request.additional_rounds
        )
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return ExtendDiscussionResponse(
        id=discussion_id,
        topic=discussion.topic,
        status=DiscussionStatus.QUEUED,
        message=f"讨论已加入队列，将进行 {request.additional_rounds} 轮追加讨论。",
    )


@router.get("/{discussion_id}/messages", response_model=DiscussionMessagesResponse)
async def get_discussion_messages(discussion_id: str) -> DiscussionMessagesResponse:
    """Get all messages for a discussion.

    Returns the discussion with all its messages for playback.
    """
    # First, try to load from persistent memory
    stored_discussion = _discussion_memory.load(discussion_id)

    if stored_discussion:
        return DiscussionMessagesResponse(
            discussion=DiscussionSummaryItem(
                id=stored_discussion.id,
                project_id=stored_discussion.project_id,
                topic=stored_discussion.topic,
                summary=stored_discussion.summary,
                message_count=len(stored_discussion.messages),
                created_at=stored_discussion.created_at.isoformat(),
                updated_at=stored_discussion.updated_at.isoformat(),
            ),
            messages=[
                MessageResponse(
                    id=msg.id,
                    agent_id=msg.agent_id,
                    agent_role=msg.agent_role,
                    content=msg.content,
                    timestamp=msg.timestamp.isoformat(),
                )
                for msg in stored_discussion.messages
            ],
        )

    # Fall back to in-memory state
    discussion = get_discussion_state(discussion_id)
    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    # For in-memory state, we don't have individual messages
    return DiscussionMessagesResponse(
        discussion=DiscussionSummaryItem(
            id=discussion.id,
            project_id="default",
            topic=discussion.topic,
            summary=discussion.result[:200] if discussion.result else None,
            message_count=1 if discussion.result else 0,
            created_at=discussion.created_at,
            updated_at=discussion.completed_at or discussion.started_at or discussion.created_at,
        ),
        messages=[
            MessageResponse(
                id="result",
                agent_id="discussion",
                agent_role="Discussion",
                content=discussion.result or "",
                timestamp=discussion.completed_at or discussion.created_at,
            )
        ]
        if discussion.result
        else [],
    )


class RoundSummaryItem(BaseModel):
    """A single round summary."""

    round: int
    content: str
    key_points: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    generated_at: str


class RoundSummariesResponse(BaseModel):
    """Response for round summaries."""

    discussion_id: str
    summaries: list[RoundSummaryItem]


@router.get("/{discussion_id}/round-summaries", response_model=RoundSummariesResponse)
async def get_round_summaries(discussion_id: str) -> RoundSummariesResponse:
    """Get all round summaries for a discussion.

    Returns structured round-by-round summaries generated during the discussion.
    """
    stored = _discussion_memory.load(discussion_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    summaries = [
        RoundSummaryItem(
            round=s.get("round", 0),
            content=s.get("content", ""),
            key_points=s.get("key_points", []),
            open_questions=s.get("open_questions", []),
            generated_at=s.get("generated_at", ""),
        )
        for s in (stored.round_summaries or [])
    ]

    return RoundSummariesResponse(
        discussion_id=discussion_id,
        summaries=summaries,
    )


@router.get("/{discussion_id}/summary", response_model=SummaryResponse)
async def get_discussion_summary(discussion_id: str) -> SummaryResponse:
    """Get the summary of a discussion.

    Returns the cached summary if available. Call POST /summarize first
    to generate a summary.
    """
    discussion = get_discussion_state(discussion_id)
    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    if discussion_id not in _summaries:
        # Try to load from memory
        stored_discussion = _discussion_memory.load(discussion_id)
        if stored_discussion and stored_discussion.summary:
            # Create response from stored summary
            return SummaryResponse(
                discussion_id=discussion_id,
                topic=discussion.topic,
                summary=stored_discussion.summary,
                key_points=[],
                agreements=[],
                disagreements=[],
                open_questions=[],
                next_steps=[],
                generated_at=stored_discussion.updated_at.isoformat()
                if stored_discussion.updated_at
                else datetime.utcnow().isoformat(),
            )
        raise HTTPException(
            status_code=404,
            detail="Summary not found. Call POST /api/discussions/{id}/summarize first.",
        )

    return _summaries[discussion_id]


# ==============================================================================
# Discussion Chain API
# ==============================================================================


class DiscussionChainItem(BaseModel):
    """讨论链中的单个讨论项。"""

    id: str
    topic: str
    summary: str | None = None
    status: DiscussionStatus
    created_at: str
    is_origin: bool = False  # 是否是链的起点


class DiscussionChainResponse(BaseModel):
    """讨论链响应。"""

    chain: list[DiscussionChainItem]  # 从最早到最新
    current_index: int  # 当前讨论在链中的位置


@router.get("/{discussion_id}/chain", response_model=DiscussionChainResponse)
async def get_discussion_chain(discussion_id: str) -> DiscussionChainResponse:
    """获取讨论链（原讨论 → 续前讨论 → ...）。

    返回从最早的原始讨论到当前讨论的完整链。
    """
    # 首先检查讨论是否存在
    current = get_discussion_state(discussion_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    chain: list[DiscussionChainItem] = []
    visited: set[str] = set()

    # 向前追溯到原始讨论
    trace_id: str | None = discussion_id
    while trace_id and trace_id not in visited:
        visited.add(trace_id)
        disc = get_discussion_state(trace_id)
        if disc is None:
            break

        # 尝试获取摘要
        stored = _discussion_memory.load(trace_id)
        summary = stored.summary if stored else None

        chain.insert(
            0,
            DiscussionChainItem(
                id=disc.id,
                topic=disc.topic,
                summary=summary,
                status=disc.status,
                created_at=disc.created_at,
                is_origin=disc.continued_from is None,
            ),
        )
        trace_id = disc.continued_from

    # 计算当前讨论在链中的位置
    current_index = 0
    for i, item in enumerate(chain):
        if item.id == discussion_id:
            current_index = i
            break

    return DiscussionChainResponse(chain=chain, current_index=current_index)


# ==============================================================================
# Agenda API Models
# ==============================================================================


class AgendaItemResponse(BaseModel):
    """Response model for a single agenda item."""

    id: str
    title: str
    description: str | None
    status: str
    summary: str | None
    summary_details: dict[str, Any] | None = None
    started_at: str | None = None
    completed_at: str | None = None


class AgendaResponse(BaseModel):
    """Response model for the full agenda."""

    items: list[AgendaItemResponse]
    current_index: int


class AddAgendaItemRequest(BaseModel):
    """Request body for adding a new agenda item."""

    title: str = Field(..., min_length=1, max_length=100, description="议题标题")
    description: str | None = Field(default=None, max_length=500, description="议题描述")


class AddAgendaItemResponse(BaseModel):
    """Response for adding a new agenda item."""

    item: AgendaItemResponse
    message: str


class AgendaItemSummaryResponse(BaseModel):
    """Response for getting an agenda item summary."""

    item_id: str
    title: str
    summary: str | None
    summary_details: dict[str, Any] | None = None


# In-memory storage for agendas (keyed by discussion_id)
_discussion_agendas: dict[str, Agenda] = {}
_agenda_lock = threading.Lock()


def get_discussion_agenda(discussion_id: str) -> Agenda | None:
    """Get the agenda for a discussion.

    Args:
        discussion_id: The discussion ID.

    Returns:
        The Agenda or None if not found.
    """
    with _agenda_lock:
        return _discussion_agendas.get(discussion_id)


def set_discussion_agenda(discussion_id: str, agenda: Agenda) -> None:
    """Set the agenda for a discussion.

    Args:
        discussion_id: The discussion ID.
        agenda: The Agenda to store.
    """
    with _agenda_lock:
        _discussion_agendas[discussion_id] = agenda


def _agenda_item_to_response(item: AgendaItem) -> AgendaItemResponse:
    """Convert an AgendaItem to its response model."""
    return AgendaItemResponse(
        id=item.id,
        title=item.title,
        description=item.description,
        status=item.status.value,
        summary=item.summary,
        summary_details=item.summary_details.model_dump() if item.summary_details else None,
        started_at=item.started_at.isoformat() if item.started_at else None,
        completed_at=item.completed_at.isoformat() if item.completed_at else None,
    )


# ==============================================================================
# Agenda API Endpoints
# ==============================================================================


@router.get("/current/agenda", response_model=AgendaResponse | None)
async def get_current_agenda() -> AgendaResponse | None:
    """获取当前讨论的议程。

    Returns:
        当前讨论的议程，如果没有活跃讨论则返回 None。
    """
    discussion = get_current_discussion()
    if discussion is None:
        raise HTTPException(status_code=404, detail="无活跃讨论")

    agenda = get_discussion_agenda(discussion.id)
    if agenda is None:
        # Return empty agenda if not initialized
        return AgendaResponse(items=[], current_index=0)

    return AgendaResponse(
        items=[_agenda_item_to_response(item) for item in agenda.items],
        current_index=agenda.current_index,
    )


@router.post("/current/agenda/items", response_model=AddAgendaItemResponse)
async def add_agenda_item(request: AddAgendaItemRequest) -> AddAgendaItemResponse:
    """添加新议题（主策划动态添加）。

    Args:
        request: 包含议题标题和描述的请求体。

    Returns:
        新添加的议题信息。
    """
    discussion = get_current_discussion()
    if discussion is None:
        raise HTTPException(status_code=404, detail="无活跃讨论")

    agenda = get_discussion_agenda(discussion.id)
    if agenda is None:
        # Initialize agenda if not exists
        agenda = Agenda()
        set_discussion_agenda(discussion.id, agenda)

    item = agenda.add_item(title=request.title, description=request.description)
    set_discussion_agenda(discussion.id, agenda)

    return AddAgendaItemResponse(
        item=_agenda_item_to_response(item),
        message=f"已添加议题: {item.title}",
    )


@router.post("/current/agenda/items/{item_id}/skip", response_model=AgendaItemResponse)
async def skip_agenda_item(item_id: str) -> AgendaItemResponse:
    """跳过某个议题。

    Args:
        item_id: 要跳过的议题 ID。

    Returns:
        被跳过的议题信息。
    """
    discussion = get_current_discussion()
    if discussion is None:
        raise HTTPException(status_code=404, detail="无活跃讨论")

    agenda = get_discussion_agenda(discussion.id)
    if agenda is None:
        raise HTTPException(status_code=404, detail="议程未初始化")

    item = agenda.skip_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="议题未找到或无法跳过")

    set_discussion_agenda(discussion.id, agenda)
    return _agenda_item_to_response(item)


@router.get("/current/agenda/items/{item_id}/summary", response_model=AgendaItemSummaryResponse)
async def get_agenda_item_summary(item_id: str) -> AgendaItemSummaryResponse:
    """获取议题小结。

    Args:
        item_id: 议题 ID。

    Returns:
        议题的小结内容。
    """
    discussion = get_current_discussion()
    if discussion is None:
        raise HTTPException(status_code=404, detail="无活跃讨论")

    agenda = get_discussion_agenda(discussion.id)
    if agenda is None:
        raise HTTPException(status_code=404, detail="议程未初始化")

    item = agenda.get_item_by_id(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="议题未找到")

    if item.status != AgendaItemStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="议题尚未完成，无法获取小结")

    return AgendaItemSummaryResponse(
        item_id=item.id,
        title=item.title,
        summary=item.summary,
        summary_details=item.summary_details.model_dump() if item.summary_details else None,
    )


# ==============================================================================
# Per-discussion Agenda API Endpoints
# ==============================================================================


@router.get("/{discussion_id}/agenda", response_model=AgendaResponse | None)
async def get_discussion_agenda_api(discussion_id: str) -> AgendaResponse | None:
    """获取指定讨论的议程。"""
    discussion = get_discussion_state(discussion_id)
    if discussion is None:
        raise HTTPException(status_code=404, detail="讨论未找到")

    agenda = get_discussion_agenda(discussion_id)
    if agenda is None:
        return AgendaResponse(items=[], current_index=0)

    return AgendaResponse(
        items=[_agenda_item_to_response(item) for item in agenda.items],
        current_index=agenda.current_index,
    )


@router.post("/{discussion_id}/agenda/items", response_model=AddAgendaItemResponse)
async def add_discussion_agenda_item(
    discussion_id: str, request: AddAgendaItemRequest
) -> AddAgendaItemResponse:
    """为指定讨论添加新议题。"""
    discussion = get_discussion_state(discussion_id)
    if discussion is None:
        raise HTTPException(status_code=404, detail="讨论未找到")

    agenda = get_discussion_agenda(discussion_id)
    if agenda is None:
        agenda = Agenda()
        set_discussion_agenda(discussion_id, agenda)

    item = agenda.add_item(title=request.title, description=request.description)
    set_discussion_agenda(discussion_id, agenda)

    return AddAgendaItemResponse(
        item=_agenda_item_to_response(item),
        message=f"已添加议题: {item.title}",
    )

# =============================================================================
# Discussion Management (delete / stop)
# =============================================================================

@router.delete("/{discussion_id}")
async def delete_discussion(
    discussion_id: str,
    user: dict = Depends(get_optional_user),
):
    """Delete a discussion. Requires owner or superadmin."""
    owner_id = _discussion_memory.get_owner_id(discussion_id)
    if user:
        if owner_id != user["id"] and user.get("role") != "superadmin":
            raise HTTPException(403, "Not authorized to delete this discussion")
    elif owner_id is not None:
        # Discussion has an owner but no auth provided
        raise HTTPException(401, "Authentication required")

    # Stop if running
    state = get_discussion_state(discussion_id)
    if state and state.status in (DiscussionStatus.RUNNING, DiscussionStatus.PAUSED):
        state.status = DiscussionStatus.FAILED
        save_discussion_state(state)

    # Delete from memory
    success = _discussion_memory.delete(discussion_id)
    if not success:
        raise HTTPException(404, "Discussion not found")

    return {"ok": True}


@router.post("/{discussion_id}/stop")
async def stop_discussion(
    discussion_id: str,
    user: dict = Depends(get_optional_user),
):
    """Stop/interrupt a running discussion. Requires owner or superadmin."""
    owner_id = _discussion_memory.get_owner_id(discussion_id)
    if user:
        if owner_id != user["id"] and user.get("role") != "superadmin":
            raise HTTPException(403, "Not authorized to stop this discussion")
    elif owner_id is not None:
        raise HTTPException(401, "Authentication required")

    state = get_discussion_state(discussion_id)
    if not state:
        raise HTTPException(404, "Discussion not found")

    if state.status not in (DiscussionStatus.RUNNING, DiscussionStatus.PAUSED, DiscussionStatus.PENDING):
        raise HTTPException(400, f"Discussion is already {state.status.value}")

    state.status = DiscussionStatus.FAILED
    save_discussion_state(state)

    return {"ok": True, "status": "failed"}



# ---------------------------------------------------------------------------
# Public: stage moderator config (read-only, no admin auth needed)
# ---------------------------------------------------------------------------

@router.get("/stage-moderators")
async def get_stage_moderators_public(user=Depends(get_optional_user)):
    """Return stage template → moderator role mapping (public read-only)."""
    from src.admin.config_store import ConfigStore
    store = ConfigStore()
    return {"moderators": store.get_stage_moderators()}


# =============================================================================
# 功能 4：GDD 自动导出
# =============================================================================

@router.get("/export-gdd/{project_id}")
async def export_project_gdd(
    project_id: str,
    user=Depends(get_optional_user),
):
    """将项目所有阶段讨论结果合并为一份完整的 GDD（Markdown 格式）。

    遍历该项目所有已完成的讨论，按阶段顺序排列，输出结构化 Markdown。
    """
    from fastapi.responses import Response

    completed = []
    # 优先从内存字典取，再从文件取
    seen_ids = set()
    for disc in list(_discussions.values()):
        if disc.project_id == project_id and disc.status in (
            DiscussionStatus.COMPLETED, DiscussionStatus.STOPPED
        ):
            completed.append(disc)
            seen_ids.add(disc.id)

    if _STATE_DIR.exists():
        for state_file in sorted(_STATE_DIR.glob("*.json")):
            if state_file.stem in seen_ids:
                continue
            try:
                disc = _load_discussion_state(state_file.stem)
                if disc and disc.project_id == project_id and disc.status in (
                    DiscussionStatus.COMPLETED, DiscussionStatus.STOPPED
                ):
                    completed.append(disc)
            except Exception:
                continue

    if not completed:
        return {"error": "该项目暂无已完成的讨论", "gdd": ""}

    # 按创建时间排序
    completed.sort(key=lambda d: d.created_at)

    lines = [f"# 游戏设计文档 (GDD)\n\n> 项目：{project_id}  \n> 生成时间：{datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC\n\n---\n"]

    for i, disc in enumerate(completed, 1):
        stage_label = disc.target_id or f"讨论 {i}"
        lines.append(f"## {i}. {disc.topic}")
        lines.append(f"\n> 阶段：{stage_label} | 状态：{disc.status.value} | 时间：{disc.created_at[:10]}\n")
        if disc.producer_stance:
            lines.append(f"> **制作人立场**：{disc.producer_stance}\n")
        if disc.result:
            lines.append(disc.result)
        else:
            lines.append("_（本阶段无最终结论文本）_")
        if disc.quality_score:
            qs = disc.quality_score
            lines.append(
                f"\n> **讨论质量**：完整性 {qs.get('completeness', '-')}/10 | "
                f"可执行性 {qs.get('executability', '-')}/10 | "
                f"共识度 {qs.get('consensus', '-')}/10 | "
                f"综合 **{qs.get('overall', '-')}**/10"
            )
        lines.append("\n---\n")

    gdd_content = "\n".join(lines)
    return Response(
        content=gdd_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="gdd-{project_id}.md"'},
    )


# =============================================================================
# 功能 5：讨论模板库
# =============================================================================

_DISCUSSION_TEMPLATES: list[dict] = [
    {
        "id": "card-game-concept",
        "name": "卡牌游戏概念孵化",
        "stage": "concept",
        "topic_template": "{game_name} — 卡牌游戏概念孵化",
        "briefing": "聚焦卡牌收集、组合玩法、稀有度体系和 PVP/PVE 平衡设计。",
        "producer_stance": "我希望玩法简单易上手、但有足够的策略深度让硬核玩家长期留存。",
        "description": "适用于 TCG / CCG 类卡牌游戏的早期概念阶段讨论",
    },
    {
        "id": "mmo-numbers",
        "name": "MMO 数值框架",
        "stage": "numbers",
        "topic_template": "{game_name} — MMO 核心数值框架",
        "briefing": "讨论属性体系、成长曲线、战斗数值公式和经济循环。",
        "producer_stance": "严格控制付费加速幅度，确保免费玩家在 PVE 中不受歧视。",
        "description": "适用于 MMORPG 类游戏的数值设计阶段",
    },
    {
        "id": "casual-mobile",
        "name": "休闲手游概念",
        "stage": "concept",
        "topic_template": "{game_name} — 休闲手游概念设计",
        "briefing": "轻度、高频次、低门槛。强调社交分享和短时间内的完整体验。",
        "producer_stance": "5 分钟内必须让玩家感受到核心乐趣，第一周留存目标 40%+。",
        "description": "适用于超休闲或休闲类手机游戏",
    },
    {
        "id": "art-style-2d",
        "name": "2D 美术风格定义",
        "stage": "art-style",
        "topic_template": "{game_name} — 2D 美术风格方向",
        "briefing": "确定整体视觉调性、色彩方案、角色风格和 UI 语言。",
        "producer_stance": "风格需要有辨识度，在 App Store 截图中能瞬间抓住眼球。",
        "description": "适用于 2D 手游或端游的美术风格讨论",
    },
    {
        "id": "core-gameplay-loop",
        "name": "核心玩法循环设计",
        "stage": "core-gameplay",
        "topic_template": "{game_name} — 核心玩法循环",
        "briefing": "定义核心行动、即时反馈、短中长期目标的设计逻辑。",
        "producer_stance": "核心循环必须在没有任何付费的情况下完整且有趣。",
        "description": "通用核心玩法设计讨论",
    },
    {
        "id": "tech-prototype-scope",
        "name": "技术原型范围规划",
        "stage": "tech-prototype",
        "topic_template": "{game_name} — 技术原型目标与范围",
        "briefing": "明确原型需要验证的核心技术风险、选型和可交付物。",
        "producer_stance": "原型预算 4 周，只验证最高风险的 1-2 个技术点，不追求完整性。",
        "description": "技术原型阶段规划讨论",
    },
]


@router.get("/templates")
async def get_discussion_templates(
    stage: str | None = None,
    user=Depends(get_optional_user),
):
    """获取讨论模板列表。可按 stage 过滤。"""
    templates = _DISCUSSION_TEMPLATES
    if stage:
        templates = [t for t in templates if t.get("stage") == stage]
    return {"templates": templates}


@router.get("/templates/{template_id}")
async def get_discussion_template(
    template_id: str,
    user=Depends(get_optional_user),
):
    """获取单个讨论模板详情。"""
    for t in _DISCUSSION_TEMPLATES:
        if t["id"] == template_id:
            return t
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="模板不存在")


# =============================================================================
# 功能 6：Agent 专业意见归档
# =============================================================================

def _extract_agent_opinions(discussion_id: str, disc_state: DiscussionState) -> dict[str, list[str]]:
    """从讨论消息中提取各 agent 的关键观点。

    Returns:
        {role_name: [opinion1, opinion2, ...]}
    """
    stored = _discussion_memory.load(discussion_id)
    if stored is None or not stored.messages:
        return {}

    opinions: dict[str, list[str]] = {}
    # 对每条非 lead_planner 消息，若包含具体建议/立场，则记录
    opinion_markers = ["建议", "认为", "应该", "必须", "风险", "问题", "方案", "设计", "优先", "核心"]
    for msg in stored.messages:
        role = msg.agent_role or ""
        if not role or role in ("主策划", "lead_planner", disc_state.moderator_role):
            continue
        content = msg.content or ""
        if len(content) < 20:
            continue
        # 判断是否包含有效观点
        if any(marker in content for marker in opinion_markers):
            # 取前 150 字作为观点摘要
            snippet = content[:150].replace("\n", " ").strip()
            opinions.setdefault(role, []).append(snippet)

    # 每个角色最多取 3 条观点
    return {role: ops[:3] for role, ops in opinions.items()}


def _save_agent_opinions(project_id: str, discussion_id: str, disc_state: DiscussionState) -> None:
    """将讨论中提取的 agent 观点追加保存到项目级 JSON 文件。"""
    opinions = _extract_agent_opinions(discussion_id, disc_state)
    if not opinions:
        return

    opinions_dir = Path(_STATE_DIR).parent / "agent_opinions"
    opinions_dir.mkdir(parents=True, exist_ok=True)
    opinions_file = opinions_dir / f"{project_id}.json"

    existing: dict = {}
    if opinions_file.exists():
        try:
            existing = json.loads(opinions_file.read_text(encoding="utf-8"))
        except Exception:
            existing = {}

    now = datetime.utcnow().isoformat()
    for role, ops in opinions.items():
        if role not in existing:
            existing[role] = []
        for op in ops:
            existing[role].append({
                "opinion": op,
                "discussion_id": discussion_id,
                "topic": disc_state.topic,
                "stage": disc_state.target_id or "",
                "recorded_at": now,
            })
        # 最多保留每个角色最近 20 条
        existing[role] = existing[role][-20:]

    opinions_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


@router.get("/{discussion_id}/agent-opinions")
async def get_discussion_agent_opinions(
    discussion_id: str,
    user=Depends(get_optional_user),
):
    """获取某次讨论中各 agent 的关键观点摘要。"""
    disc = _discussions.get(discussion_id) or _load_discussion_state(discussion_id)
    if disc is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="讨论不存在")
    opinions = _extract_agent_opinions(discussion_id, disc)
    return {"discussion_id": discussion_id, "opinions": opinions}


@router.get("/project-opinions/{project_id}")
async def get_project_agent_opinions(
    project_id: str,
    role: str | None = None,
    user=Depends(get_optional_user),
):
    """获取项目中某个或所有 agent 的历史观点归档。"""
    opinions_dir = Path(_STATE_DIR).parent / "agent_opinions"
    opinions_file = opinions_dir / f"{project_id}.json"
    if not opinions_file.exists():
        return {"project_id": project_id, "opinions": {}}
    try:
        data = json.loads(opinions_file.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    if role:
        data = {role: data.get(role, [])}
    return {"project_id": project_id, "opinions": data}


# =============================================================================
# 功能 7：观战模式增强（观众提问队列）
# =============================================================================

class ViewerQuestionRequest(BaseModel):
    """观众提问请求。"""
    question: str = Field(..., min_length=1, max_length=500, description="问题内容")
    viewer_name: str = Field(default="匿名观众", max_length=50, description="提问者昵称")


@router.post("/{discussion_id}/viewer-question")
async def submit_viewer_question(
    discussion_id: str,
    request: ViewerQuestionRequest,
    user=Depends(get_optional_user),
):
    """观众提交问题到讨论观察队列。"""
    disc = _discussions.get(discussion_id) or _load_discussion_state(discussion_id)
    if disc is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="讨论不存在")

    question_entry = {
        "id": str(uuid.uuid4())[:8],
        "question": request.question,
        "viewer_name": request.viewer_name,
        "likes": 0,
        "adopted": False,
        "submitted_at": datetime.utcnow().isoformat(),
    }
    disc.viewer_questions.append(question_entry)
    save_discussion_state(disc)

    # 广播新问题事件给制作人
    try:
        broadcast_sync(
            {
                "type": "viewer_question",
                "data": {
                    "discussion_id": discussion_id,
                    "question": question_entry,
                },
            },
            discussion_id=discussion_id,
        )
    except Exception:
        pass

    return {"ok": True, "question": question_entry}


@router.post("/{discussion_id}/viewer-question/{question_id}/like")
async def like_viewer_question(
    discussion_id: str,
    question_id: str,
    user=Depends(get_optional_user),
):
    """给某个观众问题点赞。"""
    disc = _discussions.get(discussion_id) or _load_discussion_state(discussion_id)
    if disc is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="讨论不存在")

    for q in disc.viewer_questions:
        if q.get("id") == question_id:
            q["likes"] = q.get("likes", 0) + 1
            save_discussion_state(disc)
            return {"ok": True, "likes": q["likes"]}

    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="问题不存在")


@router.post("/{discussion_id}/viewer-question/{question_id}/adopt")
async def adopt_viewer_question(
    discussion_id: str,
    question_id: str,
    user=Depends(get_optional_user),
):
    """制作人采纳观众问题，将其作为 producer message 注入讨论。"""
    disc = _discussions.get(discussion_id) or _load_discussion_state(discussion_id)
    if disc is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="讨论不存在")

    question_text = None
    for q in disc.viewer_questions:
        if q.get("id") == question_id:
            q["adopted"] = True
            question_text = q["question"]
            break

    if question_text is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="问题不存在")

    save_discussion_state(disc)

    # 注入为制作人消息（若讨论仍在运行）
    crew = _running_crews.get(discussion_id)
    if crew:
        crew.add_producer_message(f"[观众问题] {question_text}")

    return {"ok": True, "injected": crew is not None}


# =============================================================================
# 功能 2：Agent 投票量化共识
# =============================================================================

def _compute_agent_votes(discussion_id: str) -> dict:
    """从讨论消息中解析各 Agent 的立场投票。

    扫描消息文本，检测支持/反对/保留意见的关键词，
    返回 {role: {support: n, oppose: n, neutral: n}} 结构。
    """
    stored = _discussion_memory.load(discussion_id)
    if stored is None or not stored.messages:
        return {}

    support_kw = ["支持", "同意", "赞同", "认可", "没问题", "好的", "可以", "确实", "对的", "这个方向"]
    oppose_kw = ["反对", "不同意", "不赞同", "有问题", "风险很高", "不可行", "难以接受", "存疑"]
    neutral_kw = ["保留意见", "待定", "需要更多信息", "暂时中立", "两方面都有", "可以讨论"]

    votes: dict[str, dict[str, int]] = {}
    for msg in stored.messages:
        role = msg.agent_role or ""
        if not role:
            continue
        content = msg.content or ""
        support = sum(1 for kw in support_kw if kw in content)
        oppose = sum(1 for kw in oppose_kw if kw in content)
        neutral = sum(1 for kw in neutral_kw if kw in content)
        if support + oppose + neutral == 0:
            continue
        if role not in votes:
            votes[role] = {"support": 0, "oppose": 0, "neutral": 0}
        votes[role]["support"] += support
        votes[role]["oppose"] += oppose
        votes[role]["neutral"] += neutral

    # 归一化：每个 role 取主立场
    result = {}
    for role, counts in votes.items():
        total = counts["support"] + counts["oppose"] + counts["neutral"] or 1
        result[role] = {
            "support": round(counts["support"] / total * 100),
            "oppose": round(counts["oppose"] / total * 100),
            "neutral": round(counts["neutral"] / total * 100),
            "raw": counts,
        }
    return result


@router.get("/{discussion_id}/votes")
async def get_discussion_votes(
    discussion_id: str,
    user=Depends(get_optional_user),
):
    """获取讨论中各 Agent 的投票/立场统计。"""
    disc = _discussions.get(discussion_id) or _load_discussion_state(discussion_id)
    if disc is None:
        raise HTTPException(status_code=404, detail="讨论不存在")

    votes = disc.votes
    if not votes:
        # 实时计算
        try:
            votes = _compute_agent_votes(discussion_id)
        except Exception:
            votes = {}

    return {"discussion_id": discussion_id, "votes": votes}


# =============================================================================
# 功能 5：数值自动校验
# =============================================================================

_GAME_INDUSTRY_BENCHMARKS: list[dict] = [
    {"category": "付费率", "keywords": ["付费率"], "warn_below": 1, "warn_above": 25, "unit": "%",
     "reference": "休闲 1-3% | 中核 3-8% | 重度 5-15%"},
    {"category": "次留存", "keywords": ["D1", "次留", "次日留存"], "warn_below": 20, "warn_above": 60, "unit": "%",
     "reference": "休闲 40-50% | 中核 30-40% | 重度 25-35%"},
    {"category": "七日留存", "keywords": ["D7", "七留", "七日留存"], "warn_below": 8, "warn_above": 35, "unit": "%",
     "reference": "休闲 15-25% | 中核 12-20% | 重度 10-18%"},
    {"category": "月留存", "keywords": ["D30", "月留", "月留存"], "warn_below": 3, "warn_above": 20, "unit": "%",
     "reference": "休闲 5-10% | 中核 5-8% | 重度 4-7%"},
    {"category": "保底次数", "keywords": ["保底", "天井"], "warn_below": 30, "warn_above": 300, "unit": "抽",
     "reference": "行业主流 50-200 抽"},
    {"category": "暴击倍率", "keywords": ["暴击倍率", "暴击伤害"], "warn_below": 130, "warn_above": 400, "unit": "%",
     "reference": "行业基准 150-200%"},
    {"category": "暴击率", "keywords": ["暴击率", "暴击概率"], "warn_below": 3, "warn_above": 100, "unit": "%",
     "reference": "基础 5-10% 上限 80-100%"},
    {"category": "版本周期", "keywords": ["版本周期", "更新周期", "大版本"], "warn_below": 14, "warn_above": 120, "unit": "天",
     "reference": "大版本 6-8 周 | 赛季 6-12 周"},
    {"category": "ARPU", "keywords": ["ARPU", "月均收入"], "warn_below": 1, "warn_above": 200, "unit": "元",
     "reference": "休闲 1-5元 | 中核 10-30元 | 重度 30-80元"},
]


def _validate_numbers(discussion_id: str) -> list[dict]:
    """从讨论消息中提取数值，与行业基准对比，返回校验结果。"""
    import re
    stored = _discussion_memory.load(discussion_id)
    if stored is None or not stored.messages:
        return []

    full_text = "\n".join(m.content or "" for m in stored.messages)
    results = []

    for bench in _GAME_INDUSTRY_BENCHMARKS:
        for kw in bench["keywords"]:
            # 匹配数字（带 % 或不带）
            pattern = rf"{re.escape(kw)}\s*[：:为是约]?\s*(\d+(?:\.\d+)?)\s*(%|抽|次|元|天|倍)?"
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            for match in matches:
                try:
                    value = float(match[0])
                except (ValueError, IndexError):
                    continue
                status = "normal"
                message = f"符合行业基准（{bench['reference']}）"
                if value < bench["warn_below"]:
                    status = "low"
                    message = f"低于行业基准下限 {bench['warn_below']}{bench['unit']}（{bench['reference']}）"
                elif value > bench["warn_above"]:
                    status = "high"
                    message = f"高于行业基准上限 {bench['warn_above']}{bench['unit']}（{bench['reference']}）"

                results.append({
                    "category": bench["category"],
                    "keyword": kw,
                    "value": value,
                    "unit": bench["unit"],
                    "status": status,
                    "message": message,
                    "reference": bench["reference"],
                })

    # 去重（同 category 只保留第一个）
    seen = set()
    deduped = []
    for r in results:
        key = (r["category"], r["value"])
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    return deduped


@router.get("/{discussion_id}/number-validation")
async def get_number_validation(
    discussion_id: str,
    user=Depends(get_optional_user),
):
    """获取讨论中数值与行业基准的校验报告。"""
    disc = _discussions.get(discussion_id) or _load_discussion_state(discussion_id)
    if disc is None:
        raise HTTPException(status_code=404, detail="讨论不存在")

    validation = disc.number_validation
    if validation is None:
        try:
            validation = _validate_numbers(discussion_id)
        except Exception:
            validation = []

    warnings = [v for v in validation if v["status"] != "normal"]
    return {
        "discussion_id": discussion_id,
        "validation": validation,
        "warnings_count": len(warnings),
        "has_issues": len(warnings) > 0,
    }


# =============================================================================
# 功能 8：跨项目 Agent 记忆
# =============================================================================

_AGENT_MEMORY_DIR = Path("data/agent_memory")


def _load_agent_cross_memory(role: str, limit: int = 5) -> list[dict]:
    """加载某 Agent 的跨项目记忆（最近 N 条）。"""
    _AGENT_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    mem_file = _AGENT_MEMORY_DIR / f"{role}.json"
    if not mem_file.exists():
        return []
    try:
        data = json.loads(mem_file.read_text(encoding="utf-8"))
        memories = data.get("memories", [])
        return memories[-limit:]
    except Exception:
        return []


def _update_agent_cross_memory(discussion_id: str, disc_state: DiscussionState) -> None:
    """讨论完成后，将各 Agent 的关键观点写入跨项目记忆。"""
    opinions = _extract_agent_opinions(discussion_id, disc_state)
    if not opinions:
        return

    _AGENT_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.utcnow().isoformat()

    for role, snippets in opinions.items():
        mem_file = _AGENT_MEMORY_DIR / f"{role}.json"
        existing: dict = {"memories": []}
        if mem_file.exists():
            try:
                existing = json.loads(mem_file.read_text(encoding="utf-8"))
            except Exception:
                existing = {"memories": []}

        for snippet in snippets:
            existing["memories"].append({
                "insight": snippet,
                "project_id": disc_state.project_id,
                "topic": disc_state.topic,
                "discussion_id": discussion_id,
                "recorded_at": now,
            })

        # 最多保留 50 条
        existing["memories"] = existing["memories"][-50:]
        mem_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


@router.get("/agent-memory/{role}")
async def get_agent_memory(
    role: str,
    limit: int = 10,
    user=Depends(get_optional_user),
):
    """获取某 Agent 的跨项目记忆。"""
    memories = _load_agent_cross_memory(role, limit=limit)
    return {"role": role, "memories": memories, "count": len(memories)}


# =============================================================================
# 功能 9：讨论摘要自动同步文档
# =============================================================================

@router.post("/{discussion_id}/sync-to-document")
async def sync_discussion_to_document(
    discussion_id: str,
    user=Depends(get_optional_user),
):
    """将讨论摘要/决策自动同步到阶段文档。

    - 若该阶段已有对应文档，追加本次讨论摘要
    - 若无，则创建新文档
    返回同步结果。
    """
    disc = _discussions.get(discussion_id) or _load_discussion_state(discussion_id)
    if disc is None:
        raise HTTPException(status_code=404, detail="讨论不存在")

    if disc.status not in (DiscussionStatus.COMPLETED, DiscussionStatus.STOPPED):
        raise HTTPException(status_code=400, detail="讨论尚未完成，无法同步")

    # 构建同步内容
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"## 📋 讨论摘要：{disc.topic}",
        f"\n> 时间：{now_str} | 状态：{disc.status.value}",
    ]
    if disc.producer_stance:
        lines.append(f"> **制作人立场**：{disc.producer_stance}")
    if disc.agenda_items:
        lines.append("\n**讨论议程：**")
        for i, item in enumerate(disc.agenda_items, 1):
            lines.append(f"{i}. {item}")
    if disc.result:
        lines.append(f"\n### 讨论结论\n{disc.result[:2000]}")
    if disc.quality_score:
        qs = disc.quality_score
        lines.append(
            f"\n> 质量评分：完整性 {qs.get('completeness')}/10 | "
            f"可执行性 {qs.get('executability')}/10 | "
            f"共识度 {qs.get('consensus')}/10"
        )

    content = "\n".join(lines)

    # 尝试查找项目文档系统（通过 project routes）
    try:
        from src.project.storage import ProjectStorage
        storage = ProjectStorage()
        project_id = disc.project_id
        stage_id = disc.target_id

        doc_id = None
        # 若已有同步记录，追加到原文档
        if disc.synced_document_id:
            existing = storage.get_document(project_id, disc.synced_document_id)
            if existing:
                new_content = (existing.get("content") or "") + f"\n\n---\n\n{content}"
                storage.update_document(project_id, disc.synced_document_id, {"content": new_content})
                doc_id = disc.synced_document_id
            else:
                disc.synced_document_id = None

        if not doc_id:
            # 创建新文档
            doc = storage.create_document(
                project_id=project_id,
                stage_id=stage_id,
                title=f"讨论记录：{disc.topic[:40]}",
                content=content,
            )
            doc_id = doc.get("id") if isinstance(doc, dict) else getattr(doc, "id", None)

        disc.synced_document_id = doc_id
        save_discussion_state(disc)

        return {"ok": True, "document_id": doc_id, "synced_at": now_str}

    except ImportError:
        # ProjectStorage 不可用时，返回内容供前端处理
        return {
            "ok": True,
            "document_id": None,
            "content": content,
            "synced_at": now_str,
            "note": "文档系统不可用，请手动复制内容",
        }
    except Exception as e:
        logger.warning("Sync to document failed: %s", e)
        return {
            "ok": False,
            "error": str(e),
            "content": content,
            "synced_at": now_str,
        }


# =============================================================================
# 功能 1：讨论分支探索
# =============================================================================

@router.post("/{discussion_id}/branch")
async def create_discussion_branch(
    discussion_id: str,
    branch_direction: str = "",
    rounds: int = 10,
    producer_stance: str = "",
    user=Depends(get_optional_user),
):
    """从某个讨论创建分支，探索不同设计方向。

    分支继承父讨论的 topic、agents、project_id 和 briefing，
    但使用不同的 producer_stance / branch_direction 引导讨论走向不同路径。
    """
    parent = _discussions.get(discussion_id) or _load_discussion_state(discussion_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="父讨论不存在")

    branch_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    direction_label = branch_direction or f"分支方向 {branch_id[:6]}"

    branch = DiscussionState(
        id=branch_id,
        topic=f"[分支] {parent.topic} — {direction_label}",
        rounds=rounds,
        auto_pause_interval=parent.auto_pause_interval,
        status=DiscussionStatus.PENDING,
        created_at=now,
        project_id=parent.project_id,
        target_type=parent.target_type,
        target_id=parent.target_id,
        agents=parent.agents or [],
        briefing=parent.briefing or "",
        moderator_role=parent.moderator_role or "",
        producer_stance=producer_stance or parent.producer_stance,
        agenda_items=parent.agenda_items or [],
        parent_discussion_id=discussion_id,
        branch_direction=direction_label,
        dependency_hints=parent.dependency_hints or [],
    )
    _discussions[branch_id] = branch
    save_discussion_state(branch)

    if user:
        _discussion_memory.set_owner_id(branch_id, user["id"])

    return {
        "branch_id": branch_id,
        "parent_id": discussion_id,
        "topic": branch.topic,
        "status": branch.status,
        "direction": direction_label,
    }


@router.get("/{discussion_id}/branches")
async def list_discussion_branches(
    discussion_id: str,
    user=Depends(get_optional_user),
):
    """列出某讨论的所有分支。"""
    branches = []
    for disc in list(_discussions.values()):
        if disc.parent_discussion_id == discussion_id:
            branches.append({
                "id": disc.id,
                "topic": disc.topic,
                "direction": disc.branch_direction,
                "status": disc.status,
                "created_at": disc.created_at,
                "quality_score": disc.quality_score,
            })

    # 也从磁盘扫描
    if _STATE_DIR.exists():
        seen = {b["id"] for b in branches}
        for state_file in _STATE_DIR.glob("*.json"):
            if state_file.stem in seen:
                continue
            try:
                data = json.loads(state_file.read_text(encoding="utf-8"))
                if data.get("parent_discussion_id") == discussion_id:
                    branches.append({
                        "id": data["id"],
                        "topic": data.get("topic", ""),
                        "direction": data.get("branch_direction", ""),
                        "status": data.get("status", ""),
                        "created_at": data.get("created_at", ""),
                        "quality_score": data.get("quality_score"),
                    })
            except Exception:
                continue

    return {"discussion_id": discussion_id, "branches": branches}


# =============================================================================
# 功能 10：制作人 AI 助理
# =============================================================================

_GAME_TYPE_STAGE_MAP: dict[str, list[dict]] = {
    "卡牌": [
        {"stage": "concept", "name": "概念阶段", "agenda": ["核心收集与组合玩法", "稀有度与抽卡体系", "PVP/PVE 平衡策略"]},
        {"stage": "core-gameplay", "name": "核心玩法", "agenda": ["卡牌机制设计", "战斗系统", "手牌上限与费用"]},
        {"stage": "numbers", "name": "数值设计", "agenda": ["抽卡概率与保底", "卡牌属性平衡", "赛季经济节奏"]},
        {"stage": "system-design", "name": "系统设计", "agenda": ["组牌系统", "天梯赛季", "公会/好友功能"]},
    ],
    "MMO": [
        {"stage": "concept", "name": "概念阶段", "agenda": ["世界观与背景故事", "核心差异化卖点", "目标玩家群体"]},
        {"stage": "core-gameplay", "name": "核心玩法", "agenda": ["职业与技能体系", "战斗机制", "社交互动设计"]},
        {"stage": "numbers", "name": "数值设计", "agenda": ["等级成长曲线", "装备属性体系", "经济系统设计"]},
        {"stage": "system-design", "name": "系统设计", "agenda": ["副本与世界Boss", "PVP系统", "工会系统"]},
    ],
    "休闲": [
        {"stage": "concept", "name": "概念阶段", "agenda": ["核心操作与爽感", "关卡结构", "社交传播点"]},
        {"stage": "core-gameplay", "name": "核心玩法", "agenda": ["核心循环设计", "难度曲线", "进度感与成就感"]},
        {"stage": "numbers", "name": "数值设计", "agenda": ["关卡难度参数", "道具价值", "付费门槛"]},
        {"stage": "art-style", "name": "美术风格", "agenda": ["视觉风格定义", "UI/UX 原则", "角色设计方向"]},
    ],
    "SLG": [
        {"stage": "concept", "name": "概念阶段", "agenda": ["战略深度与受众定位", "世界地图设计", "联盟与外交"]},
        {"stage": "core-gameplay", "name": "核心玩法", "agenda": ["城池建设与科技树", "战争机制", "资源争夺"]},
        {"stage": "numbers", "name": "数值设计", "agenda": ["战力成长速度", "付费加速平衡", "服务器生命周期"]},
        {"stage": "system-design", "name": "系统设计", "agenda": ["联盟系统", "赛季合服机制", "活动频率"]},
    ],
}

_AUDIENCE_STANCE_MAP: dict[str, str] = {
    "硬核": "核心深度优先，允许较高学习曲线，PVP 竞技性强，付费主要解锁内容深度而非战力差距。",
    "中核": "玩法深度与休闲兼顾，日活时间 30-60 分钟，活动节奏规律，付费体验公平。",
    "休闲": "5 分钟内必须感受到核心乐趣，操作简单，社交传播性强，低付费门槛（首充 6 元体验）。",
    "女性": "美术品质优先，情感连接与故事性，收集养成为主，避免强 PVP 压迫感。",
    "海外": "本地化文化适配，合规（部分地区抽卡规范），多语言，付费习惯差异需针对性设计。",
}


@router.post("/ai-assistant/project-kickstart")
async def project_kickstart_assistant(
    game_concept: str = "",
    game_type: str = "",
    target_audience: str = "",
    game_name: str = "未命名游戏",
    user=Depends(get_optional_user),
):
    """制作人 AI 助理：根据游戏概念快速生成项目讨论框架。

    输入简单描述，返回：
    - 推荐讨论阶段顺序
    - 每阶段预设议程
    - 制作人立场建议
    - 初步 GDD 框架大纲
    """
    # 识别游戏类型关键词
    detected_type = game_type
    if not detected_type:
        concept_lower = game_concept.lower()
        if any(kw in concept_lower for kw in ["卡牌", "tcg", "ccg", "deck"]):
            detected_type = "卡牌"
        elif any(kw in concept_lower for kw in ["mmo", "mmorpg", "大世界", "开放世界"]):
            detected_type = "MMO"
        elif any(kw in concept_lower for kw in ["slg", "策略", "城池", "战争"]):
            detected_type = "SLG"
        else:
            detected_type = "休闲"

    stages = _GAME_TYPE_STAGE_MAP.get(detected_type, _GAME_TYPE_STAGE_MAP["休闲"])

    # 生成制作人立场
    audience_stance = ""
    for audience_kw, stance in _AUDIENCE_STANCE_MAP.items():
        if audience_kw in target_audience:
            audience_stance = stance
            break

    # 生成 GDD 大纲
    gdd_outline = f"""# {game_name} — 游戏设计文档大纲

## 一、项目概述
- **游戏类型**：{detected_type}
- **目标受众**：{target_audience or '待定'}
- **核心概念**：{game_concept[:200] if game_concept else '待完善'}

## 二、核心体验目标
- [ ] 核心循环设计
- [ ] 差异化卖点
- [ ] 目标数据（留存/付费）

## 三、阶段产出计划
{"".join(f"- **{s['name']}**：{', '.join(s['agenda'][:2])}" + chr(10) for s in stages)}
## 四、风险与挑战（待讨论）
- 数值平衡
- 付费模型
- 上线时机
"""

    return {
        "game_type": detected_type,
        "recommended_stages": stages,
        "producer_stance_suggestion": audience_stance,
        "gdd_outline": gdd_outline,
        "discussion_order": [s["stage"] for s in stages],
        "tips": [
            f"建议先从「{stages[0]['name']}」阶段开始讨论",
            "制作人立场越明确，Agent 讨论方向越聚焦",
            "每个阶段完成后及时导出 GDD，保持文档同步",
        ],
    }


# ============================================================================
# 功能 2：Agent 发言统计
# ============================================================================

_POSITIVE_WORDS = {"同意", "支持", "好的", "赞成", "不错", "可以", "建议采用", "推荐", "认同"}
_NEGATIVE_WORDS = {"反对", "不同意", "不可行", "有问题", "担忧", "风险", "不建议", "质疑"}


@router.get("/{discussion_id}/stats")
async def get_discussion_stats(
    discussion_id: str,
    user=Depends(get_optional_user),
):
    """获取讨论中各 Agent 的发言统计（消息数、字数、情感倾向）。"""
    discussion = _discussions.get(discussion_id)
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")

    messages = _discussion_memory.get_messages(discussion_id)
    stats: dict[str, dict] = {}
    for msg in messages:
        role = getattr(msg, "agent_role", "") or getattr(msg, "agent_id", "unknown")
        content = getattr(msg, "content", "") or ""
        if role not in stats:
            stats[role] = {"messages": 0, "chars": 0, "positive": 0, "negative": 0}
        stats[role]["messages"] += 1
        stats[role]["chars"] += len(content)
        for w in _POSITIVE_WORDS:
            if w in content:
                stats[role]["positive"] += 1
        for w in _NEGATIVE_WORDS:
            if w in content:
                stats[role]["negative"] += 1

    # 计算情感倾向 (1=正向, -1=负向, 0=中立)
    result = []
    for role, s in stats.items():
        total = s["positive"] + s["negative"]
        sentiment = 0.0
        if total > 0:
            sentiment = round((s["positive"] - s["negative"]) / total, 2)
        result.append({
            "role": role,
            "messages": s["messages"],
            "chars": s["chars"],
            "sentiment": sentiment,
            "positive_count": s["positive"],
            "negative_count": s["negative"],
        })
    result.sort(key=lambda x: x["messages"], reverse=True)
    return {"discussion_id": discussion_id, "stats": result, "total_messages": sum(s["messages"] for s in result)}


# ============================================================================
# 功能 6：批量操作
# ============================================================================

class BatchOperationRequest(BaseModel):
    """批量操作请求。"""
    discussion_ids: list[str] = Field(..., description="要操作的讨论 ID 列表")
    action: str = Field(..., description="操作类型: archive | delete | tag")
    tag: str = Field(default="", description="打标签时的标签名")


@router.post("/batch")
async def batch_operations(
    request: BatchOperationRequest,
    user=Depends(get_auth_user),
):
    """批量操作讨论（归档/删除/打标签）。"""
    results = {"success": [], "failed": []}

    for disc_id in request.discussion_ids:
        disc = _discussions.get(disc_id)
        if not disc:
            results["failed"].append({"id": disc_id, "reason": "not found"})
            continue

        try:
            if request.action == "delete":
                _discussions.pop(disc_id, None)
                # 删除持久化状态文件
                state_file = _STATE_DIR / f"{disc_id}.json"
                if state_file.exists():
                    state_file.unlink()
                results["success"].append(disc_id)

            elif request.action == "archive":
                disc.status = DiscussionStatus.STOPPED
                save_discussion_state(disc)
                results["success"].append(disc_id)

            elif request.action == "tag":
                tag = request.tag.strip()
                if tag and tag not in disc.tags:
                    disc.tags.append(tag)
                    save_discussion_state(disc)
                results["success"].append(disc_id)
            else:
                results["failed"].append({"id": disc_id, "reason": f"unknown action: {request.action}"})
        except Exception as e:
            results["failed"].append({"id": disc_id, "reason": str(e)})

    return results


# ============================================================================
# 功能 7：决策日志
# ============================================================================

_DECISION_KEYWORDS = [
    "决定", "确定", "最终", "采用", "方案确定", "结论", "定下", "选择",
    "同意采用", "决议", "拍板", "确认", "方向确定",
]


def _extract_decisions(discussion_id: str, disc_state: DiscussionState) -> None:
    """从讨论消息中提取决策类语句，写入 disc_state.decisions。"""
    if disc_state.decisions:
        return  # 已提取过

    try:
        messages = _discussion_memory.get_messages(discussion_id)
        decisions = []
        for i, msg in enumerate(messages):
            content = getattr(msg, "content", "") or ""
            for kw in _DECISION_KEYWORDS:
                if kw in content:
                    # 找到包含关键词的句子
                    sentences = [s.strip() for s in content.replace("。", "。\n").replace("！", "！\n").split("\n") if s.strip()]
                    for sent in sentences:
                        if kw in sent and len(sent) > 10:
                            decisions.append({
                                "text": sent[:200],
                                "agent_role": getattr(msg, "agent_role", ""),
                                "timestamp": getattr(msg, "timestamp", ""),
                                "message_index": i,
                                "keyword": kw,
                            })
                    break  # 每条消息只取一次
            if len(decisions) >= 20:
                break

        disc_state.decisions = decisions
        save_discussion_state(disc_state)
    except Exception as e:
        logger.warning("Decision extraction failed for %s: %s", discussion_id, e)


@router.get("/{discussion_id}/decisions")
async def get_decisions(
    discussion_id: str,
    user=Depends(get_optional_user),
):
    """获取讨论中自动提取的决策日志。"""
    disc = _discussions.get(discussion_id)
    if not disc:
        raise HTTPException(status_code=404, detail="Discussion not found")

    # 若未提取过，实时提取
    if not disc.decisions and disc.status in (DiscussionStatus.COMPLETED, DiscussionStatus.STOPPED):
        _extract_decisions(discussion_id, disc)

    return {"discussion_id": discussion_id, "decisions": disc.decisions}


# ============================================================================
# 功能 9：自动打标签
# ============================================================================

_TAG_RULES: list[tuple[str, list[str]]] = [
    ("战斗系统", ["战斗", "技能", "战力", "pvp", "boss", "伤害", "属性"]),
    ("经济系统", ["经济", "货币", "付费", "抽卡", "商城", "钻石", "金币"]),
    ("数值设计", ["数值", "成长曲线", "等级", "属性成长", "平衡"]),
    ("核心玩法", ["核心循环", "玩法", "机制", "操作", "关卡"]),
    ("社交系统", ["社交", "公会", "联盟", "好友", "组队"]),
    ("运营策略", ["活动", "运营", "留存", "日活", "召回", "赛季"]),
    ("视觉风格", ["美术", "视觉", "ui", "ue", "风格", "原画"]),
    ("世界观", ["世界观", "背景", "故事", "剧情", "ip"]),
]


def _auto_tag_discussion(discussion_id: str, disc_state: DiscussionState) -> None:
    """基于启发式关键词对讨论自动打标签。"""
    if disc_state.tags:
        return  # 已打过标签

    try:
        messages = _discussion_memory.get_messages(discussion_id)
        all_text = " ".join(
            (getattr(m, "content", "") or "").lower() for m in messages
        ) + " " + disc_state.topic.lower()

        tag_counts: dict[str, int] = {}
        for tag, keywords in _TAG_RULES:
            cnt = sum(all_text.count(kw) for kw in keywords)
            if cnt >= 2:
                tag_counts[tag] = cnt

        # 按出现频率排序，取前 3 个
        sorted_tags = sorted(tag_counts, key=lambda t: tag_counts[t], reverse=True)[:3]
        disc_state.tags = sorted_tags
        save_discussion_state(disc_state)
    except Exception as e:
        logger.warning("Auto-tag failed for %s: %s", discussion_id, e)


@router.get("/{discussion_id}/tags")
async def get_tags(
    discussion_id: str,
    user=Depends(get_optional_user),
):
    """获取讨论的自动标签。"""
    disc = _discussions.get(discussion_id)
    if not disc:
        raise HTTPException(status_code=404, detail="Discussion not found")

    if not disc.tags and disc.status in (DiscussionStatus.COMPLETED, DiscussionStatus.STOPPED):
        _auto_tag_discussion(discussion_id, disc)

    return {"discussion_id": discussion_id, "tags": disc.tags}


@router.patch("/{discussion_id}/tags")
async def update_tags(
    discussion_id: str,
    tags: list[str],
    user=Depends(get_auth_user),
):
    """手动更新讨论标签。"""
    disc = _discussions.get(discussion_id)
    if not disc:
        raise HTTPException(status_code=404, detail="Discussion not found")

    disc.tags = [t.strip() for t in tags if t.strip()][:8]
    save_discussion_state(disc)
    return {"discussion_id": discussion_id, "tags": disc.tags}


# ============================================================================
# 功能 5：讨论进度追踪（议程条目勾选）
# ============================================================================

class AgendaProgressRequest(BaseModel):
    """更新议程进度请求。"""
    item_index: int = Field(..., description="议程条目索引")
    done: bool = Field(..., description="是否已讨论完成")


@router.post("/{discussion_id}/agenda-check")
async def update_agenda_check(
    discussion_id: str,
    request: AgendaProgressRequest,
    user=Depends(get_auth_user),
):
    """勾选/取消议程条目为已讨论。"""
    disc = _discussions.get(discussion_id)
    if not disc:
        raise HTTPException(status_code=404, detail="Discussion not found")

    agenda = disc.agenda_items
    if request.item_index < 0 or request.item_index >= len(agenda):
        raise HTTPException(status_code=400, detail="Invalid item_index")

    # 确保 agenda_progress 与 agenda_items 等长
    if len(disc.agenda_progress) != len(agenda):
        disc.agenda_progress = [{"item": item, "done": False} for item in agenda]

    disc.agenda_progress[request.item_index]["done"] = request.done
    save_discussion_state(disc)
    return {"discussion_id": discussion_id, "agenda_progress": disc.agenda_progress}


# ============================================================================
# 超级制作人 AI 助理：producer-assist
# ============================================================================

_SUPER_PRODUCER_SYSTEM_QUESTIONS = """你是「超级制作人助手」，帮助真实制作人逐一回答 AI 策划团队提出的问题。

你将收到当前讨论主题、AI 向制作人提出的具体问题列表，以及近期讨论内容。

**任务**：针对每个问题，生成 2-3 条不同角度的答案选项，供制作人选择。

输出要求：
- 每条答案选项 25-60 字，口吻像真实制作人说话，直接回答问题
- 每个问题的选项之间必须有明显差异（立场不同、深度不同、或方向不同）
- 不要出现"我建议"、"建议您"等助手用语，像制作人本人在表态
- 输出严格 JSON，无多余内容

输出格式：
{
  "questions": [
    {
      "from_agent": "提问者角色名（从问题来源提取）",
      "question": "完整的原始问题",
      "answers": ["选项A（25-60字）", "选项B（25-60字）", "选项C（可选，25-60字）"]
    }
  ],
  "context_summary": "一句话概括当前讨论焦点"
}"""

_SUPER_PRODUCER_SYSTEM_GENERAL = """你是「超级制作人助手」，专门帮助真实制作人在 AI 策划团队讨论中进行高质量发言。

根据当前讨论背景和最近的对话内容，你需要生成恰好三条发言建议，分别代表：
1. 【果断推进】明确表态，推动决策落地，口吻果断有力
2. 【协商共识】寻求平衡，照顾各方观点，口吻温和建设性
3. 【深度追问】提出关键疑问，挖掘潜在问题，口吻好奇探究

要求：
- 每条建议 30-80 字，像真实制作人说话，不用"我建议"开头
- 贴合当前讨论焦点，有实质内容，不泛泛而谈
- 输出严格 JSON 格式，无多余内容

输出格式：
{
  "suggestions": [
    {"direction": "果断推进", "style": "assertive", "text": "..."},
    {"direction": "协商共识", "style": "collaborative", "text": "..."},
    {"direction": "深度追问", "style": "exploratory", "text": "..."}
  ],
  "context_summary": "一句话概括当前讨论焦点"
}"""


def _call_llm_for_producer_assist(prompt: str, system: str) -> dict | None:
    """调用 LLM 生成制作人发言建议。失败返回 None。

    使用 _get_llm_from_config() 获取 LLM 实例，确保代理 user-agent patch 已应用。
    """
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = _get_llm_from_config()
        if llm is None:
            return None

        # 限制 max_tokens（每题3条答案×100字×3问题≈3500 tokens）
        llm_short = llm.bind(max_tokens=3500)
        resp = llm_short.invoke([
            SystemMessage(content=system),
            HumanMessage(content=prompt),
        ])
        raw = resp.content if hasattr(resp, "content") else str(resp)
        # 提取 JSON
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
    except Exception as e:
        logger.warning("LLM producer-assist failed: %s", e)
    return None


def _heuristic_producer_suggestions(topic: str, recent_context: str, checkpoint_q: str) -> dict:
    """LLM 不可用时的启发式建议（基于讨论主题关键词）。"""
    focus = checkpoint_q or recent_context[:60] or topic

    # 根据讨论主题生成通用但有针对性的建议
    suggestions = [
        {
            "direction": "果断推进",
            "style": "assertive",
            "text": f"这个方向我认为可以定下来，{focus[:30]}这块优先级更高，我们先锁定核心方案，细节后续迭代。",
        },
        {
            "direction": "协商共识",
            "style": "collaborative",
            "text": f"大家对{focus[:20]}的分歧我理解，能不能先对齐一个最小共识，再在此基础上分步推进？",
        },
        {
            "direction": "深度追问",
            "style": "exploratory",
            "text": f"我想更深入了解一下：{focus[:20]}这个方案落地后，对玩家留存和付费的具体影响是什么？",
        },
    ]
    return {
        "suggestions": suggestions,
        "context_summary": f"当前讨论：{topic[:40]}",
        "source": "heuristic",
    }


def _extract_questions_for_producer(msgs: list, recent_limit: int = 8) -> list[str]:
    """从最近消息中提取 AI 角色向制作人提出的问题。

    策略：按行拆分，只收录满足条件的干净问句，过滤 markdown 代码块等噪音。
    """
    questions: list[str] = []
    # 只看最近几条消息（最后一条是制作人发言触发，往前找 AI 消息）
    for m in msgs[-recent_limit:]:
        role = getattr(m, "agent_role", "") or getattr(m, "agent_id", "")
        # 跳过制作人自己的消息
        if role in ("producer", "制作人", "user", ""):
            continue
        content = (getattr(m, "content", "") or "").strip()
        if not content:
            continue

        in_code_block = False
        for line in content.splitlines():
            stripped = line.strip()
            # 跟踪代码块状态，代码块内容一律跳过
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue
            # 必须以 ? 或 ？ 结尾，且不含 ` 反引号（避免代码片段）
            if not (stripped.endswith("?") or stripped.endswith("？")):
                continue
            if "`" in stripped:
                continue
            # 去除 markdown 加粗/编号前缀，只保留问题本体
            clean = stripped.lstrip("*#0123456789.-） ) 、").strip("*").strip()
            # 长度过滤：太短不像完整问句
            if len(clean) < 8:
                continue
            questions.append(f"[{role}] {clean}")
    return questions


@router.post("/{discussion_id}/producer-assist")
async def get_producer_suggestions(
    discussion_id: str,
    user=Depends(get_optional_user),
):
    """获取超级制作人 AI 发言建议。

    有具体问题时返回 {questions: [{from_agent, question, answers: [...]}]}。
    无问题时返回 {suggestions: [{direction, style, text}]}（通用建议）。
    """
    disc = _discussions.get(discussion_id)
    if not disc:
        raise HTTPException(status_code=404, detail="Discussion not found")

    # --- 优先使用 @超级制作人 显式标记的问题（最高优先级）---
    explicit_questions = pop_producer_questions(discussion_id)

    # 获取最近 10 条消息作为上下文
    recent_msgs: list[str] = []
    checkpoint_q = ""
    questions_for_producer: list[str] = []
    all_msgs: list = []
    try:
        loaded = _discussion_memory.load(discussion_id)
        all_msgs = list(loaded.messages) if loaded else []
        for m in all_msgs[-8:]:
            role = getattr(m, "agent_role", "") or getattr(m, "agent_id", "")
            content = (getattr(m, "content", "") or "")[:200]
            recent_msgs.append(f"[{role}] {content}")
        # Note: _extract_questions_for_producer removed — it picked up ordinary
        # discussion sentences as "questions" and showed them as wrong decision
        # cards. Only @超级制作人 explicit questions (explicit_questions queue)
        # or active checkpoint questions drive Mode A.
    except Exception:
        pass

    # 若当前有待决策 checkpoint，从 crew 实例或持久化数据中获取
    checkpoint_options: list[dict] = []
    try:
        crew_inst = _running_crews.get(discussion_id)
        if crew_inst and crew_inst._current_discussion:
            disc_checkpoints = list(crew_inst._current_discussion.checkpoints)
        else:
            stored = _discussion_memory.load(discussion_id)
            disc_checkpoints = list(stored.checkpoints) if stored else []
        for cp in reversed(disc_checkpoints):
            # checkpoint 可能是 dict 或 Pydantic model
            cp_type = cp.get("type", "") if isinstance(cp, dict) else getattr(cp, "type", "")
            cp_responded = cp.get("responded") if isinstance(cp, dict) else getattr(cp, "responded", None)
            cp_question = cp.get("question", "") if isinstance(cp, dict) else getattr(cp, "question", "")
            if cp_type == "decision" and not cp_responded:
                checkpoint_q = cp_question or ""
                # 提取 checkpoint 自带的选项作为答案候选
                raw_opts = cp.get("options", []) if isinstance(cp, dict) else getattr(cp, "options", [])
                if raw_opts:
                    checkpoint_options = [
                        {
                            "label": opt.get("label", "") if isinstance(opt, dict) else getattr(opt, "label", ""),
                            "description": opt.get("description", "") if isinstance(opt, dict) else getattr(opt, "description", ""),
                        }
                        for opt in raw_opts
                    ]
                break
    except Exception:
        pass

    recent_context = "\n".join(recent_msgs)
    logger.info(
        "producer-assist %s: explicit=%d, q4p=%d, checkpoint_q=%r",
        discussion_id[:8], len(explicit_questions), len(questions_for_producer), checkpoint_q[:40] if checkpoint_q else ""
    )

    # --- 模式 A1：有 @超级制作人 显式问题 → 直接生成决策卡答案选项 ---
    if explicit_questions:
        qs_text = "\n".join(
            f"{i+1}. [{q['from_agent']}] {q['question']}"
            for i, q in enumerate(explicit_questions[:3])
        )
        prompt = f"""讨论主题：{disc.topic}
制作人立场：{disc.producer_stance or '（未设定）'}

AI 角色通过 @超级制作人 向制作人提出的决策问题（必须逐一生成 2-3 条答案选项）：
{qs_text}

最近讨论内容（供参考）：
{recent_context or '（暂无消息）'}

请针对每个问题生成 2-3 条不同角度的答案选项，让制作人选择后发送。"""

        result = await asyncio.get_event_loop().run_in_executor(
            None, _call_llm_for_producer_assist, prompt, _SUPER_PRODUCER_SYSTEM_QUESTIONS
        )

        if result and isinstance(result.get("questions"), list) and result["questions"]:
            result["mode"] = "questions"
            result["discussion_id"] = discussion_id
            result["source"] = result.get("source", "llm")
            return result

        logger.warning(
            "producer-assist %s: Mode A1 LLM returned invalid result=%r, falling back to heuristic",
            discussion_id[:8], result,
        )
        # LLM 失败 → 用第二次更简单的 prompt 重试，只要求它为第一个问题生成 3 条答案
        _q0 = explicit_questions[0]
        _retry_prompt = (
            f"讨论主题：{disc.topic}\n\n"
            f"请为以下决策问题生成3条立场不同的答案选项，每条25-50字，"
            f"输出严格JSON格式 {{\"questions\":[{{\"from_agent\":\"{_q0['from_agent']}\","
            f"\"question\":\"...\",\"answers\":[\"A\",\"B\",\"C\"]}}]}}：\n"
            f"{_q0['question']}"
        )
        _retry_result = await asyncio.get_event_loop().run_in_executor(
            None, _call_llm_for_producer_assist, _retry_prompt, _SUPER_PRODUCER_SYSTEM_QUESTIONS
        )
        if _retry_result and isinstance(_retry_result.get("questions"), list) and _retry_result["questions"]:
            _retry_result["mode"] = "questions"
            _retry_result["discussion_id"] = discussion_id
            _retry_result["source"] = "llm_retry"
            # Merge remaining questions with original question text
            for i, eq in enumerate(explicit_questions[1:3], start=1):
                if i >= len(_retry_result["questions"]):
                    _retry_result["questions"].append({
                        "from_agent": eq["from_agent"],
                        "question": eq["question"],
                        "answers": ["是，按此方向推进", "需要进一步讨论后决定", "暂缓，优先处理其他问题"],
                    })
            return _retry_result

        # 最终回退：通用默认答案（保留正确的问题文本）
        _default_answers = ["是，按此方向推进", "需要进一步讨论后决定", "暂缓，优先处理其他问题"]
        heuristic_questions = [
            {"from_agent": q["from_agent"], "question": q["question"], "answers": _default_answers}
            for q in explicit_questions[:3]
        ]
        return {
            "mode": "questions",
            "questions": heuristic_questions,
            "context_summary": f"当前讨论：{disc.topic[:40]}",
            "source": "heuristic",
            "discussion_id": discussion_id,
        }

    # --- 模式 A2：有隐式问题（AI 消息中的问句）→ 逐题生成答案选项 ---
    if questions_for_producer or checkpoint_q:
        # 若 checkpoint 自带选项 → 直接用，无需 LLM（选项质量高于启发式）
        if checkpoint_q and checkpoint_options:
            answers = [
                f"{opt['label']}：{opt['description']}" if opt.get("description") else opt["label"]
                for opt in checkpoint_options
            ]
            return {
                "mode": "questions",
                "questions": [{"from_agent": "主策划", "question": checkpoint_q, "answers": answers}],
                "context_summary": f"当前讨论：{disc.topic[:40]}",
                "source": "checkpoint",
                "discussion_id": discussion_id,
                "checkpoint_question": checkpoint_q,
            }
        q_list = questions_for_producer[-3:]  # 最多3个问题，避免 JSON 超出 max_tokens
        if checkpoint_q and checkpoint_q not in " ".join(q_list):
            q_list = [f"[主策划] {checkpoint_q}"] + q_list

        qs_text = "\n".join(f"{i+1}. {q}" for i, q in enumerate(q_list))
        prompt = f"""讨论主题：{disc.topic}
制作人立场：{disc.producer_stance or '（未设定）'}

AI 向制作人提出的问题（必须逐一生成 2-3 条答案选项）：
{qs_text}

最近讨论内容（供参考）：
{recent_context or '（暂无消息）'}

请针对每个问题生成 2-3 条不同角度的答案选项，让制作人选择后发送。"""

        result = await asyncio.get_event_loop().run_in_executor(
            None, _call_llm_for_producer_assist, prompt, _SUPER_PRODUCER_SYSTEM_QUESTIONS
        )

        # 校验格式
        if result and isinstance(result.get("questions"), list) and result["questions"]:
            result["mode"] = "questions"
            result["discussion_id"] = discussion_id
            result["checkpoint_question"] = checkpoint_q
            result["source"] = result.get("source", "llm")
            return result

        # LLM 失败或格式错误 → 提供通用默认答案，避免制作人只能看到自定义输入
        import re as _re
        _default_answers = ["是，按此方向推进", "需要进一步讨论后决定", "暂缓，优先处理其他问题"]
        heuristic_questions = []
        for q_str in q_list:
            m = _re.match(r"\[(.+?)\]\s*(.+)", q_str)
            heuristic_questions.append({
                "from_agent": m.group(1) if m else "策划",
                "question": m.group(2) if m else q_str,
                "answers": _default_answers,
            })
        result = {
            "mode": "questions",
            "questions": heuristic_questions,
            "context_summary": f"当前讨论：{disc.topic[:40]}",
            "source": "heuristic",
        }

    # --- 模式 B：无具体问题 → 通用三方向建议 ---
    else:
        prompt = f"""讨论主题：{disc.topic}
制作人立场：{disc.producer_stance or '（未设定）'}

最近讨论内容：
{recent_context or '（暂无消息）'}

请根据以上内容生成三条发言建议。"""

        result = await asyncio.get_event_loop().run_in_executor(
            None, _call_llm_for_producer_assist, prompt, _SUPER_PRODUCER_SYSTEM_GENERAL
        )

        if not result or "suggestions" not in result:
            result = _heuristic_producer_suggestions(disc.topic, recent_context, "")

        result["mode"] = "general"

    result["discussion_id"] = discussion_id
    result["checkpoint_question"] = checkpoint_q
    return result

