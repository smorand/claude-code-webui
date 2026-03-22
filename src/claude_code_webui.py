"""CLI entry point for the claude_code_webui application."""

import asyncio
import logging
from pathlib import Path
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
    log_path = Path(settings.log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    setup_logging(app_name=settings.app_name, verbose=verbose, quiet=quiet, log_dir=log_path)
    configure_tracing(app_name=settings.app_name, log_dir=log_path)


@app.command()
def serve(
    host: Annotated[str, typer.Option("--host", "-h", help="Host to bind to")] = "0.0.0.0",  # nosec B104
    port: Annotated[int, typer.Option("--port", "-p", help="Port to bind to")] = 8080,
    reload: Annotated[bool, typer.Option("--reload", help="Enable auto reload")] = False,
) -> None:
    """Start the web UI server."""
    logger.info("Starting Claude Code Web UI on %s:%s", host, port)
    uvicorn.run("api:app", host=host, port=port, reload=reload)


@app.command()
def channel(
    port: Annotated[int, typer.Option("--port", "-p", help="HTTP server port")] = 8080,
) -> None:
    """Start the MCP channel server with HTTP/WebSocket server.

    Runs the MCP channel over stdio and the HTTP/WebSocket server concurrently.
    The MCP server communicates with Claude Code via stdin/stdout.
    The HTTP server provides WebSocket and file endpoints for the browser.
    """
    _run_channel(port)


def _run_channel(port: int) -> None:
    """Run the MCP channel and HTTP server. Separated for import isolation."""
    from api import create_app  # noqa: PLC0415 -- deferred to avoid circular import
    from channel import run_channel_server  # noqa: PLC0415
    from channel_bridge import ChannelBridge  # noqa: PLC0415
    from database import Database  # noqa: PLC0415

    settings = Settings(port=port)
    log_path = Path(settings.log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    setup_logging(
        app_name=settings.app_name,
        verbose=settings.debug,
        log_dir=log_path,
    )

    db = Database(db_path=settings.database_path)
    bridge = ChannelBridge(db=db, channel_name=settings.channel_name)

    application = create_app(settings=settings, bridge=bridge)

    config = uvicorn.Config(
        application,
        host=settings.host,
        port=settings.port,
        log_level="info",
    )
    http_server = uvicorn.Server(config)

    async def run_both() -> None:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(run_channel_server(bridge, settings))
            tg.create_task(http_server.serve())

    asyncio.run(run_both())


if __name__ == "__main__":
    app()
