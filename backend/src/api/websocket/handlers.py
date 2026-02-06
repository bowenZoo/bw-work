"""WebSocket endpoint handlers."""

import json
import logging
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


def _get_current_discussion() -> "DiscussionState | None":
    """Lazy import to avoid circular dependency."""
    from src.api.routes.discussion import get_current_discussion
    return get_current_discussion()


@router.websocket("/ws/{discussion_id}")
async def websocket_endpoint(websocket: WebSocket, discussion_id: str) -> None:
    """WebSocket endpoint for real-time discussion updates.

    Args:
        websocket: The WebSocket connection.
        discussion_id: The discussion ID to subscribe to.
    """
    # Validate origin for cross-origin requests
    if not _validate_origin(websocket):
        logger.warning(
            "Rejected WebSocket connection from invalid origin: %s",
            websocket.headers.get("origin"),
        )
        await websocket.close(code=1008, reason="Invalid origin")
        return

    # Accept connection and register
    await connection_manager.connect(websocket, discussion_id)

    try:
        while True:
            # Receive message from client
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
        # Send current discussion state and historical messages
        current = _get_current_discussion()
        if current:
            # Load historical messages
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
