"""FastAPI server for Claude Code Web UI with OpenTelemetry tracing."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from config import Settings
from logging_config import setup_logging
from tracing import configure_tracing

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application with OTel instrumentation."""
    settings = settings or Settings()

    setup_logging(app_name=settings.app_name, verbose=settings.debug)
    provider = configure_tracing(app_name=settings.app_name)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        provider.shutdown()

    application = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

    @application.get("/health")
    async def health() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "healthy"}

    FastAPIInstrumentor.instrument_app(application)

    return application


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="0.0.0.0", port=8080, reload=True)  # nosec B104
