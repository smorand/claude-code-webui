"""CLI entry point for the claude_code_webui application."""

import logging
from typing import Annotated

import typer
import uvicorn

from config import Settings
from logging_config import setup_logging
from tracing import configure_tracing

app = typer.Typer()
logger = logging.getLogger(__name__)


@app.callback()
def main(
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable debug logging"),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Only show warnings and errors"),
    ] = False,
) -> None:
    """Claude Code Web UI: a web interface for Claude Code CLI."""
    settings = Settings()
    setup_logging(app_name=settings.app_name, verbose=verbose, quiet=quiet)
    configure_tracing(app_name=settings.app_name)


@app.command()
def serve(
    host: Annotated[str, typer.Option("--host", "-h", help="Host to bind to")] = "0.0.0.0",  # nosec B104
    port: Annotated[int, typer.Option("--port", "-p", help="Port to bind to")] = 8080,
    reload: Annotated[bool, typer.Option("--reload", help="Enable auto reload")] = False,
) -> None:
    """Start the web UI server."""
    logger.info("Starting Claude Code Web UI on %s:%s", host, port)
    uvicorn.run("api:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
