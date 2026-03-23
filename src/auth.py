"""OAuth2 authentication with Google (GCP) for the FastAPI application."""

from __future__ import annotations

import logging
import secrets
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from starlette.requests import Request  # noqa: TC002

from tracing import trace_span

_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

if TYPE_CHECKING:
    from config import Settings
    from database import Database

logger = logging.getLogger(__name__)

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"  # nosec B105
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
_OAUTH2_SCOPES = "openid email profile"
_CALLBACK_PATH = "/auth/callback"
_HTTP_OK = 200


def _resolve_redirect_uri(request: Request, allowed_origins: list[str]) -> str:
    """Build the OAuth2 redirect URI from the incoming request origin.

    Validates that the request origin is in the allowed list.
    Raises HTTPException 403 if the origin is not allowed.
    """
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.url.netloc)
    origin = f"{scheme}://{host}"

    if origin not in allowed_origins:
        logger.warning("Origin not in allowed list: %s", origin)
        raise HTTPException(status_code=403, detail=f"Origin not allowed: {origin}")

    return f"{origin}{_CALLBACK_PATH}"


async def get_current_user(request: Request) -> dict[str, Any]:
    """FastAPI dependency that checks session authentication.

    Returns user data dict if authenticated, otherwise raises or redirects.
    """
    session = request.session
    if session.get("authenticated"):
        db: Database = request.app.state.db
        user = await db.get_user(session["user_email"])
        if user is not None:
            return {"email": user.email, "name": user.name, "picture": user.picture}

    is_htmx = request.headers.get("hx-request") == "true"
    accepts_html = "text/html" in request.headers.get("accept", "")

    if is_htmx:
        raise HTTPException(status_code=401, headers={"HX-Redirect": "/auth/login"})

    if accepts_html:
        raise HTTPException(status_code=302, headers={"Location": "/auth/login"})

    raise HTTPException(status_code=401, detail="Not authenticated")


async def _exchange_code_for_token(client: AsyncOAuth2Client, code: str) -> str:
    """Exchange authorization code for access token. Raises HTTPException on failure."""
    try:
        token = await client.fetch_token(
            _GOOGLE_TOKEN_URL,
            code=code,
            grant_type="authorization_code",
        )
    except Exception:
        logger.exception("Token exchange failed")
        raise HTTPException(status_code=403, detail="Token exchange failed")  # noqa: B904

    access_token: str = token.get("access_token", "")
    if not access_token:
        raise HTTPException(status_code=403, detail="No access token received")
    return access_token


async def _fetch_google_userinfo(access_token: str) -> dict[str, Any]:
    """Fetch user profile from Google userinfo endpoint. Raises HTTPException on failure."""
    async with httpx.AsyncClient() as http_client:
        resp = await http_client.get(
            _GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if resp.status_code != _HTTP_OK:
        raise HTTPException(status_code=403, detail="Failed to fetch user info")
    result: dict[str, Any] = resp.json()
    return result


def _is_email_allowed(email: str, allowed_emails: list[str]) -> bool:
    """Check whether the email is in the allowed list."""
    if not allowed_emails:
        return True
    return email in allowed_emails


def create_auth_router(settings: Settings, db: Database) -> APIRouter:
    """Create the OAuth2 authentication router."""
    router = APIRouter(prefix="/auth", tags=["auth"])

    def _build_oauth_client(redirect_uri: str) -> AsyncOAuth2Client:
        return AsyncOAuth2Client(
            client_id=settings.oauth2_client_id,
            client_secret=settings.oauth2_client_secret,
            redirect_uri=redirect_uri,
            scope=_OAUTH2_SCOPES,
        )

    @router.get("/login")
    async def login(request: Request) -> RedirectResponse:
        """Redirect to Google OAuth2 consent screen."""
        with trace_span("auth.login"):
            redirect_uri = _resolve_redirect_uri(request, settings.oauth2_allowed_origins)
            state = secrets.token_urlsafe(32)
            request.session["oauth2_state"] = state
            request.session["oauth2_redirect_uri"] = redirect_uri

            client = _build_oauth_client(redirect_uri)
            uri, _ = client.create_authorization_url(
                _GOOGLE_AUTH_URL,
                state=state,
            )
            return RedirectResponse(url=uri, status_code=302)

    @router.get("/callback")
    async def callback(request: Request, code: str, state: str) -> Response:
        """Handle Google OAuth2 callback with authorization code exchange."""
        with trace_span("auth.callback"):
            stored_state = request.session.get("oauth2_state")
            if not stored_state or stored_state != state:
                logger.warning("OAuth2 state mismatch")
                raise HTTPException(status_code=403, detail="Invalid state parameter")

            redirect_uri = request.session.get("oauth2_redirect_uri", "")
            client = _build_oauth_client(redirect_uri)
            access_token = await _exchange_code_for_token(client, code)
            userinfo = await _fetch_google_userinfo(access_token)

            email = userinfo.get("email", "")
            name = userinfo.get("name", "")
            picture = userinfo.get("picture")

            if not _is_email_allowed(email, settings.oauth2_allowed_emails):
                logger.warning("Email not in allowed list: %s", email)
                return _templates.TemplateResponse(
                    request,
                    "unauthorized.html",
                    {"email": email},
                    status_code=403,
                )
            await db.upsert_user(email=email, name=name, picture=picture)

            request.session["user_email"] = email
            request.session["authenticated"] = True
            request.session.pop("oauth2_state", None)

            logger.info("User authenticated: %s", email)
            return RedirectResponse(url="/", status_code=302)

    @router.get("/logout")
    async def logout(request: Request) -> Response:
        """Clear session and redirect to login."""
        with trace_span("auth.logout"):
            request.session.clear()
            is_htmx = request.headers.get("hx-request") == "true"
            if is_htmx:
                return Response(
                    status_code=200,
                    headers={"HX-Redirect": "/auth/login"},
                )
            return RedirectResponse(url="/auth/login", status_code=302)

    @router.get("/me")
    async def me(request: Request) -> JSONResponse:
        """Return the current user's profile from SQLite."""
        with trace_span("auth.me"):
            user_data = await get_current_user(request)
            return JSONResponse(content=user_data)

    return router
