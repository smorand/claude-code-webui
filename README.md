# Claude Code Web UI

A web interface for interacting with Claude Code CLI. Features a real time chat UI built with htmx, file upload support, and SQLite backed conversation persistence.

## Requirements

- Python 3.13 or later
- uv (package manager)

## Quick Start

```bash
# Install dependencies
make sync

# Start the web UI server
make run ARGS='serve'

# Start with auto reload for development
make run ARGS='serve --reload'
```

Open http://localhost:8080 in your browser to start chatting.

## Features

- **Chat Interface**: Real time conversational UI with WebSocket streaming, Markdown rendering, and multi turn conversations
- **File Upload**: Attach files to messages (drag and drop or file picker), with validation for size and file types
- **Conversation History**: SQLite backed persistence across server restarts, with configurable history limits
- **MCP Channel**: Pluggable communication layer for Claude integration (stub provided for development)

## Available Commands

| Command | Description |
|---------|-------------|
| `make sync` | Install dependencies |
| `make run` | Run the CLI application |
| `make run ARGS='serve'` | Start the web UI server |
| `make test` | Run tests |
| `make test-cov` | Run tests with coverage |
| `make check` | Run all quality checks |
| `make format` | Format code with Ruff |
| `make docker-build` | Build Docker image |
| `make run-up` | Start with Docker Compose |
| `make clean` | Remove build artifacts |
| `make help` | Show all available commands |

## Configuration

Configuration is done via environment variables with the `CCWEBUI_` prefix:

| Variable | Default | Description |
|----------|---------|-------------|
| `CCWEBUI_APP_NAME` | `claude-code-webui` | Application name |
| `CCWEBUI_DEBUG` | `false` | Enable debug mode |
| `CCWEBUI_HOST` | `0.0.0.0` | Host to bind to |
| `CCWEBUI_PORT` | `8080` | Port to bind to |
| `CCWEBUI_UPLOAD_DIR` | `./uploads` | Directory for uploaded files |
| `CCWEBUI_MAX_UPLOAD_SIZE_MB` | `10` | Maximum upload file size in MB |
| `CCWEBUI_ALLOWED_UPLOAD_EXTENSIONS` | (see config.py) | Allowed file extensions for upload |
| `CCWEBUI_MAX_HISTORY_MESSAGES` | `100` | Max messages sent to Claude as context |
| `CCWEBUI_DATABASE_PATH` | `./data/ccwebui.db` | SQLite database file path |

You can also create a `.env` file in the project root.

## Project Structure

```
claude-code-webui/
├── src/
│   ├── claude_code_webui.py  # CLI entry point (Typer)
│   ├── api.py                # FastAPI server with OTel, routes, lifespan
│   ├── config.py             # Settings (pydantic-settings)
│   ├── database.py           # SQLite database layer (aiosqlite)
│   ├── chat.py               # WebSocket chat handler
│   ├── channel.py            # MCP channel protocol and stub
│   ├── file_upload.py        # File upload endpoint and validation
│   ├── logging_config.py     # Logging setup (rich + file)
│   ├── tracing.py            # OpenTelemetry tracing (JSONL)
│   └── templates/
│       ├── index.html         # Chat frontend (htmx)
│       └── partials/          # htmx partial templates
├── tests/                    # Unit tests
│   └── functional/           # Integration tests
├── specs/                    # Specifications and backlog
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
