# Web Chat Interface & File Upload -- Change Specification

> Generated on: 2026-03-22
> Project: claude-code-webui
> Version: 2.0
> Status: Draft
> Type: Change Specification

## 1. Change Summary

Add a web chat interface and file upload capability to the claude-code-webui project. The project currently has a FastAPI backend with only a health endpoint and no frontend. These changes introduce the core user-facing functionality: a conversational chat UI (built with htmx) where users interact with Claude via the MCP channel protocol, file upload integration so users can attach files to their conversations, and SQLite-backed conversation persistence.

### Modifications Overview

| MOD ID  | Type | Title                          | Priority   |
|---------|------|--------------------------------|------------|
| MOD-001 | Add  | Chat Backend (WebSocket API)   | Must-have  |
| MOD-002 | Add  | Chat Frontend (htmx Web UI)    | Must-have  |
| MOD-004 | Add  | File Upload Backend            | Must-have  |
| MOD-005 | Add  | File Upload Frontend           | Must-have  |
| MOD-006 | Add  | Conversation History (SQLite)  | Must-have  |

## 2. Current State Analysis

### 2.1 Project Overview

claude-code-webui is a Python 3.13 project using FastAPI, Typer CLI, OpenTelemetry tracing, and pydantic-settings for configuration. The project is scaffolded but minimal:

- **CLI** (`src/claude_code_webui.py`): Typer app with a `serve` command that starts the FastAPI server via uvicorn.
- **API** (`src/api.py`): FastAPI app with a single `/health` endpoint. OTel instrumentation is wired via `FastAPIInstrumentor`.
- **Config** (`src/config.py`): `Settings` class with `CCWEBUI_` env prefix. Fields: `app_name`, `debug`, `host`, `port`.
- **Logging** (`src/logging_config.py`): Rich console handler + file handler.
- **Tracing** (`src/tracing.py`): JSONL file exporter for OTel spans, plus a `trace_span` context manager.
- **Tests**: Unit tests for config and tracing; one functional test for the health endpoint using `httpx.AsyncClient` with ASGI transport.

There is no frontend, no Claude integration, no file handling, and no WebSocket support.

### 2.2 Existing Specifications

- `specs/BACKLOG.md`: Lists five backlog items including Web Chat Interface, MCP Server Integration, Claude Code Channel Protocol, File Upload, and OAuth2 Authentication. This spec addresses the Web Chat Interface and File Upload items.

### 2.3 Relevant Architecture

- **FastAPI app factory**: `create_app(settings)` in `api.py` creates the application with lifespan context manager and OTel.
- **Settings pattern**: All config via `pydantic-settings` with `CCWEBUI_` prefix.
- **Module layout**: All source in `src/`, flat structure (no packages), modules imported by name.
- **Test pattern**: `tests/` for unit, `tests/functional/` for integration. Async tests with `pytest-asyncio`, `httpx.AsyncClient` + `ASGITransport`.
- **Dependencies**: FastAPI, uvicorn, httpx, pydantic, OTel, typer, rich.
- **Communication with Claude**: Claude Code spawns this application as an MCP server. Communication with Claude is handled via the MCP channel protocol (see backlog items "MCP Server Integration" and "Claude Code Channel Protocol"). This spec does NOT implement the MCP channel; it references it as the communication layer and focuses on the web UI and file upload features.

## 3. Requested Modifications

### MOD-001: Chat Backend (WebSocket API)

- **Type:** Add
- **Description:** Add a WebSocket endpoint (`/ws/chat`) that accepts user messages and streams Claude's responses back in real time. The endpoint must handle connection lifecycle (open, message, close, error).
- **Rationale:** WebSocket enables real-time bidirectional communication for a responsive chat experience. Streaming responses gives users immediate feedback as Claude generates output.
- **Priority:** Must-have
- **Details:**
  - **Input**: JSON messages over WebSocket with structure `{"type": "user_message", "content": "...", "conversation_id": "...", "attachments": [{"file_id": "..."}]}`
  - **Output**: JSON messages streamed back: `{"type": "assistant_chunk", "content": "...", "conversation_id": "..."}` for streaming, `{"type": "assistant_complete", "content": "...", "conversation_id": "..."}` when done, and `{"type": "error", "detail": "..."}` for errors.
  - **Connection protocol**: On connect, server sends `{"type": "connected", "conversation_id": "..."}`. Client sends user messages. Server streams responses.
  - **Conversation ID**: Client may send an existing `conversation_id` to continue a conversation, or omit it to start a new one.
  - **Claude communication**: The WebSocket handler delegates message processing to the MCP channel layer (separate spec). This spec defines the WebSocket API contract; the MCP channel spec defines how messages reach Claude and responses come back.

### MOD-002: Chat Frontend (htmx Web UI)

