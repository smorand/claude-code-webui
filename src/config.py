"""Application settings using pydantic-settings."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path.home() / ".config" / "ccwebui"
_DATA_DIR = Path.home() / ".local" / "share" / "ccwebui"
_CACHE_DIR = Path.home() / ".cache" / "ccwebui"
_OAUTH2_YAML = _CONFIG_DIR / "oauth2.yaml"


class Settings(BaseSettings):
    """Application configuration loaded from environment variables.

    Configuration is loaded in order: defaults, config file (~/.config/ccwebui/.env),
    then environment variables (CCWEBUI_ prefix). Environment variables take precedence.
    """

    model_config = SettingsConfigDict(
        env_prefix="CCWEBUI_",
        env_file=str(_CONFIG_DIR / ".env"),
        env_file_encoding="utf-8",
    )

    app_name: str = "claude-code-webui"
    debug: bool = False
    host: str = "0.0.0.0"  # nosec B104
    port: int = 8080

    upload_dir: str = str(Path.home() / "Downloads")
    max_upload_size_mb: int = 10
    allowed_upload_extensions: list[str] = [
        ".txt",
        ".md",
        ".py",
        ".js",
        ".ts",
        ".html",
        ".css",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".cfg",
        ".ini",
        ".xml",
        ".csv",
        ".tsv",
        ".sql",
        ".sh",
        ".bash",
        ".go",
        ".rs",
        ".java",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".rb",
        ".php",
        ".swift",
        ".kt",
        ".scala",
        ".r",
        ".m",
        ".tf",
        ".hcl",
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".webp",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".pptx",
        ".log",
        ".env",
        ".dockerfile",
        ".makefile",
    ]
    max_history_messages: int = 100
    database_path: str = str(_DATA_DIR / "ccwebui.db")
    log_dir: str = str(_CACHE_DIR / "logs")

    oauth2_enabled: bool = False
    oauth2_client_id: str = ""
    oauth2_client_secret: str = ""
    oauth2_allowed_origins: list[str] = []
    oauth2_allowed_emails: list[str] = []
    session_secret_key: str = ""
    oauth2_yaml_path: str = str(_OAUTH2_YAML)

    ssl_certfile: str = ""
    ssl_keyfile: str = ""

    channel_name: str = "webui"
    channel_state_dir: Path = Path.home() / ".claude" / "channels" / "webui"
    channel_inbox_dir: Path | None = None
    channel_outbox_dir: Path | None = None
    channel_max_file_size: int = 52_428_800

    @model_validator(mode="before")
    @classmethod
    def _load_oauth2_yaml(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Load OAuth2 settings from YAML file, env vars take precedence."""
        yaml_path = Path(values.get("oauth2_yaml_path", str(_OAUTH2_YAML)))
        if not yaml_path.exists():
            return values

        with yaml_path.open() as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            return values

        field_map = {  # nosec B105
            "enabled": "oauth2_enabled",
            "client_id": "oauth2_client_id",
            "client_secret": "oauth2_client_secret",
            "allowed_origins": "oauth2_allowed_origins",
            "allowed_emails": "oauth2_allowed_emails",
            "session_secret_key": "session_secret_key",
            "ssl_certfile": "ssl_certfile",
            "ssl_keyfile": "ssl_keyfile",
        }
        _path_fields = {"ssl_certfile", "ssl_keyfile"}
        for yaml_key, settings_key in field_map.items():
            if yaml_key in data and not values.get(settings_key):
                val = data[yaml_key]
                if settings_key in _path_fields and isinstance(val, str):
                    val = str(Path(val).expanduser())
                values[settings_key] = val

        return values

    @model_validator(mode="after")
    def _validate_oauth2(self) -> Settings:
        """Validate that required OAuth2 fields are set when oauth2_enabled is True."""
        if not self.oauth2_enabled:
            return self
        missing = []
        if not self.oauth2_client_id:
            missing.append("client_id")
        if not self.oauth2_client_secret:
            missing.append("client_secret")
        if not self.oauth2_allowed_origins:
            missing.append("allowed_origins")
        if not self.session_secret_key:
            missing.append("session_secret_key")
        if not self.oauth2_allowed_emails:
            missing.append("allowed_emails")
        if missing:
            yaml_path = self.oauth2_yaml_path
            msg = f"OAuth2 is enabled but required settings are missing: {', '.join(missing)}. Configure them in {yaml_path}"
            raise ValueError(msg)
        return self

    @property
    def resolved_inbox_dir(self) -> Path:
        """Return inbox directory, defaulting to {channel_state_dir}/inbox/."""
        return self.channel_inbox_dir or (self.channel_state_dir / "inbox")

    @property
    def resolved_outbox_dir(self) -> Path:
        """Return outbox directory, defaulting to {channel_state_dir}/outbox/."""
        return self.channel_outbox_dir or (self.channel_state_dir / "outbox")
