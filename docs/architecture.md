# Architecture

## Overview

Claude Code Web UI is a web application that provides a browser interface for interacting with Claude Code CLI. It is built with FastAPI for the backend and serves a web frontend.

## Components

### CLI Layer (`src/claude_code_webui.py`)
The CLI entry point uses Typer and provides the `serve` command to start the web server. It handles logging and tracing initialization.

### API Layer (`src/api.py`)
The FastAPI application serves the web UI and exposes API endpoints. It is instrumented with OpenTelemetry for observability.

### Configuration (`src/config.py`)
Application settings are managed via pydantic-settings with the `CCWEBUI_` environment variable prefix. A `.env` file is loaded automatically if present.

### Observability
- **Logging:** Rich console output + file logging to `claude-code-webui.log`
- **Tracing:** OpenTelemetry spans exported as JSONL to `claude-code-webui-otel.log`

## Deployment

The application can be deployed as a Docker container. The multi-stage Dockerfile ensures a minimal runtime image. Docker Compose is provided for local orchestration.
