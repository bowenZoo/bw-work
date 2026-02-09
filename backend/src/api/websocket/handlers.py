"""WebSocket endpoint handlers."""

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.api.websocket.events import ClientMessageType, PongEvent
from src.api.websocket.manager import connection_manager, global_connection_manager
from src.config.settings import settings
from src.memory.discussion_memory import DiscussionMemory

if TYPE_CHECKING:
    from src.api.routes.discussion import DiscussionState

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

# Memory storage for loading discussion messages
_discussion_memory = DiscussionMemory(data_dir="data/projects")


def _load_doc_contents(discussion_id: str, project_id: str = "default") -> dict[str, str]:
    """Load all .md doc files for a discussion from disk."""
    docs_dir = Path("data/projects") / project_id / discussion_id / "docs"
    result: dict[str, str] = {}
    if docs_dir.exists():
        for path in sorted(docs_dir.glob("*.md")):
            try:
                result[path.name] = path.read_text(encoding="utf-8")
            except Exception:
                pass
    return result


def _get_current_discussion() -> "DiscussionState | None":
    """Lazy import to avoid circular dependency."""
    from src.api.routes.discussion import get_current_discussion
    return get_current_discussion()


def _get_agent_statuses(discussion_id: str | None = None) -> dict[str, str]:
    """Lazy import to avoid circular dependency."""
    from src.api.routes.discussion import get_agent_statuses
    return get_agent_statuses(discussion_id)


async def _send_discussion_sync(websocket: WebSocket, discussion_id: str) -> None:
    """Send initial sync message for a per-discussion WebSocket connection.

    Loads the discussion state, messages, round summaries, agent statuses,
    doc plan, and doc contents, then sends them as a single sync message.
    """
    from src.api.routes.discussion import get_discussion_state

    discussion = get_discussion_state(discussion_id)
    if discussion is None:
        await websocket.send_json({
            "type": "sync",
            "data": {"discussion": None, "messages": []},
        })
        return

    # Load messages
    stored = _discussion_memory.load(discussion_id)
    messages = []
    if stored and stored.messages:
        messages = [
            {
                "id": msg.id,
                "agent_id": msg.agent_id,
                "agent_role": msg.agent_role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
            }
            for msg in stored.messages
        ]

    round_summaries = []
    if stored and stored.round_summaries:
        round_summaries = stored.round_summaries

    doc_plan = stored.doc_plan if stored else None
    doc_contents = _load_doc_contents(discussion_id)

    # Check paused state
    from src.crew.discussion_crew import get_discussion_state as get_disc_state, DiscussionState as DiscState
    disc_state = get_disc_state(discussion_id)
    is_paused = disc_state is not None and disc_state.get("state") == DiscState.PAUSED

    await websocket.send_json({
        "type": "sync",
        "data": {
            "discussion": {
                "id": discussion.id,
                "topic": discussion.topic,
                "rounds": discussion.rounds,
                "status": discussion.status.value,
                "created_at": discussion.created_at,
                "started_at": discussion.started_at,
                "completed_at": discussion.completed_at,
                "result": discussion.result,
                "error": discussion.error,
            },
            "messages": messages,
            "round_summaries": round_summaries,
            "agent_statuses": _get_agent_statuses(discussion_id),
            "doc_plan": doc_plan,
            "doc_contents": doc_contents,
            "is_paused": is_paused,
        },
    })


def _validate_origin(websocket: WebSocket) -> bool:
    """Validate the origin header for cross-origin requests.

    Origin validation strategy:
    - Origin exists and in allowed list -> accept
    - Origin exists but not in allowed list -> reject
    - Origin is empty (CLI, server clients) -> accept (MVP stage)

    Args:
        websocket: The WebSocket connection to validate.

    Returns:
        True if the origin is valid, False otherwise.
    """
    origin = websocket.headers.get("origin")

    # No origin (CLI, server-side clients) -> accept in MVP
    if not origin:
        return True

    # Check against allowed origins
    for prefix in settings.websocket_allowed_origin_prefixes:
        if origin.startswith(prefix):
            return True

    # Exact matches for development
    return origin in settings.websocket_allowed_origins


async def _handle_client_message(websocket: WebSocket, message: dict) -> None:
    """Handle incoming client messages.

    Args:
        websocket: The WebSocket connection.
        message: The parsed message dictionary.
    """
    message_type = message.get("type")

    if message_type == ClientMessageType.PING:
        # Update heartbeat and respond with pong
        connection_manager.update_heartbeat(websocket)
        pong = PongEvent()
        await websocket.send_json(pong.to_dict())
    else:
        logger.debug("Unknown message type: %s", message_type)


async def _handle_global_client_message(websocket: WebSocket, message: dict) -> None:
    """Handle incoming client messages for global WebSocket.

    Args:
        websocket: The WebSocket connection.
        message: The parsed message dictionary.
    """
    message_type = message.get("type")

    if message_type == ClientMessageType.PING:
        # Update heartbeat and respond with pong
        global_connection_manager.update_heartbeat(websocket)
        pong = PongEvent()
        await websocket.send_json(pong.to_dict())
    else:
        logger.debug("Unknown global message type: %s", message_type)