- **Type:** Add
- **Description:** Add a single-page chat interface built with htmx, served by FastAPI. Clean, modern layout with a message list, input area, and send button. htmx handles reactivity (partial page updates, WebSocket integration) without a build step.
- **Rationale:** This is the primary user-facing feature of the project. htmx provides clean interactivity (partial DOM updates, WebSocket binding, form handling) while keeping the frontend simple: no build toolchain, no npm, just HTML attributes.
- **Priority:** Must-have
- **Details:**
  - Served at `/` (root route) as HTML templates rendered by FastAPI (Jinja2 templates with htmx attributes).
  - **htmx integration**: Use htmx for WebSocket connections (`hx-ws`), form submissions, file upload progress, and partial DOM updates. Include htmx via CDN `<script>` tag (no build step).
  - **Layout**: Full-height chat container with a scrollable message area and a fixed-bottom input bar.
  - **Message display**: User messages right-aligned, assistant messages left-aligned. Markdown rendering for assistant responses (code blocks, bold, italics, lists).
  - **Streaming**: Assistant responses must appear incrementally as chunks arrive via WebSocket. htmx's WebSocket extension (`ws`) handles the connection; the server sends HTML fragments that htmx swaps into the DOM.
  - **Input**: Text area (multi-line with Shift+Enter for newline, Enter to send). Send button. File attachment button (triggers file upload).
  - **Conversation management**: New conversation button. Conversation list sidebar (optional, can be deferred if complex).
  - **Responsive**: Must work on desktop and tablet. Mobile is nice-to-have.
  - **No build step**: htmx loaded from CDN. Minimal inline JS only where htmx attributes are insufficient (e.g., Markdown rendering via `marked.js` from CDN). Templates in `src/templates/` directory.

### MOD-004: File Upload Backend

- **Type:** Add
- **Description:** Add a REST endpoint (`POST /api/files/upload`) that accepts file uploads, stores them on the server filesystem, and returns a file ID that can be referenced in chat messages.
- **Rationale:** Users need to share files with Claude for code review, analysis, and other file-dependent tasks.
- **Priority:** Must-have
- **Details:**
  - **Input**: Multipart form upload with one or more files.
  - **Output**: JSON response `{"files": [{"file_id": "...", "filename": "...", "size": ..., "content_type": "..."}]}`
  - **Storage**: Files stored in a configurable upload directory (new `Settings` field: `upload_dir`, default `./uploads`). Directory created on startup if it does not exist.
  - **File ID**: UUID4-based, stored as `<upload_dir>/<file_id>/<original_filename>` to preserve the original name.
  - **Validation**:
    - Maximum file size: configurable via `Settings.max_upload_size_mb` (default: 10 MB).
    - Allowed file types: text files, code files, images, PDFs, common document formats. Configurable via `Settings.allowed_upload_extensions` (default: a reasonable list).
    - Reject empty files.
  - **Cleanup**: No automatic cleanup in this spec. Files persist until manually deleted or server restart. Cleanup can be a future enhancement.
  - **OTel**: Trace file upload operations (`file.upload`).

### MOD-005: File Upload Frontend

- **Type:** Add
- **Description:** Integrate file upload into the chat UI using htmx. Users can click an attachment button, select files, see upload progress, and the uploaded files are attached to their next message.
- **Rationale:** Seamless file attachment is essential for a good chat UX with Claude.
- **Priority:** Must-have
- **Details:**
  - Attachment button (paperclip icon) next to the message input.
  - Click opens a native file picker (accepts the same extensions as the backend).
  - Selected files are uploaded immediately via `POST /api/files/upload` using htmx (`hx-post`, `hx-encoding="multipart/form-data"`). The server returns an HTML fragment with the file chip that htmx swaps into the attachment area.
  - Upload progress indicator shown below the input area (htmx `hx-indicator` or `htmx:xhr:progress` event).
  - Uploaded files shown as chips/tags (filename + remove button) in the input area.
  - When the user sends a message, the `file_id`s of attached files are included in the WebSocket message.
  - Drag-and-drop file upload onto the chat area (nice-to-have, but straightforward to implement with the same upload flow).

### MOD-006: Conversation History (SQLite)

