"""Tests for the config module."""

import pytest

from config import Settings


def test_default_settings() -> None:
    """Test that default settings are loaded."""
    settings = Settings()
    assert settings.app_name == "claude-code-webui"
    assert settings.debug is False
    assert settings.host == "0.0.0.0"
    assert settings.port == 8080


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that settings can be overridden via environment variables."""
    monkeypatch.setenv("CCWEBUI_APP_NAME", "test_app")
    monkeypatch.setenv("CCWEBUI_DEBUG", "true")
    settings = Settings()
    assert settings.app_name == "test_app"
    assert settings.debug is True
