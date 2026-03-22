# Claude Code Web UI

A web interface for interacting with Claude Code CLI. Features an MCP channel server as the sole communication channel with Claude Code, a real time chat UI built with htmx, file upload support, and SQLite backed conversation persistence.

## Requirements

- Python 3.13 or later
- uv (package manager)

## Installation

```bash
# Install to ~/.local/bin with config in ~/.config/ccwebui
make install
```

This creates:
- `~/.local/bin/claude-code-webui` : Binary
- `~/.config/ccwebui/.env` : Configuration file
- `~/.config/ccwebui/mcp.json` : MCP server config for Claude Code
- `~/.local/share/ccwebui/` : Database and application data

Ensure `~/.local/bin` is in your `PATH`.

## Quick Start

```bash
# Install dependencies (development)
make sync

# Start the web UI server (standalone, no Claude Code integration)
make run ARGS='serve'

# Start with auto reload for development
make run ARGS='serve --reload'
```

Open http://localhost:8080 in your browser to start chatting.

## Channel Integration

The MCP channel is the **sole communication path** between the web UI and Claude Code. There is no CLI subprocess fallback.

### How It Works

1. Claude Code spawns the MCP channel server as a subprocess
2. The server communicates with Claude Code over stdio using the MCP protocol
3. The server declares the `claude/channel` experimental capability
4. User messages from the browser are forwarded to Claude via `notifications/claude/channel`
5. Claude responds by calling the `reply` and `edit_message` tools
6. Responses are broadcast to connected browser clients via WebSocket

### Usage with Claude Code

```bash
# After make install, start Claude with the MCP config
claude --mcp-config ~/.config/ccwebui/mcp.json
```

### Manual Testing

```bash
# Start the MCP channel server with HTTP/WebSocket
make run ARGS='channel'

# With custom port
make run ARGS='channel --port 9090'
```

### Channel Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `CCWEBUI_CHANNEL_NAME` | `webui` | MCP server name (source attribute in channel tags) |
| `CCWEBUI_CHANNEL_STATE_DIR` | `~/.claude/channels/webui/` | Base directory for channel state |
| `CCWEBUI_CHANNEL_INBOX_DIR` | `{state_dir}/inbox/` | Directory for inbound file uploads |
| `CCWEBUI_CHANNEL_OUTBOX_DIR` | `{state_dir}/outbox/` | Directory for outbound file attachments |
| `CCWEBUI_CHANNEL_MAX_FILE_SIZE` | `52428800` (50MB) | Maximum file size in bytes |

## Features

- **MCP Channel**: Sole communication channel with Claude Code via MCP protocol over stdio
- **Chat Interface**: Real time conversational UI with WebSocket, Markdown rendering, and multi turn conversations
- **File Upload**: Attach files to messages (drag and drop or file picker), with validation for size and file types
- **File Attachments**: Claude can send files back to the browser via the reply tool
- **Conversation History**: SQLite backed persistence across server restarts, with configurable history limits
- **Message Editing**: Claude can edit previously sent messages

## Available Commands

| Command | Description |
|---------|-------------|
| `make install` | Install binary to ~/.local/bin with config |
| `make uninstall` | Remove binary (preserves config and data) |
| `make sync` | Install dependencies (development) |
| `make run` | Run the CLI application |
| `make run ARGS='serve'` | Start the web UI server (standalone) |
| `make run ARGS='channel'` | Start the MCP channel server |
| `make test` | Run tests |
| `make test-cov` | Run tests with coverage |
| `make check` | Run all quality checks |
| `make format` | Format code with Ruff |
| `make docker-build` | Build Docker image |
| `make run-up` | Start with Docker Compose |
| `make clean` | Remove build artifacts |
| `make help` | Show all available commands |

## Configuration

Configuration is loaded from `~/.config/ccwebui/.env`, then overridden by environment variables with the `CCWEBUI_` prefix.

| Variable | Default | Description |
|----------|---------|-------------|
| `CCWEBUI_APP_NAME` | `claude-code-webui` | Application name |
| `CCWEBUI_DEBUG` | `false` | Enable debug mode |
| `CCWEBUI_HOST` | `0.0.0.0` | Host to bind to |
| `CCWEBUI_PORT` | `8080` | Port to bind to |
| `CCWEBUI_UPLOAD_DIR` | `~/Downloads` | Directory for uploaded files |
| `CCWEBUI_MAX_UPLOAD_SIZE_MB` | `10` | Maximum upload file size in MB |
| `CCWEBUI_ALLOWED_UPLOAD_EXTENSIONS` | (see config.py) | Allowed file extensions for upload |
| `CCWEBUI_MAX_HISTORY_MESSAGES` | `100` | Max messages sent to Claude as context |
| `CCWEBUI_DATABASE_PATH` | `~/.local/share/ccwebui/ccwebui.db` | SQLite database file path |

See also [Channel Configuration](#channel-configuration) above for channel specific settings.

### File Locations

| Path | Purpose |
|------|---------|
| `~/.config/ccwebui/.env` | Configuration file |
| `~/.config/ccwebui/mcp.json` | MCP server config for `claude --mcp-config` |
| `~/.local/share/ccwebui/ccwebui.db` | SQLite database |
| `~/Downloads/` | Uploaded files |
| `~/.claude/channels/webui/` | MCP channel state (inbox/outbox) |

## Project Structure

```
claude-code-webui/
├── src/
│   ├── claude_code_webui.py  # CLI entry point (Typer, serve + channel commands)
│   ├── api.py                # FastAPI server with OTel, routes, lifespan
│   ├── config.py             # Settings (pydantic-settings)
│   ├── database.py           # SQLite database layer (aiosqlite)
│   ├── chat.py               # WebSocket chat handler (/ws/chat)
│   ├── channel.py            # MCP channel server (stdio, tools, protocol)
│   ├── channel_bridge.py     # Shared state bridge (MCP <-> FastAPI)
│   ├── file_upload.py        # File upload endpoint and validation
│   ├── logging_config.py     # Logging setup (rich + file)
│   ├── tracing.py            # OpenTelemetry tracing (JSONL)
│   └── templates/
│       ├── index.html         # Chat frontend (htmx)
│       └── partials/          # htmx partial templates
├── tests/                    # Unit tests
│   └── functional/           # Integration tests
├── specs/                    # Specifications and backlog
├── .mcp.json                 # MCP server configuration (development only)
├── pyproject.toml            # Project configuration
├── Makefile                  # Build automation
├── Dockerfile                # Container build
└── README.md                 # This file
```

## Docker

```bash
# Build Docker image
make docker-build

# Start with Docker Compose
make run-up

# Stop
make run-down
```

## Log Files

- `claude-code-webui.log` : Application logs (also shown in console with colors)
- `claude-code-webui-otel.log` : OpenTelemetry traces in JSONL format

## License

MIT
