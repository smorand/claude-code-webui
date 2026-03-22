# Backlog

## Features

- [x] **Web Chat Interface**: Web UI to write messages and receive answers from Claude, with a conversational chat experience (see `specs/2026-03-22_20:34:04-web-chat-and-file-upload.md`)
- [x] **File Upload**: Allow users to upload files to the server from the web interface (see `specs/2026-03-22_20:34:04-web-chat-and-file-upload.md`)
- [x] **MCP Server Integration**: Implement an MCP (Model Context Protocol) server to communicate with Claude (see `specs/2026-03-22_20:35:31-mcp-channel-integration.md`)
- [x] **Claude Code Channel Protocol**: Follow the Claude Code channel protocol (plugin:fakechat@claude-plugins-official) for proper plugin communication (see `specs/2026-03-22_20:35:31-mcp-channel-integration.md`)
- [x] **OAuth2 Authentication (GCP)**: Implement OAuth2 via Google Cloud Platform for authenticating users on the server (see `specs/2026-03-22_20:34:05-add-oauth2-gcp.md`)

## Deferred from Specs

| ID       | Idea                              | Description                                                                                                          | Rationale for Deferral                                           | Source Spec                                    |
|----------|-----------------------------------|----------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------|------------------------------------------------|
| DEFER-001| Permission Relay                  | Support `claude/channel/permission` capability to forward tool approval prompts to the web UI for remote approval    | Adds significant complexity; core two-way chat works without it  | 2026-03-22_20:35:31-mcp-channel-integration.md |
| DEFER-002| Web Chat Frontend                 | HTML/JS chat UI for the browser side of the channel                                                                  | Backend must be implemented first; separate concern               | 2026-03-22_20:35:31-mcp-channel-integration.md |