- **Type:** Add
- **Description:** Persist conversation history in a SQLite database using `aiosqlite` for async access. Conversations, messages, and file metadata are stored durably across server restarts.
- **Rationale:** Claude needs conversation context to provide coherent multi-turn responses. SQLite persistence ensures conversations survive server restarts and avoids memory pressure from in-memory storage.
- **Priority:** Must-have
- **Details:**
  - **Database location**: Configurable via `Settings.database_path` (default: `./data/ccwebui.db`). Directory created on startup if it does not exist.
  - **Schema**:
    - `conversations` table: `id` (TEXT PRIMARY KEY, UUID4), `title` (TEXT, nullable, auto-generated from first message), `created_at` (TEXT, ISO 8601), `updated_at` (TEXT, ISO 8601).
    - `messages` table: `id` (TEXT PRIMARY KEY, UUID4), `conversation_id` (TEXT, FK to conversations.id), `role` (TEXT, "user" or "assistant"), `content` (TEXT), `created_at` (TEXT, ISO 8601). Index on `conversation_id`.
    - `files` table: `id` (TEXT PRIMARY KEY, UUID4, same as file_id), `message_id` (TEXT, FK to messages.id, nullable for files uploaded but not yet sent), `filename` (TEXT), `size` (INTEGER), `content_type` (TEXT), `storage_path` (TEXT), `created_at` (TEXT, ISO 8601). Index on `message_id`.
  - **Database initialization**: Schema created via `CREATE TABLE IF NOT EXISTS` on application startup (in the FastAPI lifespan).
  - **Async access**: All database operations use `aiosqlite` (async context manager pattern).
  - **Repository pattern**: New module `src/database.py` with a `Database` class providing methods: `create_conversation()`, `get_conversation()`, `list_conversations()`, `add_message()`, `get_messages(conversation_id)`, `add_file()`, `get_file()`, `get_files_for_message()`.
  - **History retrieval**: When Claude needs conversation context, retrieve messages ordered by `created_at` for the given `conversation_id`.
  - **Maximum history for Claude context**: Configurable via `Settings.max_history_messages` (default: 100). When sending context to Claude, only the last N messages are included. All messages remain in the database.
  - **OTel**: Trace database operations (`db.query`, `db.insert`).

## 4. Impact Analysis

### 4.1 Affected Components

| File/Module | Impact Type | Description |
|-------------|-------------|-------------|
| `src/api.py` | Modified | Add WebSocket endpoint, file upload endpoint, serve htmx templates, inject database dependency |
| `src/config.py` | Modified | Add new settings: `upload_dir`, `max_upload_size_mb`, `allowed_upload_extensions`, `max_history_messages`, `database_path` |
| `src/database.py` | New | SQLite database layer with aiosqlite, repository pattern |
| `src/chat.py` | New | WebSocket chat handler, message models |
| `src/file_upload.py` | New | File upload handling, validation, storage |
| `src/templates/index.html` | New | Chat frontend (htmx + Jinja2 template) |
| `src/templates/partials/` | New | htmx partial templates (message fragments, file chips, conversation list items) |
| `src/claude_code_webui.py` | Minor | No changes expected (CLI just starts uvicorn) |
| `src/logging_config.py` | No change | Existing logging works for new modules |
| `src/tracing.py` | No change | `trace_span` used by new modules |
| `pyproject.toml` | Modified | Add `python-multipart`, `websockets`, `aiosqlite`, `jinja2` dependencies |

### 4.2 Affected Requirements

No existing formal specifications exist (only `specs/BACKLOG.md`). The backlog items "Web Chat Interface" and "File Upload" will be addressed by this spec. The backlog items "MCP Server Integration", "Claude Code Channel Protocol", and "OAuth2 Authentication" are NOT addressed and remain in the backlog.

### 4.3 Affected Tests

| Test File | Test ID/Name | Action | Description |
|-----------|-------------|--------|-------------|
| `tests/functional/test_api.py` | `test_health_endpoint` | No change | Existing health check remains valid |
| `tests/test_config.py` | `test_default_settings` | Modified | Must verify new settings fields have correct defaults |
| `tests/test_config.py` | `test_settings_from_env` | Modified | Must verify new settings fields can be overridden via env |
| `tests/functional/test_chat.py` | New | New | WebSocket chat endpoint tests |
| `tests/functional/test_file_upload.py` | New | New | File upload endpoint tests |
| `tests/test_database.py` | New | New | SQLite database layer tests |
| `tests/test_chat.py` | New | New | Chat models and message handling tests |
| `tests/test_file_upload.py` | New | New | File validation and storage tests |

### 4.4 Affected Documentation

| Document | Section | Action | Description |
|----------|---------|--------|-------------|
| `CLAUDE.md` | Project Structure | Modified | Add new modules to the structure list |
| `CLAUDE.md` | Conventions | Modified | Add WebSocket, htmx, and database conventions |
| `README.md` | Project Structure | Modified | Add new modules |
| `README.md` | Configuration | Modified | Document new settings |
| `README.md` | Quick Start | Modified | Mention accessing the chat UI in browser |
| `.agent_docs/python.md` | No change | -- | Existing coding standards apply |
| `.agent_docs/makefile.md` | No change | -- | No Makefile changes needed |

### 4.5 Dependencies & Risks

**New dependencies:**
- `python-multipart` (required by FastAPI for file upload parsing)
- `websockets` (required by uvicorn/FastAPI for WebSocket support)
- `aiosqlite` (async SQLite access)
- `jinja2` (template rendering for htmx partials)

