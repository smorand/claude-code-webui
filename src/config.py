"""Application settings using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables.

    Environment variables are prefixed with CCWEBUI_ (e.g., CCWEBUI_APP_NAME).
    A .env file is loaded automatically if present.
    """

    model_config = SettingsConfigDict(
        env_prefix="CCWEBUI_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    app_name: str = "claude-code-webui"
    debug: bool = False
    host: str = "0.0.0.0"  # nosec B104
    port: int = 8080

    upload_dir: str = "./uploads"
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
    database_path: str = "./data/ccwebui.db"
