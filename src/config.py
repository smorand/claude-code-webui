"""Application settings using pydantic-settings."""

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_CONFIG_DIR = Path.home() / ".config" / "ccwebui"
_DATA_DIR = Path.home() / ".local" / "share" / "ccwebui"
_CACHE_DIR = Path.home() / ".cache" / "ccwebui"


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
    oauth2_redirect_uri: str = ""
    oauth2_allowed_domains: list[str] = []
    session_secret_key: str = ""

    channel_name: str = "webui"
    channel_state_dir: Path = Path.home() / ".claude" / "channels" / "webui"
    channel_inbox_dir: Path | None = None
    channel_outbox_dir: Path | None = None
    channel_max_file_size: int = 52_428_800

    @model_validator(mode="after")
    def _validate_oauth2(self) -> "Settings":
        """Validate that required OAuth2 fields are set when oauth2_enabled is True."""
        if not self.oauth2_enabled:
            return self
        missing = []
        if not self.oauth2_client_id:
            missing.append("CCWEBUI_OAUTH2_CLIENT_ID")
        if not self.oauth2_client_secret:
            missing.append("CCWEBUI_OAUTH2_CLIENT_SECRET")
        if not self.oauth2_redirect_uri:
            missing.append("CCWEBUI_OAUTH2_REDIRECT_URI")
        if not self.session_secret_key:
            missing.append("CCWEBUI_SESSION_SECRET_KEY")
        if missing:
            msg = f"OAuth2 is enabled but required settings are missing: {', '.join(missing)}"
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