**Risks:**
- **MCP channel not yet implemented**: The chat backend depends on the MCP channel protocol (separate spec) to communicate with Claude. Until that spec is implemented, the chat backend must use a pluggable interface (protocol/abstract class) with a stub/mock implementation for development and testing.
- **File storage**: Storing uploads on the local filesystem means files are lost if the server moves or the container is recreated. Acceptable for initial version.
- **No authentication**: Without OAuth2 (backlog item), anyone who can reach the server can use it. The server must only bind to localhost in non-production scenarios, or rely on network-level security.
- **SQLite concurrency**: SQLite supports concurrent reads but serializes writes. For a single-user or low-concurrency scenario this is fine. If high concurrency is needed, migration to PostgreSQL can be a future enhancement.
- **htmx CDN dependency**: The frontend requires loading htmx from a CDN. If offline use is needed, the htmx library can be vendored as a static file.

**Rollback strategy:** All changes are additive. The existing `/health` endpoint is unaffected. Rollback is simply reverting the commits. SQLite database file can be deleted to reset state.

## 5. New & Modified Requirements

### New Requirements

#### FR-NEW-001: WebSocket Chat Endpoint

- **Description:** The system must expose a WebSocket endpoint at `/ws/chat` that accepts user messages as JSON and streams Claude's responses back as JSON chunks.
- **Inputs:** JSON: `{"type": "user_message", "content": "string", "conversation_id": "string|null", "attachments": [{"file_id": "string"}]}`
- **Outputs:** JSON stream: `connected`, `assistant_chunk`, `assistant_complete`, `error` message types.
- **Business Rules:**
  - If `conversation_id` is null or missing, create a new conversation and return the ID in the `connected` message.
  - If `conversation_id` is provided but not found in the database, return an error message.
  - Messages with empty `content` and no `attachments` must be rejected with an error.
  - The WebSocket must remain open for the duration of the conversation session.
  - Message processing is delegated to the MCP channel layer (separate spec). This endpoint defines the WebSocket contract only.
- **Priority:** Must-have

#### FR-NEW-002: Chat Frontend (htmx)

- **Description:** The system must serve a chat interface at the root URL (`/`) built with htmx and Jinja2 templates, with message display, text input, and file attachment.
- **Inputs:** User interaction (typing, clicking, file selection).
- **Outputs:** Rendered HTML page with real-time chat via WebSocket (htmx `hx-ws`).
- **Business Rules:**
  - Assistant messages must render Markdown (code blocks, inline code, bold, italics, lists, links).
  - Messages must appear in chronological order.
  - The chat area must auto-scroll to the latest message.
  - Streaming assistant responses must be visible as they arrive. The server sends HTML fragments; htmx swaps them into the message area.
  - The send button and Enter key must be disabled while a response is being generated.
  - htmx must be loaded from CDN (`<script>` tag). No build step, no npm.
  - Templates stored in `src/templates/` with partials in `src/templates/partials/`.
- **Priority:** Must-have

#### FR-NEW-003: MCP Channel Interface (Stub)

- **Description:** The system must define a protocol/abstract class for the Claude communication layer. A stub implementation must be provided for development and testing. The real implementation will come from the MCP channel spec.
- **Inputs:** User message string, conversation history (list of messages), list of file paths (for attachments).
- **Outputs:** Async generator yielding response text chunks.
- **Business Rules:**
  - The interface must define: `async def send_message(message, history, file_paths) -> AsyncGenerator[str, None]`.
  - The stub implementation must return a fixed response (e.g., echo the user message or return a placeholder).
  - The interface must be injectable into the FastAPI app (dependency injection via lifespan).
  - All invocations must be traced with OTel spans.
- **Priority:** Must-have

#### FR-NEW-004: File Upload Endpoint

- **Description:** The system must expose `POST /api/files/upload` that accepts multipart file uploads, validates them, stores them on disk, and returns file metadata.
- **Inputs:** Multipart form data with one or more files.
- **Outputs:** JSON: `{"files": [{"file_id": "uuid", "filename": "string", "size": int, "content_type": "string"}]}`
- **Business Rules:**
  - Reject files exceeding `max_upload_size_mb` (422 response).
  - Reject files with disallowed extensions (422 response).
  - Reject empty files (422 response).
  - Store each file as `<upload_dir>/<file_id>/<original_filename>`.
  - Create `upload_dir` on application startup if it does not exist.
  - Record file metadata in the SQLite `files` table.
  - Return 201 on success.
  - Trace each upload with OTel span (`file.upload`).
- **Priority:** Must-have

#### FR-NEW-005: File Attachment in Chat

- **Description:** The chat frontend must allow users to attach uploaded files to messages, and the backend must pass those files to the MCP channel layer.
- **Inputs:** File IDs included in WebSocket message `attachments` array.
- **Outputs:** Files resolved to filesystem paths and passed to the MCP channel interface.
- **Business Rules:**
  - If a referenced `file_id` does not exist in the database or on disk, return an error for that specific file but do not reject the entire message (warn and continue without that file).
  - The frontend must display attached files as removable chips in the input area (rendered as htmx-swappable HTML fragments).
  - Multiple files can be attached to a single message.
  - When a message is sent, file records in the database are linked to the message via `message_id`.
- **Priority:** Must-have

