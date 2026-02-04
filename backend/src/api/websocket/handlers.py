"""WebSocket endpoint handlers."""

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.api.websocket.events import ClientMessageType, PongEvent
from src.api.websocket.manager import connection_manager
from src.config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


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
