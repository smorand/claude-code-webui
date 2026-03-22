# Backlog

## Features

- [x] **Web Chat Interface**: Web UI to write messages and receive answers from Claude, with a conversational chat experience (see `specs/2026-03-22_20:34:04-web-chat-and-file-upload.md`)
- [x] **File Upload**: Allow users to upload files to the server from the web interface (see `specs/2026-03-22_20:34:04-web-chat-and-file-upload.md`)
- [ ] **MCP Server Integration**: Implement an MCP (Model Context Protocol) server to communicate with Claude (prerequisite for chat functionality; web-chat spec defines a stub interface)
- [ ] **Claude Code Channel Protocol**: Follow the Claude Code channel protocol (plugin:fakechat@claude-plugins-official) for proper plugin communication (prerequisite for chat functionality; web-chat spec defines a stub interface)
- [ ] **OAuth2 Authentication (GCP)**: Implement OAuth2 via Google Cloud Platform for authenticating users on the server
