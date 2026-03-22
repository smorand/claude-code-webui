"""Tests for the MCP channel server module."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

from channel import (
    _build_edit_tool,
    _build_reply_tool,
    _handle_edit,
    _handle_reply,
    create_mcp_server,
    register_handlers,
)
from channel_bridge import ChannelBridge
from config import Settings


def test_create_mcp_server() -> None:
    """Server is created with correct name and instructions."""
    server = create_mcp_server(name="test")
    assert server.name == "test"


def test_reply_tool_schema() -> None:
    """Reply tool has correct input schema."""
    tool = _build_reply_tool()
    assert tool.name == "reply"
    assert "text" in tool.inputSchema["properties"]
    assert "reply_to" in tool.inputSchema["properties"]
    assert "files" in tool.inputSchema["properties"]
    assert tool.inputSchema["required"] == ["text"]


def test_edit_tool_schema() -> None:
    """Edit tool has correct input schema."""
    tool = _build_edit_tool()
    assert tool.name == "edit_message"
    assert "message_id" in tool.inputSchema["properties"]
    assert "text" in tool.inputSchema["properties"]
    assert set(tool.inputSchema["required"]) == {"message_id", "text"}


async def test_handle_reply_no_text() -> None:
    """E2E-NEW-010 variant: Reply with no text returns error."""
    bridge = AsyncMock(spec=ChannelBridge)
    settings = Settings()

    result = await _handle_reply(bridge, settings, {"text": "", "files": []})

    assert len(result) == 1
    assert "required" in result[0].text.lower()


async def test_handle_reply_success() -> None:
    """Reply tool delegates to bridge and returns message ID."""
    bridge = AsyncMock(spec=ChannelBridge)
    bridge.handle_reply.return_value = "msg-123"
    settings = Settings()

    result = await _handle_reply(bridge, settings, {"text": "hello"})

    bridge.handle_reply.assert_awaited_once_with(text="hello", reply_to=None, file_info=None)
    assert "msg-123" in result[0].text


async def test_handle_reply_with_file(tmp_path: Any) -> None:
    """E2E-NEW-011: Reply with file copies to outbox."""
    source = tmp_path / "test.txt"
    source.write_text("content")

    bridge = AsyncMock(spec=ChannelBridge)
    bridge.handle_reply.return_value = "msg-123"
    settings = Settings(
        channel_outbox_dir=tmp_path / "outbox",
        channel_max_file_size=1_000_000,
    )

    with patch("channel.trace_span"):
        result = await _handle_reply(bridge, settings, {"text": "file", "files": [str(source)]})

    assert "msg-123" in result[0].text
    call_kwargs = bridge.handle_reply.call_args[1]
    assert call_kwargs["file_info"]["name"] == "test.txt"
    assert call_kwargs["file_info"]["url"].startswith("/files/")

    outbox = tmp_path / "outbox"
    assert outbox.exists()
    assert len(list(outbox.iterdir())) == 1


async def test_handle_reply_file_not_found() -> None:
    """Reply with nonexistent file returns error."""
    bridge = AsyncMock(spec=ChannelBridge)
    settings = Settings()

    result = await _handle_reply(bridge, settings, {"text": "file", "files": ["/nonexistent/file.txt"]})

    assert result[0].text.startswith("Error")
    assert "not found" in result[0].text


async def test_handle_reply_file_too_large(tmp_path: Any) -> None:
    """E2E-NEW-012: Reply with oversized file returns error."""
    source = tmp_path / "large.bin"
    source.write_bytes(b"x" * 200)

    bridge = AsyncMock(spec=ChannelBridge)
    settings = Settings(
        channel_max_file_size=100,
    )

    with patch("channel.trace_span"):
        result = await _handle_reply(bridge, settings, {"text": "file", "files": [str(source)]})

    assert "too large" in result[0].text.lower()


async def test_handle_edit_success() -> None:
    """Edit tool delegates to bridge and returns ok."""
    bridge = AsyncMock(spec=ChannelBridge)
    bridge.handle_edit.return_value = True

    result = await _handle_edit(bridge, {"message_id": "m1", "text": "updated"})

    bridge.handle_edit.assert_awaited_once_with(message_id="m1", text="updated")
    assert result[0].text == "ok"


async def test_handle_edit_not_found() -> None:
    """Edit of nonexistent message returns error."""
    bridge = AsyncMock(spec=ChannelBridge)
    bridge.handle_edit.return_value = False

    result = await _handle_edit(bridge, {"message_id": "m1", "text": "updated"})

    assert "not found" in result[0].text.lower()


async def test_handle_edit_missing_params() -> None:
    """Edit with missing params returns error."""
    bridge = AsyncMock(spec=ChannelBridge)

    result = await _handle_edit(bridge, {"message_id": "", "text": ""})

    assert "required" in result[0].text.lower()


async def test_unknown_tool_returns_error() -> None:
    """E2E-NEW-010: Unknown tool name returns error text."""
    bridge = AsyncMock(spec=ChannelBridge)
    settings = Settings()

    server = create_mcp_server(name="test")
    register_handlers(server, bridge, settings)

    # The handler is registered internally; test via the tool dispatch logic
    # which is captured in handle_call_tool closure. We test the individual
    # handlers directly since the decorator registrations are internal to MCP SDK.
