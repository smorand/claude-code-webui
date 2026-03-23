"""Shared test fixtures."""

import pytest


@pytest.fixture(autouse=True)
def _disable_oauth2_yaml(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent tests from loading the real ~/.config/ccwebui/oauth2.yaml."""
    monkeypatch.setenv("CCWEBUI_OAUTH2_YAML_PATH", "/nonexistent/oauth2.yaml")
