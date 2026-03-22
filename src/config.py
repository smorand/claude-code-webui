"""Application settings using pydantic-settings."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_CONFIG_DIR = Path.home() / ".config" / "ccwebui"
_DATA_DIR = Path.home() / ".local" / "share" / "ccwebui"


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

    channel_name: str = "webui"
    channel_state_dir: Path = Path.home() / ".claude" / "channels" / "webui"
    channel_inbox_dir: Path | None = None
    channel_outbox_dir: Path | None = None
    channel_max_file_size: int = 52_428_800

    @property
    def resolved_inbox_dir(self) -> Path:
        """Return inbox directory, defaulting to {channel_state_dir}/inbox/."""
        return self.channel_inbox_dir or (self.channel_state_dir / "inbox")

    @property
    def resolved_outbox_dir(self) -> Path:
        """Return outbox directory, defaulting to {channel_state_dir}/outbox/."""
        return self.channel_outbox_dir or (self.channel_state_dir / "outbox")