#### FR-NEW-006: Conversation History (SQLite Persistence)

- **Description:** The system must persist per-conversation message history in a SQLite database for multi-turn Claude interactions and cross-restart durability.
- **Inputs:** Messages exchanged over WebSocket.
- **Outputs:** Conversation context passed to the MCP channel interface.
- **Business Rules:**
  - Conversations stored in `conversations` table with UUID4 `id`, `title`, `created_at`, `updated_at`.
  - Messages stored in `messages` table with UUID4 `id`, `conversation_id` (FK), `role`, `content`, `created_at`.
  - Files stored in `files` table with UUID4 `id`, `message_id` (FK), `filename`, `size`, `content_type`, `storage_path`, `created_at`.
  - Schema created via `CREATE TABLE IF NOT EXISTS` on application startup.
  - All database access via `aiosqlite` (async).
  - When building context for Claude, include at most `max_history_messages` most recent messages (configurable, default 100).
  - Conversation `title` auto-generated from the first user message (first 50 characters).
  - Conversation `updated_at` refreshed on every new message.
- **Priority:** Must-have

#### FR-NEW-007: Database Repository

- **Description:** The system must provide a `Database` class in `src/database.py` encapsulating all SQLite operations behind a clean async interface.
- **Inputs:** Method calls from chat and file upload handlers.
- **Outputs:** Data objects (conversations, messages, files).
- **Business Rules:**
  - Methods: `init_schema()`, `create_conversation()`, `get_conversation(id)`, `list_conversations()`, `add_message(conversation_id, role, content)`, `get_messages(conversation_id, limit)`, `add_file(file_id, filename, size, content_type, storage_path)`, `link_file_to_message(file_id, message_id)`, `get_file(file_id)`, `get_files_for_message(message_id)`.
  - `init_schema()` called during FastAPI lifespan startup.
  - Database instance injected into the FastAPI app (not created inline).
  - All methods must be traced with OTel spans.
- **Priority:** Must-have

### Modified Requirements

#### FR-MOD-001: Settings (references `config.py`)

- **Original behavior:** Settings has 4 fields: `app_name`, `debug`, `host`, `port`.
- **New behavior:** Settings gains additional fields: `upload_dir` (str, default `"./uploads"`), `max_upload_size_mb` (int, default `10`), `allowed_upload_extensions` (list[str], default common text/code/doc extensions), `max_history_messages` (int, default `100`), `database_path` (str, default `"./data/ccwebui.db"`).
- **Reason for change:** New features require configuration.
- **Business Rules:** All new fields must be overridable via `CCWEBUI_` environment variables.

### Removed Requirements

None.

## 6. Non-Functional Requirements Changes

#### NFR-001: Response Latency

- **Description:** The first chunk of Claude's streaming response must appear in the UI within 3 seconds of sending a message (assuming the MCP channel responds within that time). The WebSocket and service layers must not add more than 200ms of overhead.
- **Priority:** Must-have

#### NFR-002: File Upload Size

- **Description:** File upload endpoint must reject oversized files early (before reading the entire body into memory) using FastAPI's file size handling.
- **Priority:** Should-have

#### NFR-003: Observability

- **Description:** All new operations (WebSocket connections, database queries, file uploads) must produce OTel spans following the existing `category.operation` naming convention.
- **Priority:** Must-have

#### NFR-004: Security

- **Description:** File uploads must be validated (extension whitelist, size limit). The upload directory must not be directly browsable. Filenames must be sanitized to prevent path traversal.
- **Priority:** Must-have

#### NFR-005: Database Durability

- **Description:** SQLite database must use WAL (Write-Ahead Logging) mode for improved concurrent read performance and crash resilience. Database file location must be configurable.
- **Priority:** Must-have

## 7. Documentation Updates

All documentation changes listed below MUST be implemented as part of this change.

### 7.1 CLAUDE.md & .agent_docs/

- **CLAUDE.md Project Structure**: Add `src/database.py`, `src/chat.py`, `src/file_upload.py`, `src/templates/index.html`, `src/templates/partials/` to the structure list.
- **CLAUDE.md Conventions**: Add: "WebSocket handlers in `chat.py`, file operations in `file_upload.py`, database access in `database.py`. Frontend uses htmx templates in `src/templates/`. No inline SQL outside `database.py`."
- **CLAUDE.md Documentation Index**: Add links to any new `.agent_docs/` files if created.

### 7.2 docs/*

No existing docs files to update. If `docs/` contains architecture or usage docs, add a section on the chat and file upload features.

### 7.3 README.md

- **Quick Start**: Add step: "Open http://localhost:8080 in your browser to start chatting."
- **Project Structure**: Add new files to the tree diagram.
- **Configuration**: Add table rows for all new `CCWEBUI_` settings (`upload_dir`, `max_upload_size_mb`, `allowed_upload_extensions`, `max_history_messages`, `database_path`).
- **Features section**: Add a new "Features" section listing chat, file upload, and conversation persistence capabilities.

