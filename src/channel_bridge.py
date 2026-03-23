"""Shared state bridge between MCP channel server and FastAPI WebSocket layer.

Manages connected WebSocket clients, message broadcast, delivery to MCP,
and SQLite persistence for all channel messages.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from tracing import trace_span

if TYPE_CHECKING:
    from fastapi import WebSocket

    from database import Database

logger = logging.getLogger(__name__)

NotifySender = Callable[[str, dict[str, str]], Coroutine[Any, Any, None]]


class ChannelBridge:
    """Bridge between the MCP channel server and the FastAPI WebSocket layer.

    Coordinates message flow, client tracking, SQLite persistence,
    and MCP notification emission.
    """

    __slots__ = ("_clients", "_db", "_notify_sender", "_settings_channel_name")

    def __init__(
        self,
        db: Database,
        channel_name: str = "webui",
    ) -> None:
        self._db = db
        self._settings_channel_name = channel_name
        self._clients: set[WebSocket] = set()
        self._notify_sender: NotifySender | None = None

    @property
    def clients(self) -> set[WebSocket]:
        """Return the set of connected WebSocket clients."""
        return self._clients

    def set_notify_sender(self, sender: NotifySender) -> None:
        """Register the MCP notification sender callback.

        Called by the channel server once the MCP session is established.
        """
        self._notify_sender = sender

    def add_client(self, ws: WebSocket) -> None:
        """Register a WebSocket client for broadcasts."""
        self._clients.add(ws)
        logger.info("WebSocket client connected, total: %d", len(self._clients))

    def remove_client(self, ws: WebSocket) -> None:
        """Unregister a WebSocket client."""
        self._clients.discard(ws)
        logger.info("WebSocket client disconnected, total: %d", len(self._clients))

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send a JSON message to all connected WebSocket clients."""
        payload = json.dumps(message)
        logger.info("Broadcasting to %d clients: type=%s", len(self._clients), message.get("type"))
        disconnected: list[WebSocket] = []
        for client in self._clients:
            try:
                await client.send_text(payload)
            except Exception:
                logger.warning("Failed to send to WebSocket client, removing")
                disconnected.append(client)
        for client in disconnected:
            self._clients.discard(client)

    async def deliver(
        self,
        message_id: str,
        text: str,
        chat_id: str = "web",
        user: str = "web",
        file_path: str | None = None,
    ) -> None:
        """Deliver a user message: persist to SQLite then emit MCP notification.

        Args:
            message_id: Unique message identifier.
            text: Message text content.
            chat_id: Chat/conversation identifier.
            user: Username of the sender.
            file_path: Optional absolute path to an attached file.
        """
        with trace_span("channel.deliver", attributes={"message_id": message_id, "chat_id": chat_id}):
            await self._persist_user_message(message_id, chat_id, text, file_path)
            await self._emit_notification(message_id, text, chat_id, user, file_path)

    async def handle_reply(
        self,
        text: str,
        reply_to: str | None = None,
        file_info: dict[str, str] | None = None,
        chat_id: str = "web",
    ) -> str:
        """Handle a reply from Claude: persist to SQLite then broadcast.

        Returns the generated message ID.
        """
        with trace_span("channel.reply", attributes={"chat_id": chat_id}):
            msg_id = str(uuid.uuid4())
            ts = datetime.now(UTC).isoformat()

            await self._persist_assistant_message(msg_id, chat_id, text)

            payload: dict[str, Any] = {
                "type": "msg",
                "id": msg_id,
                "from": "assistant",
                "text": text,
                "ts": ts,
            }
            if reply_to:
                payload["replyTo"] = reply_to
            if file_info:
                payload["file"] = file_info

            await self.broadcast(payload)
            return msg_id

    async def handle_edit(self, message_id: str, text: str) -> bool:
        """Handle an edit from Claude: update SQLite then broadcast.

        Returns True if the message was found and updated.
        """
        with trace_span("channel.edit", attributes={"message_id": message_id}):
            updated = await self._persist_edit(message_id, text)
            if not updated:
                return False

            await self.broadcast(
                {
                    "type": "edit",
                    "id": message_id,
                    "text": text,
                }
            )
            return True

    async def _persist_user_message(
        self,
        message_id: str,
        chat_id: str,
        text: str,
        file_path: str | None,  # noqa: ARG002 -- reserved for future file metadata persistence
    ) -> None:
        """Persist a user message to SQLite. Log and continue on failure."""
        try:
            with trace_span("channel.persist", attributes={"message_id": message_id, "operation": "insert_user"}):
                conversation = await self._db.get_conversation(chat_id)
                if conversation is None:
                    await self._db.create_conversation(title=text[:50])
                await self._db.add_message(chat_id, "user", text)
        except Exception:
            logger.exception("Failed to persist user message %s", message_id)

    async def _persist_assistant_message(
        self,
        message_id: str,
        chat_id: str,
        text: str,
    ) -> None:
        """Persist an assistant message to SQLite. Log and continue on failure."""
        try:
            with trace_span("channel.persist", attributes={"message_id": message_id, "operation": "insert_assistant"}):
                await self._db.add_message(chat_id, "assistant", text)
        except Exception:
            logger.exception("Failed to persist assistant message %s", message_id)

    async def _persist_edit(self, message_id: str, text: str) -> bool:
        """Update a message in SQLite. Returns False if not found. Logs on failure."""
        try:
            with trace_span("channel.persist", attributes={"message_id": message_id, "operation": "update"}):
                return await self._db.update_message(message_id, text)
        except Exception:
            logger.exception("Failed to persist edit for message %s", message_id)
            return False

    async def _emit_notification(
        self,
        message_id: str,
        text: str,
        chat_id: str,
        user: str,
        file_path: str | None,
    ) -> None:
        """Emit a notifications/claude/channel MCP notification."""
        if self._notify_sender is None:
            logger.warning("No MCP notification sender registered, message %s not forwarded to Claude", message_id)
            return

        ts = datetime.now(UTC).isoformat()
        meta: dict[str, str] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "user": user,
            "ts": ts,
        }
        if file_path:
            meta["file_path"] = file_path

        try:
            with trace_span("channel.notify", attributes={"message_id": message_id}):
                await self._notify_sender(text, meta)
        except Exception:
            logger.exception("Failed to emit MCP notification for message %s", message_id)
