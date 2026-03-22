"""FastAPI server for Claude Code Web UI with OpenTelemetry tracing."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from starlette.requests import Request  # noqa: TC002 -- needed at runtime for FastAPI annotation resolution

from channel import StubChannel
from chat import create_chat_router
from config import Settings
from database import Database
from file_upload import create_file_upload_router
from logging_config import setup_logging
from tracing import configure_tracing

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application with OTel instrumentation."""
    settings = settings or Settings()

    setup_logging(app_name=settings.app_name, verbose=settings.debug)
    provider = configure_tracing(app_name=settings.app_name)

    db = Database(db_path=settings.database_path)
    channel = StubChannel()
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

    application.include_router(create_file_upload_router(settings, db))
    application.include_router(create_chat_router(settings, db, channel))

    FastAPIInstrumentor.instrument_app(application)

    return application


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="0.0.0.0", port=8080, reload=True)  # nosec B104