## 8. End-to-End Test Updates

All test changes MUST be implemented in the `tests/` directory. Every modification MUST have tests covering happy paths, failure paths, edge cases, and error recovery.

### 8.1 Test Summary

| Test ID | Action | Category | Scenario | Priority |
|---------|--------|----------|----------|----------|
| E2E-NEW-001 | New | Core Journey | Send message and receive response via WebSocket | Critical |
| E2E-NEW-002 | New | Core Journey | Multi-turn conversation maintains context | Critical |
| E2E-NEW-003 | New | Feature | Upload file successfully | Critical |
| E2E-NEW-004 | New | Error | Upload oversized file rejected | High |
| E2E-NEW-005 | New | Error | Upload disallowed extension rejected | High |
| E2E-NEW-006 | New | Feature | Send message with file attachment | High |
| E2E-NEW-007 | New | Error | WebSocket message with empty content rejected | High |
| E2E-NEW-008 | New | Error | Reference non-existent file_id in attachment | Medium |
| E2E-NEW-009 | New | Feature | Chat frontend serves at root URL | High |
| E2E-NEW-010 | New | Core Journey | Conversation persists across simulated restart | Critical |
| E2E-NEW-011 | New | Feature | List conversations from database | High |
| E2E-NEW-012 | New | Edge | Conversation history truncation for Claude context | Medium |
| E2E-NEW-013 | New | Error | Upload empty file rejected | Medium |
| E2E-NEW-014 | New | Feature | Multiple file upload in single request | Medium |
| E2E-NEW-015 | New | Feature | Database schema initialization (idempotent) | High |
| E2E-NEW-016 | New | Feature | File metadata recorded in database | High |
| E2E-NEW-017 | New | Feature | Conversation title auto-generated from first message | Medium |
| E2E-MOD-001 | Modified | Feature | Default settings include new fields | High |
| E2E-MOD-002 | Modified | Feature | Settings overridable via env for new fields | High |

### 8.2 New Tests

#### E2E-NEW-001: WebSocket Chat Send and Receive

- **Category:** Core Journey
- **Modification:** MOD-001
- **Preconditions:** FastAPI test app running, MCP channel stub returning a fixed response.
- **Steps:**
  - Given a WebSocket connection to `/ws/chat`
  - When the client sends `{"type": "user_message", "content": "Hello"}`
  - Then the server sends `{"type": "connected", "conversation_id": "..."}` on connect
  - And the server streams one or more `{"type": "assistant_chunk", "content": "..."}` messages
  - And the server sends `{"type": "assistant_complete", "content": "...", "conversation_id": "..."}`
- **Priority:** Critical

#### E2E-NEW-002: Multi-Turn Conversation

- **Category:** Core Journey
- **Modification:** MOD-001, MOD-006
- **Preconditions:** FastAPI test app running, MCP channel stub configured.
- **Steps:**
  - Given a WebSocket connection with conversation_id from a previous exchange
  - When the client sends a follow-up message with the same conversation_id
  - Then the MCP channel interface receives the conversation history including the previous exchange
  - And the server returns a response
  - And both messages are persisted in the SQLite database
- **Priority:** Critical

#### E2E-NEW-003: File Upload Success

- **Category:** Feature
- **Modification:** MOD-004
- **Preconditions:** Upload directory exists (or will be created).
- **Steps:**
  - Given a valid text file under the size limit
  - When `POST /api/files/upload` with the file as multipart form data
  - Then response status is 201
  - And response body contains `file_id`, `filename`, `size`, `content_type`
  - And the file exists on disk at `<upload_dir>/<file_id>/<filename>`
  - And the file metadata is recorded in the SQLite `files` table
- **Priority:** Critical

#### E2E-NEW-004: Upload Oversized File Rejected

- **Category:** Error
- **Modification:** MOD-004
- **Preconditions:** `max_upload_size_mb` set to 1.
- **Steps:**
  - Given a file larger than 1 MB
  - When `POST /api/files/upload` with the file
  - Then response status is 422
  - And response body contains an error message about file size
- **Priority:** High

#### E2E-NEW-005: Upload Disallowed Extension Rejected

- **Category:** Error
- **Modification:** MOD-004
- **Preconditions:** Default allowed extensions configured.
- **Steps:**
  - Given a file with extension `.exe`
  - When `POST /api/files/upload` with the file
  - Then response status is 422
  - And response body contains an error message about file type
- **Priority:** High

#### E2E-NEW-006: Send Message with File Attachment

- **Category:** Feature
- **Modification:** MOD-001, MOD-004, MOD-005
- **Preconditions:** A file has been uploaded and a file_id obtained.
- **Steps:**
  - Given a WebSocket connection to `/ws/chat`
  - When the client sends `{"type": "user_message", "content": "Review this file", "attachments": [{"file_id": "<id>"}]}`
  - Then the MCP channel interface receives the file path as context
  - And the server returns a response
  - And the file record in the database is linked to the message
