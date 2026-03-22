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
