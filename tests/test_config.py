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
    assert settings.upload_dir.endswith("/Downloads")
    assert settings.max_upload_size_mb == 10
    assert isinstance(settings.allowed_upload_extensions, list)
    assert ".py" in settings.allowed_upload_extensions
    assert ".txt" in settings.allowed_upload_extensions
    assert settings.max_history_messages == 100
    assert settings.database_path.endswith("/.local/share/ccwebui/ccwebui.db")
    assert settings.log_dir.endswith("/.cache/ccwebui/logs")
    assert settings.channel_name == "webui"
    assert settings.channel_max_file_size == 52_428_800
    assert "webui" in str(settings.channel_state_dir)


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that settings can be overridden via environment variables."""
    monkeypatch.setenv("CCWEBUI_APP_NAME", "test_app")
    monkeypatch.setenv("CCWEBUI_DEBUG", "true")
    monkeypatch.setenv("CCWEBUI_UPLOAD_DIR", "/tmp/test_uploads")
    monkeypatch.setenv("CCWEBUI_MAX_UPLOAD_SIZE_MB", "25")
    monkeypatch.setenv("CCWEBUI_DATABASE_PATH", "/tmp/test.db")
    monkeypatch.setenv("CCWEBUI_MAX_HISTORY_MESSAGES", "50")
    monkeypatch.setenv("CCWEBUI_CHANNEL_NAME", "custom")
    settings = Settings()
    assert settings.app_name == "test_app"
    assert settings.debug is True
    assert settings.upload_dir == "/tmp/test_uploads"
    assert settings.max_upload_size_mb == 25
    assert settings.database_path == "/tmp/test.db"
    assert settings.max_history_messages == 50
    assert settings.channel_name == "custom"