- **Priority:** High

#### E2E-NEW-007: Empty Content Message Rejected

- **Category:** Error
- **Modification:** MOD-001
- **Preconditions:** WebSocket connection established.
- **Steps:**
  - Given a WebSocket connection to `/ws/chat`
  - When the client sends `{"type": "user_message", "content": ""}`
  - Then the server sends `{"type": "error", "detail": "..."}`
- **Priority:** High

#### E2E-NEW-008: Non-Existent File ID in Attachment

- **Category:** Error
- **Modification:** MOD-005
- **Preconditions:** WebSocket connection established.
- **Steps:**
  - Given a WebSocket connection to `/ws/chat`
  - When the client sends a message with `attachments: [{"file_id": "nonexistent-uuid"}]`
  - Then the server sends a warning about the missing file
  - And the message is still processed (without the missing attachment)
- **Priority:** Medium

#### E2E-NEW-009: Chat Frontend Served at Root

- **Category:** Feature
- **Modification:** MOD-002
- **Preconditions:** FastAPI test app running.
- **Steps:**
  - Given the server is running
  - When `GET /`
  - Then response status is 200
  - And response content-type is `text/html`
  - And the body contains htmx script tag and essential chat UI elements (message input, send button)
- **Priority:** High

#### E2E-NEW-010: Conversation Persists Across Restart

- **Category:** Core Journey
- **Modification:** MOD-006
- **Preconditions:** SQLite database with an existing conversation.
- **Steps:**
  - Given a conversation with messages was created and stored in the database
  - When a new Database instance is created against the same database file
  - Then `get_conversation(id)` returns the conversation
  - And `get_messages(conversation_id)` returns the previously stored messages
- **Priority:** Critical

#### E2E-NEW-011: List Conversations

- **Category:** Feature
- **Modification:** MOD-006
- **Preconditions:** SQLite database with multiple conversations.
- **Steps:**
  - Given three conversations exist in the database
  - When `list_conversations()` is called
  - Then all three conversations are returned, ordered by `updated_at` descending
- **Priority:** High

#### E2E-NEW-012: Conversation History Truncation for Claude Context

- **Category:** Edge
- **Modification:** MOD-006
- **Preconditions:** `max_history_messages` set to 2.
- **Steps:**
  - Given a conversation with 5 messages in the database
  - When `get_messages(conversation_id, limit=2)` is called
  - Then only the 2 most recent messages are returned
  - And all 5 messages remain in the database
- **Priority:** Medium

#### E2E-NEW-013: Empty File Upload Rejected

- **Category:** Error
- **Modification:** MOD-004
- **Steps:**
  - Given an empty file (0 bytes)
  - When `POST /api/files/upload` with the file
  - Then response status is 422
- **Priority:** Medium

#### E2E-NEW-014: Multiple File Upload

- **Category:** Feature
- **Modification:** MOD-004
- **Steps:**
  - Given two valid files
  - When `POST /api/files/upload` with both files
  - Then response status is 201
  - And response body contains two file entries with distinct file_ids
  - And both files are recorded in the database
- **Priority:** Medium

#### E2E-NEW-015: Database Schema Initialization (Idempotent)

- **Category:** Feature
- **Modification:** MOD-006
- **Steps:**
  - Given a fresh SQLite database file
  - When `init_schema()` is called twice
  - Then no error occurs (CREATE TABLE IF NOT EXISTS is idempotent)
  - And all three tables (conversations, messages, files) exist
- **Priority:** High

#### E2E-NEW-016: File Metadata in Database

- **Category:** Feature
- **Modification:** MOD-004, MOD-006
- **Steps:**
  - Given a file was uploaded successfully
  - When `get_file(file_id)` is called
  - Then the returned record contains the correct filename, size, content_type, and storage_path
- **Priority:** High

#### E2E-NEW-017: Conversation Title Auto-Generated

- **Category:** Feature
- **Modification:** MOD-006
- **Steps:**
  - Given a new conversation is created
  - When the first user message "Please help me review this Python code for security issues" is added
  - Then the conversation title is set to "Please help me review this Python code for se" (first 50 chars)
- **Priority:** Medium

### 8.3 Modified Tests

#### E2E-MOD-001: Default Settings Include New Fields (was `test_default_settings`)

- **Original test:** Verified 4 default settings fields.
- **Modified to validate:** Also verify defaults for `upload_dir`, `max_upload_size_mb`, `allowed_upload_extensions`, `max_history_messages`, `database_path`.
- **Steps:**
  - Given default `Settings()`
  - When reading new fields
  - Then `upload_dir` is `"./uploads"`, `max_upload_size_mb` is `10`, `database_path` is `"./data/ccwebui.db"`, etc.

#### E2E-MOD-002: Settings Override via Env for New Fields (was `test_settings_from_env`)

