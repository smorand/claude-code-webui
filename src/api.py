"""FastAPI server for Claude Code Web UI with OpenTelemetry tracing."""

from __future__ import annotations

import json
import logging
import mimetypes
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, Form, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from starlette.requests import Request  # noqa: TC002 -- needed at runtime for FastAPI annotation resolution

from channel_bridge import ChannelBridge
from chat import create_chat_router
from config import Settings
from database import Database
from file_upload import create_file_upload_router
from logging_config import setup_logging
from tracing import configure_tracing, trace_span

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _register_channel_endpoints(
    application: FastAPI,
    bridge: ChannelBridge,
    settings: Settings,
) -> None:
    """Register MCP channel WebSocket, upload, and file serving endpoints."""

    @application.websocket("/ws")
    async def websocket_channel(websocket: WebSocket) -> None:
        """WebSocket endpoint bridging browser clients to the MCP channel."""
        await websocket.accept()
        bridge.add_client(websocket)
        try:
            while True:
                raw = await websocket.receive_text()
                with trace_span("ws.inbound"):
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    msg_id = data.get("id")
                    text = data.get("text", "")
                    if not msg_id or not text:
                        continue

                    await bridge.deliver(
                        message_id=msg_id,
                        text=text,
                        chat_id=data.get("chat_id", "web"),
                    )
        except WebSocketDisconnect:
            pass
        finally:
            bridge.remove_client(websocket)

    @application.post("/upload", status_code=204)
    async def channel_upload(
        id: str = Form(...),
        text: str = Form(""),
        file: UploadFile | None = None,
    ) -> Response:
        """Upload a file and deliver via the MCP channel."""
        if not id:
            return Response(status_code=400, content="id is required")

        file_path: str | None = None
        if file and file.filename:
            with trace_span("channel.upload", attributes={"filename": file.filename}):
                content = await file.read()
                if len(content) > settings.channel_max_file_size:
                    return Response(status_code=413, content="File too large")

                inbox = settings.resolved_inbox_dir
                inbox.mkdir(parents=True, exist_ok=True)

                ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
                suffix = Path(file.filename).suffix
                dest = inbox / f"{ts}_{id}{suffix}"
                dest.write_bytes(content)
                file_path = str(dest)

        await bridge.deliver(
            message_id=id,
            text=text or (file.filename if file and file.filename else ""),
            file_path=file_path,
        )
        return Response(status_code=204)

    @application.get("/files/{filename}")
    async def serve_outbox_file(filename: str) -> Response:
        """Serve a file from the outbox directory."""
        if ".." in filename or "/" in filename:
            return Response(status_code=400, content="Invalid filename")

        file_path = settings.resolved_outbox_dir / filename
        if not file_path.exists():
            return Response(status_code=404, content="File not found")

        content_type, _ = mimetypes.guess_type(str(file_path))
        return FileResponse(
            path=str(file_path),
            media_type=content_type or "application/octet-stream",
            filename=filename,
        )


def create_app(
    settings: Settings | None = None,
    bridge: ChannelBridge | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application with OTel instrumentation.

    Args:
        settings: Application settings. Created from environment if not provided.
        bridge: Optional channel bridge for MCP integration. If not provided,
                a bridge is created for standalone HTTP mode.
    """
    settings = settings or Settings()

    # Only configure logging/tracing in standalone mode (no bridge = standalone)
    if bridge is not None:
        db = Database(db_path=settings.database_path)
        provider = configure_tracing(app_name=settings.app_name)
    else:
        setup_logging(app_name=settings.app_name, verbose=settings.debug)
        provider = configure_tracing(app_name=settings.app_name)
        db = Database(db_path=settings.database_path)
        bridge = ChannelBridge(db=db, channel_name=settings.channel_name)

    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await db.init_schema()
        upload_dir = Path(settings.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Upload directory ready: %s", upload_dir)
        yield
        provider.shutdown()

    application = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

    @application.get("/health")
    async def health() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "healthy"}

    @application.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        """Serve the chat frontend."""
        return templates.TemplateResponse(request, "index.html")

    _register_channel_endpoints(application, bridge, settings)
    application.include_router(create_file_upload_router(settings, db))
    application.include_router(create_chat_router(db, bridge))

    FastAPIInstrumentor.instrument_app(application)

    return application


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="0.0.0.0", port=8080, reload=True)  # nosec B104
