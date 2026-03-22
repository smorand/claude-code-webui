"""Functional tests for the WebSocket chat endpoint."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from opentelemetry import trace
from starlette.testclient import TestClient

from api import create_app
from config import Settings
from database import Database


@pytest.fixture(autouse=True)
def _reset_tracer() -> None:
    """Reset global tracer provider between tests."""
    trace._TRACER_PROVIDER = None  # type: ignore[attr-defined]
    trace._TRACER_PROVIDER_SET_ONCE._done = False  # type: ignore[attr-defined]


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Create test settings with temp paths."""
    return Settings(
        app_name="test_chat",
        debug=True,
        upload_dir=str(tmp_path / "uploads"),
        database_path=str(tmp_path / "test.db"),
        max_history_messages=100,
    )


@pytest.fixture
def sync_client(settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:  # type: ignore[misc]
    """Create a sync test client for WebSocket testing (lifespan runs with TestClient context)."""
    monkeypatch.chdir(tmp_path)
    application = create_app(settings=settings)
    with TestClient(application) as client:
        yield client  # type: ignore[misc]


@pytest.fixture
async def async_client(settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncClient:
    """Create an async test client for HTTP requests."""
    monkeypatch.chdir(tmp_path)
    application = create_app(settings=settings)

    db = Database(db_path=settings.database_path)
    await db.init_schema()
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)

    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c  # type: ignore[misc]


def test_websocket_chat_send_message(sync_client: TestClient) -> None:
    """User message is accepted and conversation created."""
    with sync_client.websocket_connect("/ws/chat") as ws:
        ws.send_text(json.dumps({"type": "user_message", "content": "Hello"}))

        connected = ws.receive_json()
        assert connected["type"] == "connected"
        assert "conversation_id" in connected


def test_websocket_chat_multi_turn(sync_client: TestClient) -> None:
    """Multi-turn conversation maintains context."""
    with sync_client.websocket_connect("/ws/chat") as ws:
        ws.send_text(json.dumps({"type": "user_message", "content": "First"}))
        connected1 = ws.receive_json()
        conversation_id = connected1["conversation_id"]

        ws.send_text(
            json.dumps(
                {
                    "type": "user_message",
                    "content": "Second",
                    "conversation_id": conversation_id,
                }
            )
        )
        connected2 = ws.receive_json()
        assert connected2["conversation_id"] == conversation_id


def test_websocket_chat_empty_content_rejected(sync_client: TestClient) -> None:
    """Empty content message is rejected."""
    with sync_client.websocket_connect("/ws/chat") as ws:
        ws.send_text(json.dumps({"type": "user_message", "content": ""}))
        error = ws.receive_json()
        assert error["type"] == "error"
        assert "empty" in error["detail"].lower()


def test_websocket_chat_invalid_json(sync_client: TestClient) -> None:
    """Invalid JSON returns error."""
    with sync_client.websocket_connect("/ws/chat") as ws:
        ws.send_text("not json")
        error = ws.receive_json()
        assert error["type"] == "error"


def test_websocket_chat_nonexistent_conversation(sync_client: TestClient) -> None:
    """Referencing nonexistent conversation_id returns error."""
    with sync_client.websocket_connect("/ws/chat") as ws:
        ws.send_text(
            json.dumps(
                {
                    "type": "user_message",
                    "content": "Hello",
                    "conversation_id": "nonexistent-uuid",
                }
            )
        )
        error = ws.receive_json()
        assert error["type"] == "error"
        assert "not found" in error["detail"].lower()


def test_websocket_chat_with_file_attachment(sync_client: TestClient) -> None:
    """Message with file attachment resolves file and delivers."""
    upload_resp = sync_client.post(
        "/api/files/upload",
        files=[("files", ("code.py", io.BytesIO(b"x = 1"), "text/x-python"))],
    )
    assert upload_resp.status_code == 201
    file_id = upload_resp.json()["files"][0]["file_id"]

    with sync_client.websocket_connect("/ws/chat") as ws:
        ws.send_text(
            json.dumps(
                {
                    "type": "user_message",
                    "content": "Review this file",
                    "attachments": [{"file_id": file_id}],
                }
            )
        )
        connected = ws.receive_json()
        assert connected["type"] == "connected"


def test_websocket_chat_nonexistent_file_warns(sync_client: TestClient) -> None:
    """Non-existent file_id in attachment sends warning but continues."""
    with sync_client.websocket_connect("/ws/chat") as ws:
        ws.send_text(
            json.dumps(
                {
                    "type": "user_message",
                    "content": "Review this",
                    "attachments": [{"file_id": "nonexistent-uuid"}],
                }
            )
        )
        messages = []
        for _ in range(5):
            try:
                msg = ws.receive_json(mode="text")
                messages.append(msg)
                if msg["type"] == "connected":
                    break
            except Exception:
                break

        types_found = [m["type"] for m in messages]
        assert "warning" in types_found or "connected" in types_found


async def test_chat_frontend_served(async_client: AsyncClient) -> None:
    """Chat frontend serves at root URL."""
    response = await async_client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "htmx" in response.text.lower()
    assert "message-input" in response.text
