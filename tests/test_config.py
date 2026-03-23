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
    assert settings.oauth2_enabled is False


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that settings can be overridden via environment variables."""
    monkeypatch.setenv("CCWEBUI_APP_NAME", "test_app")
    monkeypatch.setenv("CCWEBUI_DEBUG", "true")
    monkeypatch.setenv("CCWEBUI_UPLOAD_DIR", "/tmp/test_uploads")
    monkeypatch.setenv("CCWEBUI_MAX_UPLOAD_SIZE_MB", "25")
    monkeypatch.setenv("CCWEBUI_DATABASE_PATH", "/tmp/test.db")
    monkeypatch.setenv("CCWEBUI_MAX_HISTORY_MESSAGES", "50")
    monkeypatch.setenv("CCWEBUI_CHANNEL_NAME", "custom")
    monkeypatch.setenv("CCWEBUI_OAUTH2_ENABLED", "true")
    monkeypatch.setenv("CCWEBUI_OAUTH2_CLIENT_ID", "test_client_id")
    monkeypatch.setenv("CCWEBUI_OAUTH2_CLIENT_SECRET", "test_secret")
    monkeypatch.setenv("CCWEBUI_OAUTH2_ALLOWED_ORIGINS", '["http://localhost:8080"]')
    monkeypatch.setenv("CCWEBUI_SESSION_SECRET_KEY", "test_session_secret_key_32chars!")
    monkeypatch.setenv("CCWEBUI_OAUTH2_ALLOWED_EMAILS", '["admin@test.com"]')
    settings = Settings()
    assert settings.app_name == "test_app"
    assert settings.debug is True
    assert settings.upload_dir == "/tmp/test_uploads"
    assert settings.max_upload_size_mb == 25
    assert settings.database_path == "/tmp/test.db"
    assert settings.max_history_messages == 50
    assert settings.channel_name == "custom"
    assert settings.oauth2_enabled is True
    assert settings.oauth2_client_id == "test_client_id"


def test_oauth2_enabled_missing_fields_raises() -> None:
    """E2E-NEW-011: Missing OAuth2 config with enabled=True fails at startup."""
    with pytest.raises(Exception, match="required settings are missing"):
        Settings(oauth2_enabled=True)


def test_oauth2_loaded_from_yaml(tmp_path: pytest.TempPathFactory) -> None:
    """OAuth2 settings loaded from YAML file."""
    yaml_file = tmp_path / "oauth2.yaml"  # type: ignore[operator]
    yaml_file.write_text(
        "enabled: true\n"
        "client_id: yaml_client\n"
        "client_secret: yaml_secret\n"
        "allowed_origins:\n"
        "  - http://localhost:8080\n"
        "session_secret_key: yaml_session_key_long_enough_32ch\n"
        "allowed_emails:\n"
        "  - admin@test.com\n"
    )
    settings = Settings(oauth2_yaml_path=str(yaml_file))
    assert settings.oauth2_enabled is True
    assert settings.oauth2_client_id == "yaml_client"
    assert settings.oauth2_client_secret == "yaml_secret"
    assert settings.oauth2_allowed_emails == ["admin@test.com"]
