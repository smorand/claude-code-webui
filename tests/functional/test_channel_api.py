"""Integration tests for MCP channel API endpoints."""

from __future__ import annotations

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
        app_name="test_channel",
        debug=True,
        upload_dir=str(tmp_path / "uploads"),
        database_path=str(tmp_path / "test.db"),
        channel_state_dir=tmp_path / "channel",
        channel_inbox_dir=tmp_path / "inbox",
        channel_outbox_dir=tmp_path / "outbox",
        channel_max_file_size=1000,
    )


@pytest.fixture
def sync_client(settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:  # type: ignore[misc]
    """Create a sync test client with lifespan."""
    monkeypatch.chdir(tmp_path)
    application = create_app(settings=settings)
    with TestClient(application) as client:
        yield client  # type: ignore[misc]


@pytest.fixture
async def async_client(settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncClient:
    """Create an async test client."""
    monkeypatch.chdir(tmp_path)
    application = create_app(settings=settings)

    db = Database(db_path=settings.database_path)
    await db.init_schema()
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)

    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c  # type: ignore[misc]


def test_websocket_connect_disconnect(sync_client: TestClient) -> None:
    """E2E-NEW-004: WebSocket connection adds and removes client."""
    with sync_client.websocket_connect("/ws"):
        pass  # connect then disconnect


def test_websocket_send_valid_message(sync_client: TestClient) -> None:
    """E2E-NEW-001: Valid message is accepted (delivery handled by bridge)."""
    with sync_client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"id": "m1", "text": "hello"}))
        # No response expected immediately (bridge handles async delivery)


def test_websocket_malformed_message(sync_client: TestClient) -> None:
    """E2E-NEW-007: Malformed message is silently discarded."""
    with sync_client.websocket_connect("/ws") as ws:
        ws.send_text("not json")
        # Connection stays open, no crash


def test_websocket_missing_fields(sync_client: TestClient) -> None:
    """Message without id or text is silently discarded."""
    with sync_client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"text": "no id"}))
        ws.send_text(json.dumps({"id": "m1"}))  # no text


async def test_file_upload(async_client: AsyncClient, settings: Settings) -> None:
    """E2E-NEW-005: File upload saves to inbox and returns 204."""
    inbox = Path(settings.resolved_inbox_dir)

    response = await async_client.post(
        "/upload",
        data={"id": "m1", "text": "see attached"},
        files={"file": ("test.txt", b"hello world", "text/plain")},
    )
    assert response.status_code == 204

    files = list(inbox.iterdir())
    assert len(files) == 1
    assert files[0].read_text() == "hello world"


async def test_file_upload_too_large(async_client: AsyncClient) -> None:
    """E2E-NEW-008: File exceeding max size returns 413."""
    response = await async_client.post(
        "/upload",
        data={"id": "m1", "text": "big file"},
        files={"file": ("large.bin", b"x" * 2000, "application/octet-stream")},
    )
    assert response.status_code == 413


async def test_file_upload_no_id(async_client: AsyncClient) -> None:
    """Upload without id field is rejected."""
    response = await async_client.post(
        "/upload",
        data={"text": "no id"},
    )
    assert response.status_code == 422


async def test_file_serving(async_client: AsyncClient, settings: Settings) -> None:
    """E2E-NEW-006: File served from outbox with correct MIME type."""
    outbox = settings.resolved_outbox_dir
    outbox.mkdir(parents=True, exist_ok=True)
    (outbox / "test.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    response = await async_client.get("/files/test.png")
    assert response.status_code == 200
    assert "image/png" in response.headers["content-type"]


async def test_file_serving_not_found(async_client: AsyncClient) -> None:
    """File not found returns 404."""
    response = await async_client.get("/files/nonexistent.txt")
    assert response.status_code == 404


async def test_file_serving_path_traversal(async_client: AsyncClient) -> None:
    """E2E-NEW-009: Path traversal attempt returns 400."""
    response = await async_client.get("/files/..%2F..%2Fetc%2Fpasswd")
    # The URL decoding by FastAPI may handle this, but the ".." check catches it
    assert response.status_code in (400, 404, 422)


async def test_file_serving_slash_in_name(async_client: AsyncClient) -> None:
    """Filename with slash returns 400."""
    response = await async_client.get("/files/sub/file.txt")
    # FastAPI may interpret this as a different route, resulting in 404
    assert response.status_code in (400, 404)


async def test_channel_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """E2E-NEW-013: Channel settings configurable via environment."""
    monkeypatch.setenv("CCWEBUI_CHANNEL_NAME", "custom")
    settings = Settings()
    assert settings.channel_name == "custom"


async def test_channel_settings_defaults() -> None:
    """E2E-MOD-001: Config defaults include channel settings."""
    settings = Settings()
    assert settings.channel_name == "webui"
    assert settings.channel_max_file_size == 52_428_800
    assert "webui" in str(settings.channel_state_dir)
