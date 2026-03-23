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
- `~/.local/bin/claude-code-webui` : Backend binary
- `~/.local/bin/claude-webui` : Launcher script (auto port, inline MCP config)
- `~/.config/ccwebui/.env` : Configuration file
- `~/.local/share/ccwebui/` : Database and application data

Ensure `~/.local/bin` is in your `PATH`.

## Quick Start

### Prerequisites (OAuth2 Authentication)

To enable Google OAuth2 authentication:

1. Go to [Google Cloud Console](https://console.cloud.google.com/) > APIs & Services > Credentials
2. Create an OAuth 2.0 Client ID (Web application type)
3. Add each allowed origin's `/auth/callback` as an authorized redirect URI (e.g. `http://localhost:8080/auth/callback`, `https://myhost.example.com:8080/auth/callback`)
4. Create `~/.config/ccwebui/oauth2.yaml`:

```yaml
enabled: true
client_id: "your_client_id"
client_secret: "your_client_secret"
session_secret_key: "a_random_secret_at_least_32_chars"
allowed_origins:
  - "http://localhost:8080"
  - "https://myhost.example.com:8080"
allowed_emails:
  - "user1@example.com"
  - "user2@example.com"

# TLS (optional, required for HTTPS origins)
ssl_certfile: ~/.config/ccwebui/tls/cert.pem
ssl_keyfile: ~/.config/ccwebui/tls/key.pem
```

The redirect URI is computed dynamically from the incoming request's origin (scheme + host), validated against `allowed_origins`. Only the emails listed in `allowed_emails` can access the application. OAuth2 is disabled by default (when the YAML file is absent or `enabled: false`).

To generate a self-signed TLS certificate:

```bash
mkdir -p ~/.config/ccwebui/tls
openssl req -x509 -newkey rsa:2048 \
  -keyout ~/.config/ccwebui/tls/key.pem \
  -out ~/.config/ccwebui/tls/cert.pem \
  -days 365 -nodes \
  -subj "/CN=myhost.example.com" \
  -addext "subjectAltName=DNS:myhost.example.com,DNS:localhost"
```

### Starting the Server

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
# Start Claude with web UI (finds available port in 8080..8089)
claude-webui

# Pass additional Claude flags
claude-webui --resume
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

### Communication
- **MCP Channel**: Sole communication path with Claude Code via MCP protocol over stdio (no CLI subprocess fallback)
- **Real time Chat**: WebSocket based conversational UI with Markdown rendering, code blocks, and multi turn conversations
- **Conversation Persistence**: SQLite backed history across server restarts, with configurable context limits and auto generated titles

### File Handling
- **File Upload**: Multiple upload methods: click to browse, drag and drop onto drop zone, or drag and drop anywhere on the page
- **Clipboard Paste**: Paste images directly from clipboard (auto saved as `screenshot_YYYYMMDDHHMMSS.png`)
- **Upload Progress**: Visual progress bar with percentage during file upload
- **File Validation**: Extension whitelist (90+ types) and size limit enforcement with error feedback
- **File Attachments**: Claude can send files back to the browser as downloadable links via the reply tool

### Authentication & Security
- **Google OAuth2**: Optional authentication via GCP with login, callback, logout, and profile endpoints
- **Email Whitelist**: Strict access control via `allowed_emails` list (required when OAuth2 is enabled)
- **Dynamic Redirect URI**: OAuth2 callback URL computed from request origin, validated against `allowed_origins` (supports reverse proxies via X-Forwarded headers)
- **TLS Support**: Optional HTTPS via `ssl_certfile`/`ssl_keyfile`, required for non localhost origins
- **Unauthorized Page**: Styled 403 page with the denied email and a "Try another account" button to retrigger authentication
- **Logout**: Header button (visible when auth is enabled) clears session and redirects to login

### Observability
- **Logging**: Rich console output with file based logs in `~/.cache/ccwebui/logs/`
- **Tracing**: OpenTelemetry spans exported as JSONL, covering auth, database, channel, file upload, and WebSocket operations
- **Message Editing**: Claude can edit previously sent assistant messages in real time

## Available Commands

| Command | Description |
|---------|-------------|
| `make install` | Install binaries to ~/.local/bin with config |
| `make uninstall` | Remove binaries (preserves config and data) |
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
| `CCWEBUI_LOG_DIR` | `~/.cache/ccwebui/logs` | Directory for log files |
See also [Channel Configuration](#channel-configuration) above for channel specific settings.

OAuth2 and TLS settings are configured via `~/.config/ccwebui/oauth2.yaml` (see [Prerequisites](#prerequisites-oauth2-authentication)). Environment variables with the `CCWEBUI_` prefix can override YAML values.

### File Locations

| Path | Purpose |
|------|---------|
| `~/.local/bin/claude-webui` | Launcher script |
| `~/.local/bin/claude-code-webui` | Backend binary |
| `~/.config/ccwebui/.env` | Configuration file |
| `~/.config/ccwebui/oauth2.yaml` | OAuth2 and TLS configuration |
| `~/.config/ccwebui/tls/` | TLS certificate and key |
| `~/.local/share/ccwebui/ccwebui.db` | SQLite database |
| `~/.cache/ccwebui/logs/` | Application and OTel logs |
| `~/Downloads/` | Uploaded files |
| `~/.claude/channels/webui/` | MCP channel state (inbox/outbox) |

## Project Structure

```
claude-code-webui/
├── bin/
│   └── claude-webui            # Launcher script (installed to ~/.local/bin)
├── src/
│   ├── claude_code_webui.py  # CLI entry point (Typer, serve + channel commands)
│   ├── api.py                # FastAPI server with OTel, routes, lifespan
│   ├── auth.py               # OAuth2 authentication (GCP, login, callback, session)
│   ├── config.py             # Settings (pydantic-settings)
│   ├── database.py           # SQLite database layer (aiosqlite, users + conversations)
│   ├── chat.py               # WebSocket chat handler (/ws/chat)
│   ├── channel.py            # MCP channel server (stdio, tools, protocol)
│   ├── channel_bridge.py     # Shared state bridge (MCP <-> FastAPI)
│   ├── file_upload.py        # File upload endpoint and validation
│   ├── logging_config.py     # Logging setup (rich + file)
│   ├── tracing.py            # OpenTelemetry tracing (JSONL)
│   └── templates/
│       ├── index.html         # Chat frontend (htmx)
│       ├── unauthorized.html  # OAuth2 access denied page
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

Logs are written to `~/.cache/ccwebui/logs/`:

- `claude-code-webui.log` : Application logs (also shown in console with colors)
- `claude-code-webui-otel.log` : OpenTelemetry traces in JSONL format

## License

MIT
