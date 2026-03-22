"""Integration tests for the FastAPI server with OTel tracing."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient
from opentelemetry import trace

from api import create_app
from config import Settings

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _reset_tracer() -> None:
    """Reset global tracer provider between tests."""
    trace._TRACER_PROVIDER = None  # type: ignore[attr-defined]
    trace._TRACER_PROVIDER_SET_ONCE._done = False  # type: ignore[attr-defined]


@pytest.fixture
def otel_dir(tmp_path: Path) -> Path:
    """Provide a temp dir for OTel logs."""
    return tmp_path


@pytest.fixture
def settings(otel_dir: Path) -> Settings:
    """Create test settings pointing OTel logs to tmp dir."""
    return Settings(app_name="test_api", debug=True)


@pytest.fixture
async def client(settings: Settings, otel_dir: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncClient:
    """Create an async test client for the API."""
    monkeypatch.chdir(otel_dir)
    application = create_app(settings=settings)
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c  # type: ignore[misc]


async def test_health_endpoint(client: AsyncClient) -> None:
    """Test the health check endpoint responds correctly."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
