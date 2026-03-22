# MCP Server & Claude Code Channel Integration -- Change Specification

> Generated on: 2026-03-22
> Project: claude-code-webui
> Version: 1.1
> Status: Draft
> Type: Change Specification

## 1. Change Summary

Add an MCP (Model Context Protocol) server with Claude Code channel protocol support to the claude-code-webui backend. This MCP server is the **sole communication channel** between the web UI and Claude Code; there is no CLI subprocess fallback. The server follows the official `plugin:fakechat@claude-plugins-official` pattern, communicating with Claude Code over stdio and exposing reply/edit tools so Claude can send messages back to the web UI. All messages exchanged through the channel (both user messages forwarded to Claude and Claude's replies/edits) are persisted to SQLite via `aiosqlite`. The frontend consuming the WebSocket bridge uses htmx for real-time UI updates.

### Modifications Overview

| MOD ID  | Type | Title                                      | Priority   |
|---------|------|--------------------------------------------|------------|
| MOD-001 | Add  | MCP channel server (stdio transport)       | Must-have  |
| MOD-002 | Add  | Claude Code channel protocol compliance    | Must-have  |
| MOD-003 | Add  | Reply and edit_message tools               | Must-have  |
| MOD-004 | Add  | WebSocket bridge for real-time UI delivery | Must-have  |
| MOD-005 | Add  | Channel configuration settings             | Must-have  |
| MOD-006 | Add  | File attachment support (inbound/outbound) | Should-have|
| MOD-007 | Add  | SQLite message persistence for MCP channel | Must-have  |

## 2. Current State Analysis

### 2.1 Project Overview

The project is a Python 3.13 FastAPI application that provides a web interface for interacting with Claude Code CLI. It currently has:
- A Typer CLI entry point (`src/claude_code_webui.py`) with a `serve` command
- A FastAPI server (`src/api.py`) with only a `/health` endpoint
- Configuration via pydantic-settings with `CCWEBUI_` prefix (`src/config.py`)
- Logging with rich console + file output (`src/logging_config.py`)
- OpenTelemetry tracing with JSONL export (`src/tracing.py`)
- Docker support (Dockerfile + docker-compose.yml)

The application has no communication layer with Claude Code CLI yet. It is an empty shell with infrastructure scaffolding.

### 2.2 Existing Specifications

- `specs/BACKLOG.md`: Lists five features including "MCP Server Integration" and "Claude Code Channel Protocol" as separate backlog items. This spec addresses both.

### 2.3 Relevant Architecture

- **CLI layer**: Typer app with `serve` command that starts uvicorn
- **API layer**: FastAPI with OTel instrumentation, factory pattern (`create_app()`)
- **Config**: pydantic-settings `Settings` class with env var prefix
- **Observability**: Structured logging + OTel tracing already in place
- **Dependencies**: FastAPI, uvicorn, httpx, pydantic, opentelemetry stack already present

## 3. Requested Modifications

### MOD-001: MCP Channel Server (stdio transport)

- **Type:** Add
- **Description:** Implement an MCP server that runs as a subprocess spawned by Claude Code CLI, communicating over stdin/stdout using the MCP protocol. This server declares the `claude/channel` experimental capability so Claude Code registers it as a channel. This MCP server is the **sole communication channel** between the web UI and Claude Code. There is no CLI subprocess fallback or alternative communication path.
- **Rationale:** This is the foundational and only transport layer that enables Claude Code to communicate with our web UI. All user/assistant interactions flow exclusively through this MCP channel.
- **Priority:** Must-have
- **Details:**
  - The MCP server process must use stdio transport (stdin/stdout for JSON-RPC messages)
  - Must NOT write anything to stdout except MCP protocol messages (logging must go to stderr or files)
  - Must declare `experimental: { "claude/channel": {} }` capability
  - Must declare `tools: {}` capability for two-way communication
  - Must provide `instructions` string telling Claude how to interact with the channel
  - The MCP server is a separate entry point from the FastAPI server; Claude Code spawns it as a subprocess
  - Uses the Python MCP SDK (`mcp` package) with its low-level `Server` class (not `FastMCP`) since we need experimental capabilities

### MOD-002: Claude Code Channel Protocol Compliance

- **Type:** Add
- **Description:** Implement the channel notification protocol so the web UI can push user messages into Claude Code sessions and receive responses.
- **Rationale:** The channel protocol (`notifications/claude/channel`) is the standard mechanism for pushing events into Claude Code. Compliance ensures interoperability with the Claude Code CLI.
- **Priority:** Must-have
- **Details:**
  - Emit `notifications/claude/channel` with `content` (string) and `meta` (dict of string to string) fields
  - Meta must include: `chat_id`, `message_id`, `user`, `ts` (ISO 8601 timestamp)
  - Meta may include: `file_path` for file attachments
  - Content becomes the body of the `<channel>` tag in Claude's context
  - Each meta key becomes an attribute on the `<channel>` tag
  - The `source` attribute is set automatically from the server's configured name
  - Instructions must tell Claude to use the reply tool and pass `chat_id` from the tag

### MOD-003: Reply and edit_message Tools

- **Type:** Add
- **Description:** Expose two MCP tools: `reply` (send a message back to the web UI) and `edit_message` (edit a previously sent message).
- **Rationale:** These tools enable two-way communication. Claude calls them to send responses back through the channel to the browser.
- **Priority:** Must-have
- **Details:**
  - **`reply` tool:**
    - Input schema: `text` (string, required), `reply_to` (string, optional message ID), `files` (array of strings, optional absolute file paths)
    - Broadcasts the message to connected WebSocket clients
    - For file attachments: copies file to outbox directory, generates a URL, includes file metadata in broadcast
    - File size limit: 50MB per file
    - Returns confirmation with message ID(s)
  - **`edit_message` tool:**
    - Input schema: `message_id` (string, required), `text` (string, required)
    - Broadcasts an edit event to connected WebSocket clients
    - Returns "ok" on success
  - Tool handlers must be registered via `ListToolsRequestSchema` and `CallToolRequestSchema`

### MOD-004: WebSocket Bridge for Real-time UI Delivery

- **Type:** Add
- **Description:** Add a WebSocket endpoint to the FastAPI server that bridges between the MCP server process and browser clients. The frontend consuming this WebSocket uses htmx for real-time DOM updates.
- **Rationale:** The MCP server communicates with Claude Code over stdio, but browser clients need WebSocket for real-time message delivery. An inter-process communication mechanism bridges the two.
- **Priority:** Must-have
- **Details:**
  - FastAPI WebSocket endpoint at `/ws` for browser connections
  - Track connected clients for broadcast
  - Accept inbound messages from browser clients (JSON with `id` and `text` fields)
  - Forward inbound messages to the MCP server's `deliver()` function
  - Receive outbound messages from MCP tool calls (reply, edit) and broadcast to WebSocket clients
  - Message wire format: `{ type: "msg", id, from, text, ts, replyTo?, file? }` for messages, `{ type: "edit", id, text }` for edits
  - The MCP server and FastAPI server run in the same process to share state (connected clients set, message delivery function)
  - The frontend uses htmx with WebSocket extension (`hx-ws`) to connect and render messages; this spec covers the backend WebSocket contract, not the htmx frontend itself

### MOD-005: Channel Configuration Settings

- **Type:** Add
- **Description:** Add channel-specific settings to the `Settings` class.
- **Rationale:** Channel behavior (port, directories, server name) must be configurable via environment variables following the existing `CCWEBUI_` prefix pattern.
- **Priority:** Must-have
- **Details:**
  - `channel_name: str = "webui"`: MCP server name (appears as `source` attribute in `<channel>` tags)
  - `channel_state_dir: Path`: Base directory for channel state (default: `~/.claude/channels/webui/`)
  - `channel_inbox_dir: Path`: Directory for inbound file uploads (default: `{state_dir}/inbox/`)
  - `channel_outbox_dir: Path`: Directory for outbound file attachments (default: `{state_dir}/outbox/`)
  - `channel_max_file_size: int = 52_428_800`: Maximum file size in bytes (50MB)

### MOD-006: File Attachment Support (Inbound/Outbound)

- **Type:** Add
- **Description:** Support file uploads from the browser to Claude (inbound) and file attachments from Claude to the browser (outbound).
- **Rationale:** The fakechat reference implementation supports file attachments in both directions. This is important for sharing code files, screenshots, and other artifacts.
- **Priority:** Should-have
- **Details:**
  - **Inbound (browser to Claude):**
    - HTTP POST `/upload` endpoint accepting multipart form data (`id`, `text`, `file` fields)
    - Save uploaded files to inbox directory with timestamped names
    - Include `file_path` in channel notification meta so Claude can read the file
  - **Outbound (Claude to browser):**
    - Reply tool accepts `files` parameter with absolute paths
    - Copy files to outbox directory with randomized names
    - Serve outbox files via HTTP GET `/files/{filename}`
    - Include file URL and name in WebSocket broadcast
  - File size validation (reject files > 50MB)
  - Basic MIME type detection for serving files

### MOD-007: SQLite Message Persistence for MCP Channel

- **Type:** Add
- **Description:** Persist all messages exchanged through the MCP channel to SQLite using `aiosqlite`. When the MCP server receives messages from Claude (via the `reply` and `edit_message` tools) or from users (via channel notifications triggered by WebSocket/upload), these messages must be written to the SQLite database.
- **Rationale:** Message persistence enables chat history, session continuity, and auditability. SQLite provides a lightweight, zero-configuration storage layer suitable for a single-node web UI.
- **Priority:** Must-have
- **Details:**
  - The database schema (tables, columns, migrations) is defined by the chat+upload spec. This spec describes only how MCP channel messages flow into SQLite.
  - **Inbound messages (user to Claude):** When a user message is delivered via WebSocket or file upload, the channel bridge must persist the message to SQLite before emitting the `notifications/claude/channel` notification. Fields stored: message ID, chat ID, sender ("user"), text content, timestamp, optional file path.
  - **Outbound messages (Claude to user):** When the `reply` tool is called, the channel bridge must persist Claude's response to SQLite before broadcasting to WebSocket clients. Fields stored: message ID, chat ID, sender ("assistant"), text content, timestamp, optional reply_to reference, optional file metadata.
  - **Edit operations:** When the `edit_message` tool is called, the channel bridge must update the existing message record in SQLite (update text, set an `edited_at` timestamp) before broadcasting the edit event.
  - Uses `aiosqlite` for async-compatible database access
  - Database connection lifecycle is managed by the channel bridge (open on startup, close on shutdown)
  - The channel bridge receives the database path from `Settings` (configured by the chat+upload spec)

## 4. Impact Analysis

### 4.1 Affected Components

| File/Module                  | Impact Type | Description                                                          |
|------------------------------|-------------|----------------------------------------------------------------------|
| `src/config.py`              | Modify      | Add channel-specific settings fields                                 |
| `src/api.py`                 | Modify      | Add WebSocket endpoint, file upload/download endpoints, lifespan mgmt|
| `src/claude_code_webui.py`   | Modify      | Add `channel` CLI command to start MCP server process                |
| `src/channel.py`             | New         | MCP channel server implementation (stdio transport, tools, notifications)|
| `src/channel_bridge.py`      | New         | Shared state bridge between MCP server and FastAPI (clients, broadcast, SQLite persistence)|
| `pyproject.toml`             | Modify      | Add `mcp` and `aiosqlite` dependencies, update isort known-first-party|
| `.mcp.json`                  | New         | MCP server configuration for Claude Code to discover the channel     |
| `Dockerfile`                 | Modify      | May need to install `mcp` and `aiosqlite` packages                   |

### 4.2 Affected Requirements

| Spec File         | Requirement ID | Impact   | Description                                                    |
|-------------------|----------------|----------|----------------------------------------------------------------|
| `specs/BACKLOG.md`| MCP Server     | Resolves | This spec implements the MCP Server Integration backlog item   |
| `specs/BACKLOG.md`| Channel Protocol| Resolves| This spec implements the Channel Protocol backlog item          |
| `specs/BACKLOG.md`| Web Chat       | Partial  | This spec provides the backend for chat; frontend is separate  |

### 4.3 Affected Tests

| Test File                       | Test ID/Name               | Action   | Description                                           |
|---------------------------------|----------------------------|----------|-------------------------------------------------------|
| `tests/test_config.py`         | `test_default_settings`    | Modify   | Must verify new channel settings defaults             |
| `tests/test_config.py`         | `test_settings_from_env`   | Modify   | Must verify channel settings can be set via env vars  |
| `tests/functional/test_api.py` | N/A                        | Add      | Must add WebSocket, upload, and file serving tests    |
| `tests/test_channel.py`        | N/A                        | New      | Must add unit tests for channel server logic          |
| `tests/test_channel_bridge.py` | N/A                        | New      | Must add unit tests for bridge state management and SQLite persistence|

### 4.4 Affected Documentation

| Document                    | Section          | Action | Description                                                |
|-----------------------------|------------------|--------|------------------------------------------------------------|
| `CLAUDE.md`                 | Project Structure| Update | Add new modules (channel.py, channel_bridge.py)            |
| `CLAUDE.md`                 | Key Commands     | Update | Add channel command                                        |
| `README.md`                 | Configuration    | Update | Add channel settings documentation                         |
| `README.md`                 | Project Structure| Update | Add new modules                                            |
| `README.md`                 | Quick Start      | Update | Add channel usage instructions                             |
| `docs/architecture.md`      | Components       | Update | Add Channel Layer and MCP Server documentation             |
| `.agent_docs/python.md`     | N/A              | Review | Verify MCP patterns align with coding standards            |

### 4.5 Dependencies & Risks

**New dependencies:**
- `mcp>=1.2.0`: Python MCP SDK (provides `mcp.server.lowlevel.Server`, `mcp.server.stdio`, types)
- `aiosqlite>=0.20.0`: Async SQLite driver for message persistence
- `websockets>=12.0` or use FastAPI's built-in WebSocket support (preferred, no new dep)

**Risks:**
- **Sole channel dependency**: The MCP server is the only communication path with Claude Code. There is no CLI subprocess fallback. If the MCP server fails to start or the channel protocol handshake fails, the web UI will have no way to communicate with Claude. Error handling and clear diagnostics at startup are critical.
- **stdio constraint**: The MCP server process must never write to stdout except MCP protocol messages. All Python logging must be directed to stderr or files. This requires careful configuration of the logging setup.
- **Process architecture**: The MCP server runs as a subprocess spawned by Claude Code, while the FastAPI server runs independently. They must share state for WebSocket client management. The recommended approach is to run both in the same process using asyncio (the MCP stdio loop and the FastAPI/uvicorn server).
- **Python MCP SDK maturity**: The `mcp` Python package is stable (v1.x) but the experimental `claude/channel` capability is Claude-Code-specific, not part of the base MCP spec. We need to use the low-level Server API to set experimental capabilities.
- **SQLite write contention**: Under high message throughput, concurrent writes to SQLite may cause contention. `aiosqlite` serializes writes through a single connection, which is acceptable for a single-node web UI but must be monitored.
- **No breaking changes**: This is purely additive; existing `/health` endpoint and CLI commands are unchanged.

**Rollback strategy:** Since this is entirely new code with no modifications to existing behavior, rollback is simply removing the new modules and reverting config changes.

## 5. New & Modified Requirements

### New Requirements

#### FR-NEW-001: MCP Channel Server Entry Point

- **Description:** The system must provide a standalone entry point that starts an MCP server communicating over stdio, declaring the `claude/channel` experimental capability. This MCP server is the **sole communication channel** with Claude Code; no CLI subprocess or alternative transport exists.
- **Inputs:** stdin (MCP JSON-RPC messages from Claude Code)
- **Outputs:** stdout (MCP JSON-RPC responses to Claude Code)
- **Business Rules:**
  - Must use stdio transport exclusively for MCP communication
  - Must declare `experimental: { "claude/channel": {} }` and `tools: {}` capabilities
  - Must provide an `instructions` string explaining the channel behavior to Claude
  - Must never write non-MCP content to stdout
  - All logging must go to stderr or log files
  - The web UI must not implement any alternative communication path with Claude Code (no CLI subprocess spawning, no HTTP-based fallback)
- **Priority:** Must-have

#### FR-NEW-002: Channel Event Emission

- **Description:** The system must emit `notifications/claude/channel` notifications when a user sends a message from the web UI. The message must be persisted to SQLite before the notification is emitted.
- **Inputs:** User message (text, optional file attachment) from WebSocket or HTTP upload
- **Outputs:** MCP notification with `content` and `meta` fields; SQLite row inserted
- **Business Rules:**
  - The message must be persisted to SQLite before emitting the MCP notification (persist-then-notify ordering)
  - `content` must contain the user's message text (or filename if attachment-only)
  - `meta` must include `chat_id` (string), `message_id` (string), `user` (string), `ts` (ISO 8601 string)
  - `meta` must include `file_path` (absolute path) when a file attachment is present
  - Meta keys must contain only letters, digits, and underscores
- **Priority:** Must-have

#### FR-NEW-003: Reply Tool

- **Description:** The system must expose an MCP tool named `reply` that Claude calls to send messages back to the web UI. The message must be persisted to SQLite before broadcasting.
- **Inputs:** `text` (string, required), `reply_to` (string, optional), `files` (array of strings, optional)
- **Outputs:** Confirmation text with sent message ID(s); SQLite row inserted; message broadcast to WebSocket clients
- **Business Rules:**
  - Must persist the message to SQLite before broadcasting (persist-then-broadcast ordering)
  - Must broadcast a message event (`type: "msg"`) to all connected WebSocket clients
  - Must set `from` to `"assistant"` on outbound messages
  - If `files` is provided, must copy the first file to the outbox directory and include file URL/name in broadcast
  - Must reject files larger than the configured maximum (default 50MB)
  - Must return `isError: true` on failure with descriptive error message
- **Priority:** Must-have

#### FR-NEW-004: Edit Message Tool

- **Description:** The system must expose an MCP tool named `edit_message` that Claude calls to edit a previously sent message. The edit must be persisted to SQLite before broadcasting.
- **Inputs:** `message_id` (string, required), `text` (string, required)
- **Outputs:** Confirmation text; SQLite row updated; edit event broadcast to WebSocket clients
- **Business Rules:**
  - Must update the existing message record in SQLite (new text, `edited_at` timestamp) before broadcasting
  - Must broadcast an edit event (`type: "edit"`) to all connected WebSocket clients
  - Must return "ok" on success
  - Must return `isError: true` on failure (including if message_id does not exist in SQLite)
- **Priority:** Must-have

#### FR-NEW-005: WebSocket Endpoint

- **Description:** The FastAPI server must expose a WebSocket endpoint at `/ws` for real-time communication with browser clients.
- **Inputs:** WebSocket connections from browsers; JSON messages with `id` and `text` fields
- **Outputs:** JSON messages broadcast to all connected clients (message and edit events)
- **Business Rules:**
  - Must track connected clients in a set for broadcast
  - Must remove clients from the set on disconnect
  - Must forward valid inbound messages (with `id` and `text`) to the channel delivery function
  - Must silently discard malformed messages
  - Must handle concurrent connections
- **Priority:** Must-have

#### FR-NEW-006: File Upload Endpoint

- **Description:** The FastAPI server must expose a POST `/upload` endpoint for file uploads from the browser.
- **Inputs:** Multipart form data with fields: `id` (string, required), `text` (string, optional), `file` (file, optional)
- **Outputs:** HTTP 204 No Content on success; channel notification emitted
- **Business Rules:**
  - Must reject requests without `id` field (HTTP 400)
  - Must save uploaded files to the inbox directory with timestamped filenames preserving original extension
  - Must reject files exceeding the configured maximum size
  - Must create inbox directory if it does not exist
  - Must forward message (with file path if present) to channel delivery function
- **Priority:** Should-have

#### FR-NEW-007: File Serving Endpoint

- **Description:** The FastAPI server must serve outbox files via GET `/files/{filename}`.
- **Inputs:** GET request with filename path parameter
- **Outputs:** File content with appropriate MIME type; HTTP 404 if not found
- **Business Rules:**
  - Must reject filenames containing `..` or `/` (path traversal prevention)
  - Must detect MIME type from file extension
  - Must return HTTP 404 for non-existent files
  - Must serve files only from the outbox directory
- **Priority:** Should-have

#### FR-NEW-008: MCP Server Configuration File

- **Description:** The project must include an `.mcp.json` file that Claude Code reads to discover and spawn the channel server.
- **Inputs:** N/A (static configuration file)
- **Outputs:** N/A
- **Business Rules:**
  - Must specify the command to start the MCP server (e.g., `uv run python src/channel.py`)
  - Must be placed in the project root
  - Must follow the standard MCP server configuration format: `{ "mcpServers": { "<name>": { "command": "...", "args": [...] } } }`
- **Priority:** Must-have

#### FR-NEW-009: Channel CLI Command

- **Description:** The CLI must provide a `channel` command that starts the MCP server for manual testing outside of Claude Code.
- **Inputs:** Optional `--port` flag for the HTTP server component
- **Outputs:** MCP server running on stdio; HTTP endpoints on configured port
- **Business Rules:**
  - Must initialize logging to stderr (not stdout)
  - Must start the MCP server with stdio transport
  - Must start the HTTP/WebSocket server on the configured port
  - Must run both event loops concurrently using asyncio
- **Priority:** Must-have

#### FR-NEW-010: SQLite Message Persistence

- **Description:** The channel bridge must persist all messages exchanged through the MCP channel to SQLite using `aiosqlite`. This covers user messages (inbound) and Claude's replies/edits (outbound).
- **Inputs:** Message data from channel delivery (user messages) and tool handlers (reply, edit_message)
- **Outputs:** SQLite rows inserted or updated
- **Business Rules:**
  - The database schema (table definitions, migrations) is defined by the chat+upload spec. This requirement covers the write path only.
  - User messages must be persisted before the `notifications/claude/channel` notification is emitted
  - Assistant messages (from `reply` tool) must be persisted before broadcasting to WebSocket clients
  - Message edits (from `edit_message` tool) must update the existing row and set an `edited_at` timestamp before broadcasting
  - The database connection must be opened during channel bridge initialization and closed during shutdown
  - The database path is provided by the `Settings` class (configured by the chat+upload spec)
  - All database operations must use `aiosqlite` for async compatibility
  - Database write failures must be logged and must NOT prevent message delivery (log-and-continue for persistence failures; the real-time path takes priority)
- **Priority:** Must-have

### Modified Requirements

#### FR-MOD-001: Settings Class (references existing `src/config.py`)

- **Original behavior:** Settings class has `app_name`, `debug`, `host`, `port` fields only.
- **New behavior:** Settings class must also include `channel_name`, `channel_state_dir`, `channel_inbox_dir`, `channel_outbox_dir`, `channel_max_file_size` fields with appropriate defaults.
- **Reason for change:** Channel configuration must follow the same `CCWEBUI_` env var pattern.
- **Business Rules:**
  - All new fields must be configurable via `CCWEBUI_` prefixed environment variables
  - `channel_state_dir` must default to `~/.claude/channels/{channel_name}/`
  - `channel_inbox_dir` must default to `{channel_state_dir}/inbox/`
  - `channel_outbox_dir` must default to `{channel_state_dir}/outbox/`
  - `channel_max_file_size` must default to 52,428,800 (50MB)

## 6. Non-Functional Requirements Changes

#### NFR-NEW-001: stdio Safety

- **Description:** The MCP server process must never write anything to stdout except valid MCP JSON-RPC messages. Violation will corrupt the protocol and break communication with Claude Code.
- **Priority:** Must-have

#### NFR-NEW-002: Concurrent WebSocket Handling

- **Description:** The WebSocket endpoint must handle multiple concurrent browser connections without blocking or data loss.
- **Priority:** Must-have

#### NFR-NEW-003: OTel Tracing for Channel Operations

- **Description:** All channel operations (message delivery, tool calls, file operations, SQLite persistence) must be traced with OpenTelemetry spans following the existing `category.operation` naming convention (e.g., `channel.deliver`, `channel.reply`, `channel.upload`, `channel.persist`).
- **Priority:** Must-have

#### NFR-NEW-004: Sole Channel Constraint

- **Description:** The MCP channel server must be the only mechanism for communicating with Claude Code. The web UI must not implement any fallback transport (CLI subprocess, HTTP polling, or other). If the MCP channel is unavailable, the web UI must report the error clearly rather than attempting an alternative path.
- **Priority:** Must-have

#### NFR-NEW-005: SQLite Persistence Resilience

- **Description:** SQLite persistence failures must not block the real-time message path. If a database write fails, the error must be logged with full context (message ID, operation type, error details) and the message must still be delivered/broadcast. The system must not crash or drop messages due to SQLite errors.
- **Priority:** Must-have

#### NFR-NEW-006: htmx Frontend Compatibility

- **Description:** The WebSocket endpoint wire format must be compatible with htmx's WebSocket extension (`hx-ws`). Messages broadcast to clients must be consumable by htmx for DOM updates. The backend must not assume any specific JavaScript framework on the client side beyond htmx.
- **Priority:** Must-have

## 7. Documentation Updates

All documentation changes listed below MUST be implemented as part of this change.

### 7.1 CLAUDE.md & .agent_docs/

**CLAUDE.md updates:**
- Add to Project Structure:
  - `src/channel.py` : MCP channel server (stdio transport, tools, channel protocol)
  - `src/channel_bridge.py` : Shared state bridge between MCP server and FastAPI
  - `.mcp.json` : MCP server configuration for Claude Code discovery
- Add to Key Commands:
  - `make run ARGS='channel'` : Start the MCP channel server (for manual testing)
- Add to Conventions:
  - MCP server process must never write to stdout except MCP protocol messages
  - Channel state stored in `~/.claude/channels/{channel_name}/`

### 7.2 docs/*

**docs/architecture.md updates:**
- Add "Channel Layer" section describing:
  - MCP server architecture (stdio transport with Claude Code)
  - Channel protocol compliance (notifications, tools)
  - WebSocket bridge pattern (MCP server <-> FastAPI <-> browser)
  - File handling (inbox/outbox directories)

### 7.3 README.md

- Add "Channel Integration" section explaining:
  - How the MCP channel works with Claude Code CLI (sole communication channel, no CLI subprocess fallback)
  - Configuration variables (`CCWEBUI_CHANNEL_*`)
  - Usage: `claude --channels plugin:webui@...` or `claude --dangerously-load-development-channels server:webui`
  - File attachment support
  - SQLite message persistence (references chat+upload spec for schema)
  - htmx frontend integration pattern
- Update Project Structure with new files
- Update Configuration table with channel settings

## 8. End-to-End Test Updates

All test changes MUST be implemented in the `tests/` directory. Every modification MUST have tests covering happy paths, failure paths, edge cases, and error recovery.

### 8.1 Test Summary

| Test ID       | Action   | Category     | Scenario                                    | Priority |
|---------------|----------|--------------|---------------------------------------------|----------|
| E2E-NEW-001   | New      | Core Journey | Channel delivers user message to MCP        | Critical |
| E2E-NEW-002   | New      | Core Journey | Reply tool broadcasts to WebSocket clients  | Critical |
| E2E-NEW-003   | New      | Feature      | Edit message tool broadcasts edit event     | High     |
| E2E-NEW-004   | New      | Feature      | WebSocket connection lifecycle              | High     |
| E2E-NEW-005   | New      | Feature      | File upload and channel notification        | High     |
| E2E-NEW-006   | New      | Feature      | File serving from outbox                    | High     |
| E2E-NEW-007   | New      | Error        | Malformed WebSocket message handling        | Medium   |
| E2E-NEW-008   | New      | Error        | File upload exceeds size limit              | Medium   |
| E2E-NEW-009   | New      | Error        | Path traversal in file serving              | High     |
| E2E-NEW-010   | New      | Error        | Unknown tool call handling                  | Medium   |
| E2E-NEW-011   | New      | Feature      | Reply tool with file attachment             | Medium   |
| E2E-NEW-012   | New      | Edge Case    | Reply tool with oversized file              | Medium   |
| E2E-NEW-013   | New      | Feature      | Channel settings from environment           | High     |
| E2E-NEW-014   | New      | Core Journey | User message persisted to SQLite            | Critical |
| E2E-NEW-015   | New      | Core Journey | Reply tool persists to SQLite before broadcast| Critical |
| E2E-NEW-016   | New      | Feature      | Edit message updates SQLite record          | High     |
| E2E-NEW-017   | New      | Error        | SQLite write failure does not block delivery| High     |
| E2E-NEW-018   | New      | Feature      | Sole channel: no fallback transport exists  | High     |
| E2E-MOD-001   | Modified | Feature      | Config defaults include channel settings    | High     |

### 8.2 New Tests

#### E2E-NEW-001: Channel Delivers User Message

- **Category:** Core Journey
- **Modification:** MOD-001, MOD-002
- **Preconditions:** Channel bridge initialized, MCP notification mock in place
- **Steps:**
  - Given a channel bridge with a mocked MCP notification sender
  - When a user message is delivered with id="m1", text="hello", no file
  - Then a `notifications/claude/channel` notification is emitted with content="hello" and meta containing chat_id="web", message_id="m1", user="web", ts (ISO format)
- **Priority:** Critical

#### E2E-NEW-002: Reply Tool Broadcasts to WebSocket Clients

- **Category:** Core Journey
- **Modification:** MOD-003, MOD-004
- **Preconditions:** Channel bridge with mock WebSocket clients
- **Steps:**
  - Given a channel bridge with two connected mock clients
  - When the reply tool is called with text="response" and no files
  - Then both clients receive a JSON message with type="msg", from="assistant", text="response"
  - And the tool returns a success result with the message ID
- **Priority:** Critical

#### E2E-NEW-003: Edit Message Tool

- **Category:** Feature
- **Modification:** MOD-003
- **Preconditions:** Channel bridge with mock WebSocket clients
- **Steps:**
  - Given a channel bridge with a connected mock client
  - When the edit_message tool is called with message_id="m1", text="updated"
  - Then the client receives a JSON message with type="edit", id="m1", text="updated"
  - And the tool returns "ok"
- **Priority:** High

#### E2E-NEW-004: WebSocket Connection Lifecycle

- **Category:** Feature
- **Modification:** MOD-004
- **Preconditions:** FastAPI test app with channel bridge
- **Steps:**
  - Given a running FastAPI app with the WebSocket endpoint
  - When a WebSocket client connects to /ws
  - Then the client is added to the connected clients set
  - When the client disconnects
  - Then the client is removed from the connected clients set
- **Priority:** High

#### E2E-NEW-005: File Upload and Channel Notification

- **Category:** Feature
- **Modification:** MOD-006
- **Preconditions:** FastAPI test app, temp inbox directory, mocked delivery function
- **Steps:**
  - Given a running FastAPI app with upload endpoint
  - When a POST /upload request is sent with id="m1", text="see attached", file=test.txt (10 bytes)
  - Then the response status is 204
  - And the file is saved to the inbox directory with a timestamped name
  - And the delivery function is called with file_path pointing to the saved file
- **Priority:** High

#### E2E-NEW-006: File Serving from Outbox

- **Category:** Feature
- **Modification:** MOD-006
- **Preconditions:** A file exists in the outbox directory
- **Steps:**
  - Given a file "test.png" in the outbox directory
  - When a GET /files/test.png request is sent
  - Then the response status is 200
  - And the content-type is "image/png"
  - And the response body matches the file content
- **Priority:** High

#### E2E-NEW-007: Malformed WebSocket Message

- **Category:** Error
- **Modification:** MOD-004
- **Preconditions:** Connected WebSocket client, mocked delivery function
- **Steps:**
  - Given a connected WebSocket client
  - When the client sends "not json"
  - Then the delivery function is not called
  - And the WebSocket connection remains open
- **Priority:** Medium

#### E2E-NEW-008: File Upload Exceeds Size Limit

- **Category:** Error
- **Modification:** MOD-006
- **Preconditions:** FastAPI test app with low max file size (e.g., 100 bytes)
- **Steps:**
  - Given a max file size of 100 bytes
  - When a POST /upload request is sent with a 200-byte file
  - Then the response status is 413 (Request Entity Too Large)
  - And no file is saved to the inbox directory
- **Priority:** Medium

#### E2E-NEW-009: Path Traversal in File Serving

- **Category:** Error
- **Modification:** MOD-006
- **Preconditions:** FastAPI test app
- **Steps:**
  - Given a running FastAPI app
  - When a GET /files/../../../etc/passwd request is sent
  - Then the response status is 400
- **Priority:** High

#### E2E-NEW-010: Unknown Tool Call

- **Category:** Error
- **Modification:** MOD-003
- **Preconditions:** Channel tool handler
- **Steps:**
  - Given the channel tool handler
  - When a CallToolRequest is received for tool name "nonexistent"
  - Then the response has isError=true and descriptive error text
- **Priority:** Medium

#### E2E-NEW-011: Reply Tool with File Attachment

- **Category:** Feature
- **Modification:** MOD-003, MOD-006
- **Preconditions:** Temp outbox directory, mock WebSocket clients, temp source file
- **Steps:**
  - Given a source file at /tmp/test.txt (10 bytes) and a mock client
  - When the reply tool is called with text="here's the file", files=["/tmp/test.txt"]
  - Then the file is copied to the outbox directory
  - And the client receives a message with file.url starting with "/files/" and file.name="test.txt"
- **Priority:** Medium

#### E2E-NEW-012: Reply Tool with Oversized File

- **Category:** Edge Case
- **Modification:** MOD-003, MOD-006
- **Preconditions:** Temp source file larger than max size
- **Steps:**
  - Given a source file larger than the configured maximum
  - When the reply tool is called with files=[path_to_large_file]
  - Then the tool returns isError=true with a "file too large" message
  - And no file is copied to the outbox directory
- **Priority:** Medium

#### E2E-NEW-013: Channel Settings from Environment

- **Category:** Feature
- **Modification:** MOD-005
- **Preconditions:** Environment variables set
- **Steps:**
  - Given CCWEBUI_CHANNEL_NAME="custom" in environment
  - When Settings is instantiated
  - Then settings.channel_name equals "custom"
  - And settings.channel_state_dir contains "custom" in its path
- **Priority:** High

#### E2E-NEW-014: User Message Persisted to SQLite

- **Category:** Core Journey
- **Modification:** MOD-007
- **Preconditions:** Channel bridge initialized with an in-memory SQLite database, MCP notification mock
- **Steps:**
  - Given a channel bridge with SQLite persistence enabled
  - When a user message is delivered with id="m1", text="hello"
  - Then a row is inserted in the messages table with message_id="m1", sender="user", text="hello"
  - And the `notifications/claude/channel` notification is emitted after persistence
- **Priority:** Critical

#### E2E-NEW-015: Reply Tool Persists to SQLite Before Broadcast

- **Category:** Core Journey
- **Modification:** MOD-003, MOD-007
- **Preconditions:** Channel bridge with in-memory SQLite and mock WebSocket clients
- **Steps:**
  - Given a channel bridge with SQLite persistence and a connected mock client
  - When the reply tool is called with text="response"
  - Then a row is inserted in the messages table with sender="assistant", text="response"
  - And the WebSocket broadcast occurs after the database write
- **Priority:** Critical

#### E2E-NEW-016: Edit Message Updates SQLite Record

- **Category:** Feature
- **Modification:** MOD-003, MOD-007
- **Preconditions:** Channel bridge with in-memory SQLite containing an existing message row
- **Steps:**
  - Given a message with id="m1" already persisted in SQLite
  - When the edit_message tool is called with message_id="m1", text="updated"
  - Then the messages table row for "m1" has text="updated" and edited_at is set
  - And the edit event is broadcast to WebSocket clients
- **Priority:** High

#### E2E-NEW-017: SQLite Write Failure Does Not Block Delivery

- **Category:** Error
- **Modification:** MOD-007
- **Preconditions:** Channel bridge with a mocked SQLite connection that raises on write
- **Steps:**
  - Given a channel bridge with a failing SQLite connection
  - When a user message is delivered with id="m1", text="hello"
  - Then the `notifications/claude/channel` notification is still emitted
  - And the error is logged with message ID and operation context
- **Priority:** High

#### E2E-NEW-018: Sole Channel Constraint Validation

- **Category:** Feature
- **Modification:** MOD-001
- **Preconditions:** Project source code
- **Steps:**
  - Given the project source code
  - When searching for subprocess.Popen, subprocess.run, or asyncio.create_subprocess patterns that spawn `claude` CLI
  - Then no such patterns exist outside of the MCP channel server
  - (This is a static analysis / code review test to verify no CLI subprocess fallback was introduced)
- **Priority:** High

### 8.3 Modified Tests

#### E2E-MOD-001: Config Defaults Include Channel Settings (was `test_default_settings`)

- **Original test:** Verified app_name, debug, host, port defaults only
- **Modified to validate:** Also verifies channel_name, channel_state_dir, channel_inbox_dir, channel_outbox_dir, channel_max_file_size defaults
- **Steps:**
  - Given no environment variables set
  - When Settings() is instantiated
  - Then settings.channel_name equals "webui"
  - And settings.channel_max_file_size equals 52428800

## 9. Consistency Notes

- The `specs/BACKLOG.md` lists "MCP Server Integration" and "Claude Code Channel Protocol" as separate items. This spec treats them as a single cohesive feature since they are tightly coupled (a channel IS an MCP server following the channel protocol). Both backlog items will be resolved by this spec.
- The backlog also lists "Web Chat Interface" which depends on this spec's backend. The frontend (htmx-based chat UI) is NOT included in this spec and remains in the backlog. This spec documents that the frontend will use htmx (not vanilla JS or a JS framework) so the WebSocket wire format must be htmx-compatible.
- The channel protocol documentation references TypeScript/Bun implementations exclusively. This spec adapts the pattern to Python using the Python MCP SDK, which may require using the low-level `mcp.server.lowlevel.Server` class instead of `FastMCP` to access experimental capabilities.
- **Sole channel decision**: This spec explicitly establishes that the MCP channel is the only communication path with Claude Code. No CLI subprocess fallback will be implemented. This is an architectural constraint that affects all future specs: any feature requiring Claude interaction must go through this MCP channel.
- **SQLite persistence boundary**: The database schema (table creation, migrations) is owned by the chat+upload spec. This spec defines only the write path: how MCP channel messages flow into SQLite. The chat+upload spec must define the `messages` table schema that this spec writes to.

## 10. Migration & Implementation Notes

### Suggested Implementation Order

1. **Phase 1: Core Infrastructure**
   - Add `mcp` and `aiosqlite` dependencies to `pyproject.toml`
   - Extend `Settings` class with channel configuration (MOD-005)
   - Create `src/channel_bridge.py` with shared state (client set, broadcast, deliver) and SQLite persistence layer (MOD-007)
   - Write tests for settings, bridge, and SQLite persistence

2. **Phase 2: MCP Channel Server**
   - Create `src/channel.py` with MCP server, stdio transport, tool handlers (MOD-001, MOD-002, MOD-003)
   - Wire tool handlers to channel bridge (which handles SQLite persistence before broadcast/notification)
   - Create `.mcp.json` configuration (FR-NEW-008)
   - Write channel unit tests

3. **Phase 3: FastAPI Integration**
   - Add WebSocket endpoint to `src/api.py` (MOD-004), ensuring wire format is htmx-compatible
   - Add file upload/download endpoints (MOD-006)
   - Add `channel` CLI command to `src/claude_code_webui.py` (FR-NEW-009)
   - Write integration tests

4. **Phase 4: Documentation & Polish**
   - Update CLAUDE.md, README.md, docs/architecture.md
   - Document sole channel architecture, SQLite persistence flow, htmx frontend expectations
   - Run `make check` and ensure >= 80% coverage
   - Manual testing with Claude Code CLI

### Key Implementation Decisions

- **Sole channel architecture**: The MCP channel is the only way the web UI communicates with Claude Code. There is no CLI subprocess fallback. This simplifies the architecture (single communication path) but means the MCP channel must be robust and well-instrumented.
- **Process model**: The MCP server (stdio) and FastAPI server (HTTP/WS) must run in the same Python process to share state (connected WebSocket clients, delivery function, SQLite connection). Use `asyncio` to run both event loops. The MCP `stdio_server` context manager provides the read/write streams; the FastAPI app runs via uvicorn's programmatic API.
- **Low-level vs FastMCP**: Use `mcp.server.lowlevel.Server` (not `FastMCP`) because `FastMCP` does not expose experimental capability registration. The low-level API allows full control over capabilities, tool handlers, and notification emission.
- **SQLite persistence**: Use `aiosqlite` for async-compatible writes. The channel bridge owns the database connection lifecycle. Writes follow persist-then-deliver ordering, but persistence failures must not block the real-time path (log-and-continue). The database schema is defined by the chat+upload spec; this spec only writes to it.
- **htmx frontend**: The WebSocket wire format must be compatible with htmx's `hx-ws` extension. Messages broadcast from the server will be consumed by htmx for DOM swaps. The backend does not serve the htmx frontend (that is in the chat+upload spec) but must ensure wire format compatibility.
- **Testing MCP without Claude Code**: Unit tests must mock the MCP transport layer. The channel bridge module isolates the shared state so it can be tested independently of MCP or FastAPI. SQLite tests use in-memory databases (`:memory:`).

### Development Testing

To test locally without publishing as a plugin:
```bash
claude --dangerously-load-development-channels server:webui
```

This requires the `.mcp.json` file to be in the project root with the correct command to start the channel server.

## 11. Open Questions & TBDs

1. **Python MCP SDK experimental capabilities**: The exact API for declaring `experimental` capabilities in `mcp.server.lowlevel.Server` needs verification against the current SDK version. The TypeScript SDK uses `capabilities: { experimental: { "claude/channel": {} } }` in the constructor, but the Python equivalent may differ. This must be validated during implementation.

2. **Process architecture trade-offs**: Running MCP stdio and FastAPI HTTP in the same process is the simplest approach for shared state, but may complicate deployment (the process is spawned by Claude Code, not by the user). An alternative is IPC between separate processes (e.g., Unix socket, shared file). The implementer must validate that the single-process approach works when Claude Code spawns the server.

3. **Permission relay**: The channel protocol supports optional permission relay (`claude/channel/permission` capability) for remote tool approval. This is explicitly deferred and NOT included in this spec. It can be added later as a separate change spec.

4. **SQLite schema coordination**: The exact table schema (column names, types, constraints) must be defined by the chat+upload spec before this spec can be fully implemented. The channel bridge's persistence layer depends on that schema. If the chat+upload spec is not yet written, the implementer must define a minimal `messages` table and document it for the chat+upload spec to adopt or supersede.

5. **htmx WebSocket extension wire format**: The htmx `hx-ws` extension expects HTML fragments by default for DOM swaps, but can also handle JSON with custom JavaScript. The exact wire format (JSON vs HTML fragments) must be coordinated with the chat+upload spec that defines the frontend. This spec assumes JSON wire format, which the htmx frontend will interpret via a small client-side handler.
