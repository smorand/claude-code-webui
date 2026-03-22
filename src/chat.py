"""WebSocket chat handler for real-time Claude conversations."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from tracing import trace_span

if TYPE_CHECKING:
    from channel import ChannelProtocol
    from config import Settings
    from database import Database

logger = logging.getLogger(__name__)


async def _send_error(websocket: WebSocket, detail: str) -> None:
    """Send an error message over WebSocket."""
    await websocket.send_json({"type": "error", "detail": detail})


async def _resolve_conversation(
    db: Database,
    websocket: WebSocket,
    req_conversation_id: str | None,
    current_conversation_id: str | None,
) -> str | None:
    """Resolve or create conversation ID. Returns None on error (error already sent)."""
    if req_conversation_id:
        conv = await db.get_conversation(req_conversation_id)
        if conv is None:
            await _send_error(websocket, f"Conversation not found: {req_conversation_id}")
            return None
        return req_conversation_id

    if current_conversation_id is not None:
        return current_conversation_id

    conv = await db.create_conversation()
    return conv.id


async def _resolve_attachments(
    db: Database,
    websocket: WebSocket,
    attachments: list[dict[str, str]],
    message_id: str,
) -> list[str]:
    """Resolve file attachments: link to message and return file paths. Warns on missing files."""
    file_paths: list[str] = []
    for attachment in attachments:
        file_id = attachment.get("file_id", "")
        file_record = await db.get_file(file_id)
        if file_record is None:
            logger.warning("File not found: %s", file_id)
            await websocket.send_json({"type": "warning", "detail": f"File not found: {file_id}"})
        else:
            file_paths.append(file_record.storage_path)
            await db.link_file_to_message(file_id, message_id)
    return file_paths


async def _stream_response(
    channel: ChannelProtocol,
    db: Database,
    websocket: WebSocket,
    conversation_id: str,
    content: str,
    history: list[dict[str, str]],
    file_paths: list[str],
) -> None:
    """Send message to channel and stream response back via WebSocket."""
    with trace_span("ws.stream_response"):
        chunks = await channel.send_message(
            message=content,
            history=history,
            file_paths=file_paths if file_paths else None,
        )

        full_response = ""
        for chunk in chunks:
            full_response += chunk
            await websocket.send_json({"type": "assistant_chunk", "content": chunk, "conversation_id": conversation_id})

        await db.add_message(conversation_id, "assistant", full_response)
        await websocket.send_json(
            {"type": "assistant_complete", "content": full_response, "conversation_id": conversation_id}
        )


def create_chat_router(settings: Settings, db: Database, channel: ChannelProtocol) -> APIRouter:
    """Create the WebSocket chat router."""
    router = APIRouter()

    @router.websocket("/ws/chat")
    async def websocket_chat(websocket: WebSocket) -> None:
        """Handle WebSocket chat connections."""
        await websocket.accept()
        conversation_id: str | None = None

        try:
            while True:
                raw = await websocket.receive_text()
                with trace_span("ws.message_received"):
                    data, content, attachments = _parse_message(raw)
                    if data is None:
                        await _send_error(websocket, "Invalid JSON")
                        continue

                    msg_type = data.get("type")
                    if msg_type != "user_message":
                        await _send_error(websocket, f"Unknown message type: {msg_type}")
                        continue

                    if not content and not attachments:
                        await _send_error(websocket, "Message content is empty and no attachments provided")
                        continue

                    resolved_id = await _resolve_conversation(
                        db, websocket, data.get("conversation_id"), conversation_id
                    )
                    if resolved_id is None:
                        continue
                    conversation_id = resolved_id

                    await websocket.send_json({"type": "connected", "conversation_id": conversation_id})

                    user_msg = await db.add_message(conversation_id, "user", content)
                    file_paths = await _resolve_attachments(db, websocket, attachments, user_msg.id)

                    history_rows = await db.get_messages(conversation_id, limit=settings.max_history_messages)
                    history = [{"role": m.role, "content": m.content} for m in history_rows]

                    await _stream_response(channel, db, websocket, conversation_id, content, history, file_paths)

        except WebSocketDisconnect:
            logger.info("WebSocket disconnected for conversation %s", conversation_id)

    return router


def _parse_message(raw: str) -> tuple[dict[str, Any] | None, str, list[dict[str, str]]]:
    """Parse a raw WebSocket message. Returns (data, content, attachments) or (None, "", []) on parse error."""
    try:
        data: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError:
        return None, "", []
    content = data.get("content", "").strip()
    attachments: list[dict[str, str]] = data.get("attachments", [])
    return data, content, attachments
