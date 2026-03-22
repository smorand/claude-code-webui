# Claude Code Web UI

## Overview

Web interface for interacting with Claude Code CLI.

**Tech Stack:** Python 3.13, FastAPI, Typer, Ruff, mypy, pytest, OpenTelemetry, pydantic-settings

## Key Commands

```bash
make sync               # Install dependencies
make run                # Run the CLI (serve command starts the web server)
make run ARGS='serve'   # Start the web UI server
make check              # Full quality gate (lint, format, typecheck, security, tests+coverage)
make docker-build       # Build Docker image
```

## Project Structure

- `src/claude_code_webui.py` : CLI entry point (Typer app with serve command)
- `src/api.py` : FastAPI server with OTel instrumentation
- `src/config.py` : Settings via pydantic-settings (CCWEBUI_ prefix)
- `src/logging_config.py` : Logging setup with rich + file output
- `src/tracing.py` : OpenTelemetry tracing with JSONL export
- `tests/` : Unit tests
- `tests/functional/` : Integration tests (API)

## Conventions

- Entry point in `src/claude_code_webui.py` contains only CLI wiring
- Business logic in separate modules within `src/`
- Use `@dataclass(frozen=True)` for value objects
- All async operations use asyncio patterns
- Logging with `%` formatting, not f-strings
- OTel traces to `<app>-otel.log`, app logs to `<app>.log`

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
