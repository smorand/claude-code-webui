"""MCP channel server for Claude Code communication.

Implements the claude/channel experimental capability over stdio transport.
Exposes reply and edit_message tools for two-way communication.
This is the sole communication channel between the web UI and Claude Code.
"""

from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

import mcp.server.stdio
from mcp import types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.shared.message import SessionMessage as McpSessionMessage

from tracing import trace_span

if TYPE_CHECKING:
    from anyio.streams.memory import MemoryObjectSendStream

    from channel_bridge import ChannelBridge
    from config import Settings

logger = logging.getLogger(__name__)

_INSTRUCTIONS = (
    "The sender reads the webui chat, not this session."
    " Anything you want them to see must go through the reply tool;"
    " your transcript output never reaches the UI.\n\n"
    "Messages from the web UI arrive as"
    ' <channel source="webui" chat_id="web" message_id="...">.'
    " If the tag has a file_path attribute, Read that file;"
    " it is an upload from the UI."
    " Reply with the reply tool."
    " To edit a previous message, call the edit_message tool"
    " with the message_id and new text."
)


def create_mcp_server(name: str = "webui") -> Server:
    """Create and configure the MCP channel server with tool handlers."""
    return Server(name, instructions=_INSTRUCTIONS)


def _build_reply_tool() -> types.Tool:
    """Build the reply tool definition."""
    return types.Tool(
        name="reply",
        description="Send a message back to the web UI",
        inputSchema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Message text to send"},
                "reply_to": {"type": "string", "description": "Optional message ID to reply to"},
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of absolute file paths to attach",
                },
            },
            "required": ["text"],
        },
    )


def _build_edit_tool() -> types.Tool:
    """Build the edit_message tool definition."""
    return types.Tool(
        name="edit_message",
        description="Edit a previously sent message",
        inputSchema={
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "ID of the message to edit"},
                "text": {"type": "string", "description": "New text for the message"},
            },
            "required": ["message_id", "text"],
        },
    )


def register_handlers(
    server: Server,
    bridge: ChannelBridge,
    settings: Settings,
) -> None:
    """Register MCP tool handlers on the server, wired to the channel bridge."""

    @server.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]
    async def handle_list_tools() -> list[types.Tool]:
        return [_build_reply_tool(), _build_edit_tool()]

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
        logger.info("MCP tool called: %s with args: %s", name, list(arguments.keys()))
        if name == "reply":
            return await _handle_reply(bridge, settings, arguments)
        if name == "edit_message":
            return await _handle_edit(bridge, arguments)
        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


async def _handle_reply(
    bridge: ChannelBridge,
    settings: Settings,
    arguments: dict[str, Any],
) -> list[types.TextContent]:
    """Handle the reply tool call."""
    text: str = arguments.get("text", "")
    reply_to: str | None = arguments.get("reply_to")
    files: list[str] = arguments.get("files", [])

    if not text and not files:
        return [types.TextContent(type="text", text="Error: text is required")]

    file_info: dict[str, str] | None = None
    if files:
        source = Path(files[0])
        if not source.exists():
            return [types.TextContent(type="text", text=f"Error: file not found: {files[0]}")]

        with trace_span("channel.file_copy", attributes={"source": str(source)}):
            file_size = source.stat().st_size
            if file_size > settings.channel_max_file_size:
                return [types.TextContent(type="text", text="Error: file too large")]

            outbox = settings.resolved_outbox_dir
            outbox.mkdir(parents=True, exist_ok=True)
            dest_name = f"{uuid.uuid4().hex}_{source.name}"
            dest = outbox / dest_name
            shutil.copy2(source, dest)

            file_info = {
                "url": f"/files/{dest_name}",
                "name": source.name,
            }

    msg_id = await bridge.handle_reply(text=text, reply_to=reply_to, file_info=file_info)
    return [types.TextContent(type="text", text=f"Sent message {msg_id}")]


async def _handle_edit(
    bridge: ChannelBridge,
    arguments: dict[str, Any],
) -> list[types.TextContent]:
    """Handle the edit_message tool call."""
    message_id: str = arguments.get("message_id", "")
    text: str = arguments.get("text", "")

    if not message_id or not text:
        return [types.TextContent(type="text", text="Error: message_id and text are required")]

    updated = await bridge.handle_edit(message_id=message_id, text=text)
    if not updated:
        return [types.TextContent(type="text", text=f"Error: message {message_id} not found")]
    return [types.TextContent(type="text", text="ok")]


def _build_notify_sender(
    write_stream: MemoryObjectSendStream[McpSessionMessage],
) -> Any:
    """Create a notification sender function that writes to the MCP stdio stream."""

    async def send_notification(content: str, meta: dict[str, str]) -> None:
        notification = types.JSONRPCNotification(
            jsonrpc="2.0",
            method="notifications/claude/channel",
            params={"content": content, "meta": meta},
        )
        message = types.JSONRPCMessage(root=notification)
        await write_stream.send(McpSessionMessage(message))

    return send_notification


async def run_channel_server(
    bridge: ChannelBridge,
    settings: Settings,
) -> None:
    """Run the MCP channel server on stdio transport.

    This is the main entry point for the MCP server process.
    It blocks until the stdio connection is closed.
    """
    server = create_mcp_server(name=settings.channel_name)
    register_handlers(server, bridge, settings)

    init_options = server.create_initialization_options(
        notification_options=NotificationOptions(),
        experimental_capabilities={"claude/channel": {}},
    )

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        bridge.set_notify_sender(_build_notify_sender(write_stream))
        logger.info("MCP channel server starting on stdio")
        await server.run(read_stream, write_stream, init_options)
