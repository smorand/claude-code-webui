"""Functional tests for the file upload endpoint."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from opentelemetry import trace

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
        app_name="test_upload",
        debug=True,
        upload_dir=str(tmp_path / "uploads"),
        database_path=str(tmp_path / "test.db"),
        max_upload_size_mb=1,
    )


@pytest.fixture
async def client(settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncClient:
    """Create an async test client with DB initialized."""
    monkeypatch.chdir(tmp_path)
    # Manually init DB and upload dir since ASGITransport doesn't trigger lifespan
    db = Database(db_path=settings.database_path)
    await db.init_schema()
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)

    application = create_app(settings=settings)
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c  # type: ignore[misc]


async def test_upload_file_success(client: AsyncClient, settings: Settings) -> None:
    """E2E-NEW-003: Upload a valid file successfully."""
    content = b"print('hello world')"
    response = await client.post(
        "/api/files/upload",
        files=[("files", ("test.py", io.BytesIO(content), "text/x-python"))],
    )
    assert response.status_code == 201
    data = response.json()
    assert len(data["files"]) == 1
    assert data["files"][0]["filename"] == "test.py"
    assert data["files"][0]["size"] == len(content)
    assert data["files"][0]["content_type"] == "text/x-python"
    assert "file_id" in data["files"][0]

    file_path = Path(settings.upload_dir) / data["files"][0]["file_id"] / "test.py"
    assert file_path.exists()


async def test_upload_oversized_file_rejected(client: AsyncClient) -> None:
    """E2E-NEW-004: Upload file exceeding max size is rejected."""
    large_content = b"x" * (2 * 1024 * 1024)  # 2 MB, limit is 1 MB
    response = await client.post(
        "/api/files/upload",
        files=[("files", ("big.txt", io.BytesIO(large_content), "text/plain"))],
    )
    assert response.status_code == 422
    assert "size" in response.json()["detail"].lower()


async def test_upload_disallowed_extension_rejected(client: AsyncClient) -> None:
    """E2E-NEW-005: Upload file with disallowed extension is rejected."""
    response = await client.post(
        "/api/files/upload",
        files=[("files", ("malware.exe", io.BytesIO(b"bad"), "application/octet-stream"))],
    )
    assert response.status_code == 422
    assert "not allowed" in response.json()["detail"].lower()


async def test_upload_empty_file_rejected(client: AsyncClient) -> None:
    """E2E-NEW-013: Upload empty file is rejected."""
    response = await client.post(
        "/api/files/upload",
        files=[("files", ("empty.txt", io.BytesIO(b""), "text/plain"))],
    )
    assert response.status_code == 422
    assert "empty" in response.json()["detail"].lower()


async def test_upload_multiple_files(client: AsyncClient) -> None:
    """E2E-NEW-014: Upload multiple files in single request."""
    response = await client.post(
        "/api/files/upload",
        files=[
            ("files", ("file1.txt", io.BytesIO(b"content1"), "text/plain")),
            ("files", ("file2.py", io.BytesIO(b"content2"), "text/x-python")),
        ],
    )
    assert response.status_code == 201
    data = response.json()
    assert len(data["files"]) == 2
    file_ids = [f["file_id"] for f in data["files"]]
    assert file_ids[0] != file_ids[1]