@router.websocket("/ws/discussion")
async def global_websocket_endpoint(websocket: WebSocket) -> None:
    """Global WebSocket endpoint for real-time discussion updates.

    All connected clients share the same global discussion.
    On connection, clients receive:
    - Current discussion state (if any)
    - Historical messages
    - Current viewer count

    Args:
        websocket: The WebSocket connection.
    """
    # Validate origin for cross-origin requests
    if not _validate_origin(websocket):
        logger.warning(
            "Rejected global WebSocket connection from invalid origin: %s",
            websocket.headers.get("origin"),
        )
        await websocket.close(code=1008, reason="Invalid origin")
        return

    # Accept connection and register
    await global_connection_manager.connect(websocket)

    try:
        # Build lobby sync: list all active discussions
        from src.api.routes.discussion import list_active_discussions as _list_active
        active_result = await _list_active()
        discussions_list = active_result.get("discussions", []) if isinstance(active_result, dict) else []

        # Also include the current discussion pointer for backward compatibility
        current = _get_current_discussion()
        logger.info(
            "WebSocket lobby_sync: active=%d, current=%s",
            len(discussions_list),
            f"id={current.id}, status={current.status}" if current else "None",
        )

        # If there is a current discussion, send full sync for it (backward compat)
        if current:
            stored = _discussion_memory.load(current.id)
            messages = []
            if stored and stored.messages:
                messages = [
                    {
                        "id": msg.id,
                        "agent_id": msg.agent_id,
                        "agent_role": msg.agent_role,
                        "content": msg.content,
                        "timestamp": msg.timestamp.isoformat(),
                    }
                    for msg in stored.messages
                ]

            round_summaries = []
            if stored and stored.round_summaries:
                round_summaries = stored.round_summaries

            doc_plan = stored.doc_plan if stored else None
            doc_contents = _load_doc_contents(current.id)

            from src.crew.discussion_crew import get_discussion_state as get_disc_state, DiscussionState as DiscState
            disc_state = get_disc_state(current.id)
            is_paused = disc_state is not None and disc_state.get("state") == DiscState.PAUSED

            await websocket.send_json({
                "type": "sync",
                "data": {
                    "discussion": {
                        "id": current.id,
                        "topic": current.topic,
                        "rounds": current.rounds,
                        "status": current.status.value,
                        "created_at": current.created_at,
                        "started_at": current.started_at,
                        "completed_at": current.completed_at,
                        "result": current.result,
                        "error": current.error,
                    },
                    "messages": messages,
                    "round_summaries": round_summaries,
                    "agent_statuses": _get_agent_statuses(current.id),
                    "doc_plan": doc_plan,
                    "doc_contents": doc_contents,
                    "is_paused": is_paused,
                },
            })
        else:
            await websocket.send_json({
                "type": "sync",
                "data": {
                    "discussion": None,
                    "messages": [],
                },
            })

        # Send lobby_sync with active discussions list
        await websocket.send_json({
            "type": "lobby_sync",
            "data": {
                "discussions": discussions_list,
            },
        })

        # Send current viewer count
        await websocket.send_json({
            "type": "viewers",
            "data": {
                "count": global_connection_manager.connection_count,
            },
        })

        # Message loop
        while True:
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                await _handle_global_client_message(websocket, message)
            except json.JSONDecodeError:
                logger.warning("Received invalid JSON: %s", data)
            except Exception as exc:
                logger.error("Error handling global message: %s", exc)

    except WebSocketDisconnect:
        logger.info("Global WebSocket disconnected")
    except Exception as exc:
        logger.error("Global WebSocket error: %s", exc)
    finally:
        await global_connection_manager.disconnect(websocket)


@router.websocket("/ws/{discussion_id}")
async def websocket_endpoint(websocket: WebSocket, discussion_id: str) -> None:
    """WebSocket endpoint for per-discussion real-time updates.

    Args:
        websocket: The WebSocket connection.
        discussion_id: The discussion ID to subscribe to.
    """
    if not _validate_origin(websocket):
        logger.warning(
            "Rejected WebSocket connection from invalid origin: %s",
            websocket.headers.get("origin"),
        )
        await websocket.close(code=1008, reason="Invalid origin")
        return

    await connection_manager.connect(websocket, discussion_id)

    try:
        # Send initial sync with current discussion state
        await _send_discussion_sync(websocket, discussion_id)

        while True:
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                await _handle_client_message(websocket, message)
            except json.JSONDecodeError:
                logger.warning("Received invalid JSON: %s", data)
            except Exception as exc:
                logger.error("Error handling message: %s", exc)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: discussion_id=%s", discussion_id)
    except Exception as exc:
        logger.error("WebSocket error: %s", exc)
    finally:
        connection_manager.disconnect(websocket, discussion_id)
