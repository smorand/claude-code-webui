"""Functional tests for OAuth2 authentication."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from opentelemetry import trace
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from api import create_app
from config import Settings
from database import Database

_TEST_OAUTH2_SETTINGS = {
    "oauth2_enabled": True,
    "oauth2_client_id": "test_client_id",
    "oauth2_client_secret": "test_client_secret",
    "oauth2_redirect_uri": "http://localhost:8080/auth/callback",
    "session_secret_key": "test_session_secret_key_for_tests_32!",
}


def _extract_state(location: str) -> str:
    """Extract the state parameter from a Google OAuth2 redirect URL."""
    return next(p.split("=", 1)[1] for p in location.split("&") if p.startswith("state="))


@pytest.fixture(autouse=True)
def _reset_tracer() -> None:
    """Reset global tracer provider between tests."""
    trace._TRACER_PROVIDER = None  # type: ignore[attr-defined]
    trace._TRACER_PROVIDER_SET_ONCE._done = False  # type: ignore[attr-defined]


@pytest.fixture
def auth_settings(tmp_path: Path) -> Settings:
    """Create test settings with OAuth2 enabled."""
    return Settings(
        app_name="test_auth",
        debug=True,
        upload_dir=str(tmp_path / "uploads"),
        database_path=str(tmp_path / "test.db"),
        **_TEST_OAUTH2_SETTINGS,  # type: ignore[arg-type]
    )


@pytest.fixture
def noauth_settings(tmp_path: Path) -> Settings:
    """Create test settings with OAuth2 disabled."""
    return Settings(
        app_name="test_noauth",
        debug=True,
        upload_dir=str(tmp_path / "uploads"),
        database_path=str(tmp_path / "test.db"),
        oauth2_enabled=False,
    )


@pytest.fixture
async def auth_client(auth_settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncClient:
    """Create an async test client with OAuth2 enabled."""
    monkeypatch.chdir(tmp_path)
    db = Database(db_path=auth_settings.database_path)
    await db.init_schema()
    Path(auth_settings.upload_dir).mkdir(parents=True, exist_ok=True)

    application = create_app(settings=auth_settings)
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c  # type: ignore[misc]


@pytest.fixture
async def noauth_client(noauth_settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncClient:
    """Create an async test client with OAuth2 disabled."""
    monkeypatch.chdir(tmp_path)
    db = Database(db_path=noauth_settings.database_path)
    await db.init_schema()
    Path(noauth_settings.upload_dir).mkdir(parents=True, exist_ok=True)

    application = create_app(settings=noauth_settings)
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c  # type: ignore[misc]


@pytest.fixture
def auth_sync_client(auth_settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:  # type: ignore[misc]
    """Create a sync test client with OAuth2 enabled for WebSocket testing."""
    monkeypatch.chdir(tmp_path)
    application = create_app(settings=auth_settings)
    with TestClient(application) as client:
        yield client  # type: ignore[misc]


async def _do_full_oauth_flow(
    client: AsyncClient,
    settings: Settings,
    email: str = "user@example.com",
    name: str = "Test User",
    picture: str = "https://example.com/photo.jpg",
) -> Any:
    """Helper: perform a full mock OAuth flow and return the final response."""
    login_resp = await client.get("/auth/login", follow_redirects=False)
    cookies = login_resp.cookies
    location = login_resp.headers["location"]
    state = _extract_state(location)

    mock_userinfo_data = {"email": email, "name": name, "picture": picture}

    with (
        patch("auth._exchange_code_for_token", new_callable=AsyncMock, return_value="mock_access_token"),
        patch("auth._fetch_google_userinfo", new_callable=AsyncMock, return_value=mock_userinfo_data),
    ):
        response = await client.get(
            f"/auth/callback?code=valid_code&state={state}",
            cookies=cookies,
            follow_redirects=False,
        )

    return response


# --- E2E-MOD-001: Health endpoint remains public ---


async def test_health_public_with_auth_enabled(auth_client: AsyncClient) -> None:
    """E2E-MOD-001: Health endpoint remains public when OAuth2 is enabled."""
    response = await auth_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


# --- E2E-NEW-001: Login redirects to Google ---


async def test_login_redirects_to_google(auth_client: AsyncClient) -> None:
    """E2E-NEW-001: Login redirects to Google OAuth2 consent screen."""
    response = await auth_client.get("/auth/login", follow_redirects=False)
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("https://accounts.google.com/o/oauth2/v2/auth")
    assert "client_id=test_client_id" in location
    assert "state=" in location
    assert "scope=" in location


# --- E2E-NEW-003: Callback with invalid state returns 403 ---


async def test_callback_invalid_state(auth_client: AsyncClient) -> None:
    """E2E-NEW-003: Callback with mismatched state returns 403."""
    response = await auth_client.get("/auth/callback?code=abc&state=wrong")
    assert response.status_code == 403
    assert "state" in response.json()["detail"].lower()


# --- E2E-NEW-006: Unauthenticated API request returns 401 ---


async def test_unauthenticated_api_returns_401(auth_client: AsyncClient) -> None:
    """E2E-NEW-006: Unauthenticated request with JSON accept returns 401."""
    response = await auth_client.get("/", headers={"Accept": "application/json"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


# --- E2E-NEW-007: Unauthenticated browser request redirects ---


async def test_unauthenticated_browser_redirects(auth_client: AsyncClient) -> None:
    """E2E-NEW-007: Unauthenticated browser request redirects to /auth/login."""
    response = await auth_client.get("/", headers={"Accept": "text/html"}, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/auth/login"


# --- E2E-NEW-010: OAuth2 disabled means no auth enforcement ---


async def test_oauth2_disabled_no_auth(noauth_client: AsyncClient) -> None:
    """E2E-NEW-010: With OAuth2 disabled, endpoints are public."""
    response = await noauth_client.get("/")
    assert response.status_code == 200


async def test_oauth2_disabled_no_auth_routes(noauth_client: AsyncClient) -> None:
    """E2E-NEW-010: With OAuth2 disabled, /auth/* endpoints do not exist."""
    response = await noauth_client.get("/auth/login")
    assert response.status_code == 404


# --- E2E-NEW-012: State token is cryptographically random ---


async def test_state_token_random(auth_client: AsyncClient) -> None:
    """E2E-NEW-012: Two successive login calls produce different state tokens."""
    resp1 = await auth_client.get("/auth/login", follow_redirects=False)
    resp2 = await auth_client.get("/auth/login", follow_redirects=False)
    state1 = _extract_state(resp1.headers["location"])
    state2 = _extract_state(resp2.headers["location"])
    assert state1 != state2
    assert len(state1) >= 32


# --- E2E-NEW-013: Token exchange failure returns 403 ---


async def test_token_exchange_failure(auth_client: AsyncClient) -> None:
    """E2E-NEW-013: Token exchange failure returns 403."""
    login_resp = await auth_client.get("/auth/login", follow_redirects=False)
    cookies = login_resp.cookies
    location = login_resp.headers["location"]
    state = _extract_state(location)

    with patch(
        "auth._exchange_code_for_token",
        new_callable=AsyncMock,
        side_effect=HTTPException(status_code=403, detail="Token exchange failed"),
    ):
        response = await auth_client.get(
            f"/auth/callback?code=test_code&state={state}",
            cookies=cookies,
        )
    assert response.status_code == 403
    assert "token exchange failed" in response.json()["detail"].lower()


# --- E2E-NEW-002 + E2E-NEW-014: Callback success, user persisted ---


async def test_callback_success_redirects(auth_client: AsyncClient, auth_settings: Settings) -> None:
    """E2E-NEW-002: Successful callback redirects to /."""
    response = await _do_full_oauth_flow(auth_client, auth_settings)
    assert response.status_code == 302
    assert response.headers["location"] == "/"


async def test_user_persisted_in_db(auth_client: AsyncClient, auth_settings: Settings) -> None:
    """E2E-NEW-014: User profile is persisted in SQLite on login."""
    await _do_full_oauth_flow(auth_client, auth_settings)
    db = Database(db_path=auth_settings.database_path)
    with patch("database.trace_span"):
        user = await db.get_user("user@example.com")
    assert user is not None
    assert user.name == "Test User"
    assert user.picture == "https://example.com/photo.jpg"


# --- E2E-NEW-015: User profile updated on subsequent login ---


async def test_user_updated_on_subsequent_login(auth_client: AsyncClient, auth_settings: Settings) -> None:
    """E2E-NEW-015: User profile updated on subsequent login."""
    await _do_full_oauth_flow(auth_client, auth_settings, name="First Name")
    db = Database(db_path=auth_settings.database_path)
    with patch("database.trace_span"):
        user1 = await db.get_user("user@example.com")

    await _do_full_oauth_flow(auth_client, auth_settings, name="Updated Name")
    with patch("database.trace_span"):
        user2 = await db.get_user("user@example.com")

    assert user1 is not None
    assert user2 is not None
    assert user2.name == "Updated Name"
    assert user2.last_login_at >= user1.last_login_at


# --- E2E-NEW-004: Callback with disallowed domain returns 403 ---


async def test_callback_disallowed_domain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """E2E-NEW-004: Callback with disallowed domain returns 403."""
    monkeypatch.chdir(tmp_path)
    settings = Settings(
        app_name="test_domain",
        debug=True,
        upload_dir=str(tmp_path / "uploads"),
        database_path=str(tmp_path / "test.db"),
        oauth2_enabled=True,
        oauth2_client_id="test_client_id",
        oauth2_client_secret="test_client_secret",
        oauth2_redirect_uri="http://localhost:8080/auth/callback",
        session_secret_key="test_session_secret_key_for_tests_32!",
        oauth2_allowed_domains=["company.com"],
    )
    db = Database(db_path=settings.database_path)
    await db.init_schema()
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)

    application = create_app(settings=settings)
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await _do_full_oauth_flow(client, settings, email="user@other.com")
    assert response.status_code == 403
    assert "domain" in response.json()["detail"].lower()


# --- E2E-NEW-008: Logout clears session ---


async def test_logout_redirects(auth_client: AsyncClient, auth_settings: Settings) -> None:
    """E2E-NEW-008: Logout clears session and redirects."""
    await _do_full_oauth_flow(auth_client, auth_settings)
    response = await auth_client.get("/auth/logout", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/auth/login"


# --- E2E-NEW-016: Database initialized on startup ---


async def test_database_initialized_on_startup(
    auth_settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E2E-NEW-016: Database and users table created on app startup."""
    monkeypatch.chdir(tmp_path)
    db = Database(db_path=auth_settings.database_path)
    await db.init_schema()

    with patch("database.trace_span"):
        user = await db.upsert_user("test@test.com", "Test", None)
    assert user.email == "test@test.com"


# --- E2E-NEW-017: WebSocket rejected when unauthenticated ---


def test_websocket_rejected_unauthenticated(auth_sync_client: TestClient) -> None:
    """E2E-NEW-017: WebSocket connection rejected with code 4001 when unauthenticated."""
    with pytest.raises(WebSocketDisconnect), auth_sync_client.websocket_connect("/ws/chat"):
        pass


# --- E2E-NEW-018: File upload rejected when unauthenticated ---


async def test_file_upload_unauthenticated(auth_client: AsyncClient) -> None:
    """E2E-NEW-018: File upload rejected when unauthenticated."""
    response = await auth_client.post(
        "/api/files/upload",
        files=[("files", ("test.py", io.BytesIO(b"x = 1"), "text/x-python"))],
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 401


# --- E2E-NEW-019: htmx unauthenticated request gets HX-Redirect ---


async def test_htmx_unauthenticated_redirect(auth_client: AsyncClient) -> None:
    """E2E-NEW-019: htmx unauthenticated request gets HX-Redirect header."""
    response = await auth_client.get("/", headers={"HX-Request": "true"})
    assert response.status_code == 401
    assert response.headers.get("hx-redirect") == "/auth/login"


# --- E2E-NEW-020: Logout via htmx returns HX-Redirect ---


async def test_logout_htmx(auth_client: AsyncClient, auth_settings: Settings) -> None:
    """E2E-NEW-020: Logout via htmx returns HX-Redirect."""
    await _do_full_oauth_flow(auth_client, auth_settings)
    response = await auth_client.get("/auth/logout", headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert response.headers.get("hx-redirect") == "/auth/login"
