"""Tests for the SQLite database layer."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from database import Database

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
async def db(tmp_path: Path) -> Database:
    """Create a test database instance with initialized schema."""
    db_path = str(tmp_path / "test.db")
    database = Database(db_path=db_path)
    with patch("database.trace_span"):
        await database.init_schema()
    return database


async def test_init_schema_idempotent(db: Database) -> None:
    """E2E-NEW-015: Schema initialization is idempotent."""
    with patch("database.trace_span"):
        await db.init_schema()
        await db.init_schema()


async def test_create_conversation(db: Database) -> None:
    """Test creating a new conversation."""
    with patch("database.trace_span"):
        conv = await db.create_conversation()
    assert conv.id is not None
    assert conv.title is None
    assert conv.created_at is not None


async def test_get_conversation(db: Database) -> None:
    """Test retrieving a conversation by ID."""
    with patch("database.trace_span"):
        conv = await db.create_conversation()
        retrieved = await db.get_conversation(conv.id)
    assert retrieved is not None
    assert retrieved.id == conv.id


async def test_get_conversation_not_found(db: Database) -> None:
    """Test that missing conversation returns None."""
    with patch("database.trace_span"):
        result = await db.get_conversation("nonexistent")
    assert result is None


async def test_list_conversations(db: Database) -> None:
    """E2E-NEW-011: List conversations ordered by updated_at desc."""
    with patch("database.trace_span"):
        await db.create_conversation(title="First")
        await db.create_conversation(title="Second")
        await db.create_conversation(title="Third")
        convs = await db.list_conversations()
    assert len(convs) == 3
    assert convs[0].title == "Third"


async def test_add_message(db: Database) -> None:
    """Test adding a message to a conversation."""
    with patch("database.trace_span"):
        conv = await db.create_conversation()
        msg = await db.add_message(conv.id, "user", "Hello")
    assert msg.conversation_id == conv.id
    assert msg.role == "user"
    assert msg.content == "Hello"


async def test_conversation_title_auto_generated(db: Database) -> None:
    """E2E-NEW-017: Title auto-generated from first user message (first 50 chars)."""
    with patch("database.trace_span"):
        conv = await db.create_conversation()
        await db.add_message(conv.id, "user", "Please help me review this Python code for security issues")
        updated = await db.get_conversation(conv.id)
    assert updated is not None
    assert updated.title == "Please help me review this Python code for securit"


async def test_get_messages(db: Database) -> None:
    """Test retrieving messages for a conversation."""
    with patch("database.trace_span"):
        conv = await db.create_conversation()
        await db.add_message(conv.id, "user", "Hello")
        await db.add_message(conv.id, "assistant", "Hi there!")
        messages = await db.get_messages(conv.id)
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"


async def test_get_messages_with_limit(db: Database) -> None:
    """E2E-NEW-012: History truncation returns only the N most recent messages."""
    with patch("database.trace_span"):
        conv = await db.create_conversation()
        for i in range(5):
            await db.add_message(conv.id, "user", f"Message {i}")
        limited = await db.get_messages(conv.id, limit=2)
        all_msgs = await db.get_messages(conv.id)
    assert len(limited) == 2
    assert limited[0].content == "Message 3"
    assert limited[1].content == "Message 4"
    assert len(all_msgs) == 5


async def test_conversation_persists(tmp_path: Path) -> None:
    """E2E-NEW-010: Conversation persists across simulated restart."""
    db_path = str(tmp_path / "persist.db")

    with patch("database.trace_span"):
        db1 = Database(db_path=db_path)
        await db1.init_schema()
        conv = await db1.create_conversation(title="Persistent")
        await db1.add_message(conv.id, "user", "Hello")

        db2 = Database(db_path=db_path)
        await db2.init_schema()
        retrieved = await db2.get_conversation(conv.id)
        messages = await db2.get_messages(conv.id)

    assert retrieved is not None
    assert retrieved.title == "Persistent"
    assert len(messages) == 1


async def test_add_file_and_get(db: Database) -> None:
    """E2E-NEW-016: File metadata recorded and retrievable."""
    with patch("database.trace_span"):
        file_row = await db.add_file(
            file_id="test-uuid",
            filename="test.py",
            size=1024,
            content_type="text/x-python",
            storage_path="/tmp/test-uuid/test.py",
        )
        assert file_row.id == "test-uuid"
        assert file_row.message_id is None

        retrieved = await db.get_file("test-uuid")
    assert retrieved is not None
    assert retrieved.filename == "test.py"
    assert retrieved.size == 1024


async def test_link_file_to_message(db: Database) -> None:
    """Test linking a file to a message."""
    with patch("database.trace_span"):
        conv = await db.create_conversation()
        msg = await db.add_message(conv.id, "user", "See attached")
        await db.add_file("f1", "doc.txt", 100, "text/plain", "/tmp/f1/doc.txt")
        await db.link_file_to_message("f1", msg.id)
        files = await db.get_files_for_message(msg.id)
    assert len(files) == 1
    assert files[0].message_id == msg.id


async def test_get_file_not_found(db: Database) -> None:
    """Test that missing file returns None."""
    with patch("database.trace_span"):
        result = await db.get_file("nonexistent")
    assert result is None
