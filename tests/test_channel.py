"""Tests for the MCP channel module."""

from __future__ import annotations

from unittest.mock import patch

from channel import ChannelProtocol, StubChannel


async def test_stub_channel_implements_protocol() -> None:
    """Test that StubChannel satisfies ChannelProtocol."""
    channel = StubChannel()
    assert isinstance(channel, ChannelProtocol)


async def test_stub_channel_echoes_message() -> None:
    """Test that StubChannel returns a response containing the user message."""
    channel = StubChannel()
    with patch("channel.trace_span"):
        chunks = await channel.send_message("Hello", history=[])
    assert len(chunks) == 1
    assert "Hello" in chunks[0]


async def test_stub_channel_with_files() -> None:
    """Test that StubChannel mentions attached files in response."""
    channel = StubChannel()
    with patch("channel.trace_span"):
        chunks = await channel.send_message(
            "Review this",
            history=[],
            file_paths=["/tmp/file1.py", "/tmp/file2.py"],
        )
    assert "2 attached file(s)" in chunks[0]


async def test_stub_channel_with_history() -> None:
    """Test that StubChannel accepts history without error."""
    channel = StubChannel()
    history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
    ]
    with patch("channel.trace_span"):
        chunks = await channel.send_message("Follow up", history=history)
    assert len(chunks) == 1