- **Original test:** Verified `app_name` and `debug` overridable.
- **Modified to validate:** Also verify new fields overridable via `CCWEBUI_UPLOAD_DIR`, `CCWEBUI_MAX_UPLOAD_SIZE_MB`, `CCWEBUI_DATABASE_PATH`, etc.
- **Steps:**
  - Given env vars set for new fields
  - When creating `Settings()`
  - Then new field values match env vars

### 8.4 Removed Tests

None.

## 9. Consistency Notes

- **MOD-003 removed (Claude CLI Integration)**: The original spec included a `claude_service.py` module that spawned the `claude` CLI as a subprocess. This has been removed. The architecture decision is that Claude Code spawns this application as an MCP server; communication with Claude flows through the MCP channel protocol (see backlog items "MCP Server Integration" and "Claude Code Channel Protocol"). This spec defines a stub interface (FR-NEW-003) so that development and testing can proceed independently of the MCP channel implementation.
- **MOD-002 changed to htmx**: The original spec used vanilla HTML/CSS/JS. This has been changed to htmx for cleaner interactivity. htmx is loaded from CDN (no build step), and the server renders HTML fragments for partial updates rather than relying on client-side JSON parsing and DOM manipulation.
- **MOD-006 changed from in-memory to SQLite**: The original spec used an in-memory dictionary with TTL and eviction logic. This has been replaced with SQLite persistence via `aiosqlite`. TTL/eviction logic has been removed; conversations persist indefinitely in the database. The `conversation_ttl_minutes` and related settings have been removed; `database_path` has been added.
- The backlog items "MCP Server Integration" and "Claude Code Channel Protocol" remain unaddressed. The stub interface in FR-NEW-003 will be replaced by the real MCP channel implementation when those specs are completed.
- The backlog item "OAuth2 Authentication" is not addressed. The file upload and chat endpoints will be unauthenticated in this spec.

## 10. Migration & Implementation Notes

### Suggested Implementation Order

1. **Database layer** (MOD-006/FR-NEW-006/FR-NEW-007): Implement `src/database.py` with SQLite schema and repository methods. Add database tests. This is the foundation for persistence.
2. **Config changes** (FR-MOD-001): Add new settings fields. Update config tests.
3. **File upload** (MOD-004): Implement `src/file_upload.py` and the `/api/files/upload` endpoint with database integration. Add file upload tests.
4. **MCP channel stub** (FR-NEW-003): Define the protocol/abstract class and stub implementation. This enables chat development without the real MCP channel.
5. **Chat backend** (MOD-001): Implement `src/chat.py` with the `/ws/chat` WebSocket endpoint. Wire up database persistence and the MCP channel stub. Add chat tests.
6. **Chat frontend** (MOD-002, MOD-005): Create `src/templates/` with htmx-based chat UI and file attachment integration. Add frontend-serving test.
7. **Documentation**: Update CLAUDE.md, README.md.

### Key Technical Decisions

- **htmx over vanilla JS**: htmx provides WebSocket binding (`hx-ws`), partial DOM updates, and form handling via HTML attributes. This eliminates most custom JavaScript while keeping the frontend simple (no build toolchain, no npm). The server renders HTML fragments that htmx swaps into the DOM.
- **SQLite over in-memory**: SQLite provides durability across restarts, eliminates memory pressure concerns, and avoids the complexity of TTL/eviction logic. `aiosqlite` provides async access compatible with the FastAPI async model. WAL mode ensures good read concurrency.
- **MCP channel, not subprocess**: Claude Code spawns this application as an MCP server. The communication layer is defined by the MCP channel protocol (separate spec). This spec defines a stub interface so the web UI can be developed and tested independently.
- **WebSocket over SSE**: WebSocket chosen over Server-Sent Events because it supports bidirectional communication (user can send follow-up messages without a new HTTP request).
- **Jinja2 templates**: htmx works best with server-rendered HTML. Jinja2 is the standard templating engine for FastAPI/Starlette and integrates naturally.

### Feature Flags

None needed. All features are additive and do not affect the existing `/health` endpoint.

## 11. Open Questions & TBDs

1. **MCP channel protocol details**: The exact interface between this web UI and the MCP channel layer will be defined in the MCP channel spec. The stub interface in FR-NEW-003 is a placeholder.
2. **Conversation sidebar**: The spec marks a conversation list sidebar as optional. Decide during implementation whether the MVP includes it or just a "New Conversation" button.
3. **File cleanup policy**: Uploaded files persist indefinitely. A cleanup strategy (cron, max age, max total size) can be added in a future spec.
4. **htmx version**: Pin the htmx CDN URL to a specific version (e.g., htmx 2.x) to avoid unexpected behavior from CDN updates.
5. **SQLite migrations**: The current schema uses `CREATE TABLE IF NOT EXISTS`. If the schema evolves in future specs, a migration strategy (e.g., `alembic` or manual version tracking) will be needed.
6. **Concurrent WebSocket connections**: The current design does not limit how many WebSocket connections can be active simultaneously. This may need a cap for resource management.
