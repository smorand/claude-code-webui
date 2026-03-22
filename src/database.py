"""SQLite database layer with aiosqlite for conversation and file persistence."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite

from tracing import trace_span

logger = logging.getLogger(__name__)

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);

CREATE TABLE IF NOT EXISTS files (
    id TEXT PRIMARY KEY,
    message_id TEXT,
    filename TEXT NOT NULL,
    size INTEGER NOT NULL,
    content_type TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (message_id) REFERENCES messages(id)
);

CREATE INDEX IF NOT EXISTS idx_files_message_id ON files(message_id);
"""


@dataclass(frozen=True)
class ConversationRow:
    """Value object for a conversation record."""

    __slots__ = ("created_at", "id", "title", "updated_at")
    id: str
    title: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class MessageRow:
    """Value object for a message record."""

    __slots__ = ("content", "conversation_id", "created_at", "id", "role")
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: str


@dataclass(frozen=True)
class FileRow:
    """Value object for a file record."""

    __slots__ = ("content_type", "created_at", "filename", "id", "message_id", "size", "storage_path")
    id: str
    message_id: str | None
    filename: str
    size: int
    content_type: str
    storage_path: str
    created_at: str


class Database:
    """Async SQLite database with repository methods for conversations, messages, and files."""

    __slots__ = ("_db_path",)

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def init_schema(self) -> None:
        """Create database tables if they do not exist. Enables WAL mode."""
        with trace_span("db.init_schema"):
            db_dir = Path(self._db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute("PRAGMA journal_mode=WAL")
                await db.executescript(_SCHEMA_SQL)
                await db.commit()
            logger.info("Database schema initialized at %s", self._db_path)

    async def create_conversation(self, title: str | None = None) -> ConversationRow:
        """Create a new conversation and return it."""
        with trace_span("db.create_conversation"):
            conversation_id = str(uuid.uuid4())
            now = datetime.now(UTC).isoformat()
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (conversation_id, title, now, now),
                )
                await db.commit()
            return ConversationRow(id=conversation_id, title=title, created_at=now, updated_at=now)

    async def get_conversation(self, conversation_id: str) -> ConversationRow | None:
        """Get a conversation by ID, or None if not found."""
        with trace_span("db.get_conversation", attributes={"conversation_id": conversation_id}):
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,))
                row = await cursor.fetchone()
                if row is None:
                    return None
                return ConversationRow(
                    id=row["id"],
                    title=row["title"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )

    async def list_conversations(self) -> list[ConversationRow]:
        """List all conversations ordered by updated_at descending."""
        with trace_span("db.list_conversations"):
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("SELECT * FROM conversations ORDER BY updated_at DESC")
                rows = await cursor.fetchall()
                return [
                    ConversationRow(
                        id=row["id"],
                        title=row["title"],
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                    )
                    for row in rows
                ]

    async def add_message(self, conversation_id: str, role: str, content: str) -> MessageRow:
        """Add a message to a conversation. Updates conversation title and updated_at."""
        with trace_span("db.add_message", attributes={"conversation_id": conversation_id, "role": role}):
            message_id = str(uuid.uuid4())
            now = datetime.now(UTC).isoformat()
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    "INSERT INTO messages (id, conversation_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
                    (message_id, conversation_id, role, content, now),
                )
                # Update conversation updated_at
                await db.execute(
                    "UPDATE conversations SET updated_at = ? WHERE id = ?",
                    (now, conversation_id),
                )
                # Auto-generate title from first user message
                if role == "user":
                    cursor = await db.execute(
                        "SELECT title FROM conversations WHERE id = ?",
                        (conversation_id,),
                    )
                    row = await cursor.fetchone()
                    if row and row[0] is None:
                        title = content[:50]
                        await db.execute(
                            "UPDATE conversations SET title = ? WHERE id = ?",
                            (title, conversation_id),
                        )
                await db.commit()
            return MessageRow(
                id=message_id,
                conversation_id=conversation_id,
                role=role,
                content=content,
                created_at=now,
            )

    async def get_messages(self, conversation_id: str, limit: int | None = None) -> list[MessageRow]:
        """Get messages for a conversation, ordered by created_at. If limit is set, return the most recent N."""
        with trace_span("db.get_messages", attributes={"conversation_id": conversation_id}):
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                if limit is not None:
                    cursor = await db.execute(
                        "SELECT * FROM (SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at DESC LIMIT ?) ORDER BY created_at ASC",
                        (conversation_id, limit),
                    )
                else:
                    cursor = await db.execute(
                        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
                        (conversation_id,),
                    )
                rows = await cursor.fetchall()
                return [
                    MessageRow(
                        id=row["id"],
                        conversation_id=row["conversation_id"],
                        role=row["role"],
                        content=row["content"],
                        created_at=row["created_at"],
                    )
                    for row in rows
                ]

    async def add_file(
        self,
        file_id: str,
        filename: str,
        size: int,
        content_type: str,
        storage_path: str,
    ) -> FileRow:
        """Add a file record (not yet linked to a message)."""
        with trace_span("db.add_file", attributes={"file_id": file_id, "filename": filename}):
            now = datetime.now(UTC).isoformat()
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    "INSERT INTO files (id, message_id, filename, size, content_type, storage_path, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (file_id, None, filename, size, content_type, storage_path, now),
                )
                await db.commit()
            return FileRow(
                id=file_id,
                message_id=None,
                filename=filename,
                size=size,
                content_type=content_type,
                storage_path=storage_path,
                created_at=now,
            )

    async def link_file_to_message(self, file_id: str, message_id: str) -> None:
        """Link an uploaded file to a message."""
        with trace_span("db.link_file_to_message", attributes={"file_id": file_id, "message_id": message_id}):
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    "UPDATE files SET message_id = ? WHERE id = ?",
                    (message_id, file_id),
                )
                await db.commit()

    async def get_file(self, file_id: str) -> FileRow | None:
        """Get a file record by ID."""
        with trace_span("db.get_file", attributes={"file_id": file_id}):
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("SELECT * FROM files WHERE id = ?", (file_id,))
                row = await cursor.fetchone()
                if row is None:
                    return None
                return FileRow(
                    id=row["id"],
                    message_id=row["message_id"],
                    filename=row["filename"],
                    size=row["size"],
                    content_type=row["content_type"],
                    storage_path=row["storage_path"],
                    created_at=row["created_at"],
                )

    async def get_files_for_message(self, message_id: str) -> list[FileRow]:
        """Get all files linked to a message."""
        with trace_span("db.get_files_for_message", attributes={"message_id": message_id}):
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("SELECT * FROM files WHERE message_id = ?", (message_id,))
                rows = await cursor.fetchall()
                return [
                    FileRow(
                        id=row["id"],
                        message_id=row["message_id"],
                        filename=row["filename"],
                        size=row["size"],
                        content_type=row["content_type"],
                        storage_path=row["storage_path"],
                        created_at=row["created_at"],
                    )
                    for row in rows
                ]
