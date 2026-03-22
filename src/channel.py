"""MCP channel protocol and stub implementation for Claude communication."""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from tracing import trace_span

logger = logging.getLogger(__name__)


@runtime_checkable
class ChannelProtocol(Protocol):
    """Protocol for the Claude communication layer.

    The real implementation will come from the MCP channel spec.
    """

    async def send_message(
        self,
        message: str,
        history: list[dict[str, str]],
        file_paths: list[str] | None = None,
    ) -> list[str]:
        """Send a message to Claude and return response chunks.

        Args:
            message: The user message text.
            history: Conversation history as list of {"role": ..., "content": ...} dicts.
            file_paths: Optional file paths to include as context.

        Returns:
            List of response text chunks.
        """
        ...


class StubChannel:
    """Stub implementation of the MCP channel for development and testing.

    Echoes the user message back as a placeholder response.
    """

    __slots__ = ()

    async def send_message(
        self,
        message: str,
        history: list[dict[str, str]],
        file_paths: list[str] | None = None,
    ) -> list[str]:
        """Return a stub response echoing the user message."""
        with trace_span(
            "channel.send_message",
            attributes={"message_length": len(message), "history_length": len(history)},
        ):
            file_note = ""
            if file_paths:
                file_note = f" (with {len(file_paths)} attached file(s))"

            response = f"[Stub] Received: {message}{file_note}"
            logger.debug("Stub channel responding to message: %s", message[:100])
            return [response]
