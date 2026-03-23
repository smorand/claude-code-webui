# Claude Code Web UI

## Overview

Web interface for interacting with Claude Code CLI. Features MCP channel server (sole communication channel with Claude Code), chat UI (htmx + WebSocket), file upload, SQLite conversation persistence, and optional Google OAuth2 authentication.

**Tech Stack:** Python 3.13, FastAPI, Typer, MCP SDK, Ruff, mypy, pytest, OpenTelemetry, pydantic-settings, aiosqlite, authlib, htmx, Jinja2

## Key Commands

```bash
make install            # Install binary to ~/.local/bin with config dirs
make sync               # Install dependencies (development)
make run ARGS='serve'   # Start the web UI server
make run ARGS='channel' # Start the MCP channel server (for manual testing)
make check              # Full quality gate (lint, format, typecheck, security, tests+coverage)
```

## File Locations

- Launcher: `~/.local/bin/claude-webui` (from `bin/claude-webui`)
- Backend: `~/.local/bin/claude-code-webui`
- Config: `~/.config/ccwebui/.env` and `~/.config/ccwebui/oauth2.yaml`
- TLS: `~/.config/ccwebui/tls/`
- Database: `~/.local/share/ccwebui/ccwebui.db`
- Logs: `~/.cache/ccwebui/logs/`
- Uploads: `~/Downloads/`
- Channel state: `~/.claude/channels/webui/`

## Project Structure

- `src/claude_code_webui.py` : CLI entry point (Typer app with serve and channel commands)
- `src/api.py` : FastAPI server with OTel, routes, lifespan (DB init, upload dir, conditional auth)
- `src/auth.py` : OAuth2 authentication (GCP, login/callback/logout, session middleware, get_current_user dependency)
- `src/config.py` : Settings via pydantic-settings (CCWEBUI_ prefix, OAuth2 config with validation)
- `src/database.py` : SQLite database layer (aiosqlite, WAL mode, repository pattern, users table)
- `src/chat.py` : WebSocket chat handler (/ws/chat)
- `src/channel.py` : MCP channel server (stdio transport, reply/edit_message tools, channel protocol)
- `src/channel_bridge.py` : Shared state bridge between MCP server and FastAPI (clients, broadcast, SQLite persistence)
- `src/file_upload.py` : File upload endpoint (POST /api/files/upload)
- `src/logging_config.py` : Logging setup with rich + file output
- `src/tracing.py` : OpenTelemetry tracing with JSONL export
- `src/templates/index.html` : Chat frontend (htmx + Jinja2)
- `src/templates/partials/` : htmx partial templates
- `.mcp.json` : MCP server configuration for Claude Code discovery
- `tests/` : Unit tests
- `tests/functional/` : Integration tests (API, WebSocket, file upload, channel, auth)

## Conventions

- Entry point in `src/claude_code_webui.py` contains only CLI wiring
- Business logic in separate modules within `src/`
- Use `@dataclass(frozen=True)` for value objects
- All async operations use asyncio patterns
- Logging with `%` formatting, not f-strings
- OTel traces to `<app>-otel.log`, app logs to `<app>.log`
- MCP server process must never write to stdout except MCP protocol messages
- Channel state stored in `~/.claude/channels/{channel_name}/`
- WebSocket handlers in `chat.py`, file operations in `file_upload.py`, database access in `database.py`
- Frontend uses htmx templates in `src/templates/`. No inline SQL outside `database.py`
- Auth dependency `get_current_user` must be applied to all protected routes when OAuth2 is enabled
- OAuth2 is toggled via `oauth2_enabled` setting (default: False); when disabled, no auth middleware is applied
- OAuth2 redirect URI is computed dynamically from request origin, validated against `oauth2_allowed_origins`
- TLS is configured via `ssl_certfile`/`ssl_keyfile` in oauth2.yaml; required for HTTPS origins
- htmx requests use `HX-Redirect` header for auth redirects (not 302)

## Process

- Every modification must be committed and pushed to remote
- Every modification must include docs updates (CLAUDE.md + .agent_docs and README.md + docs)

## Quality Gate

Run `make check` before every commit. It runs: lint, format-check, typecheck, security, test-cov (>= 80% coverage).

## Auto-Evaluation Checklist

Before considering any task complete:
- [ ] `make check` passes
- [ ] No sync blocking calls in async code
- [ ] All external calls traced with OpenTelemetry
- [ ] No forbidden practices (bare except, print, mutable defaults, .format(), assert)
- [ ] Config via Settings class, not os.environ
- [ ] Dependencies injected, not created inline
- [ ] Test coverage >= 80%
- [ ] Changes committed and pushed

## Coding Standards

This project follows the `python` skill. Reload it for full coding standards reference.

## Documentation Index

- `.agent_docs/python.md` : Python coding standards and conventions
- `.agent_docs/makefile.md` : Detailed Makefile documentation
