"""Application configuration settings."""

import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support.

    All settings can be overridden via environment variables prefixed with DATACOMPASS_.
    For example, DATACOMPASS_DATA_DIR=/custom/path.
    """

    model_config = SettingsConfigDict(
        env_prefix="DATACOMPASS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Paths
    data_dir: Path = Field(
        default_factory=lambda: Path.home() / ".datacompass",
        description="Directory for Data Compass data and configuration",
    )
    config_file: Path | None = Field(
        default=None,
        description="Path to configuration file (default: {data_dir}/config.yaml)",
    )

    # Database
    database_url: str | None = Field(
        default=None,
        description="Database URL (default: sqlite:///{data_dir}/datacompass.db)",
    )

    # Output
    default_format: Literal["json", "table"] = Field(
        default="json",
        description="Default output format for CLI commands",
    )

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Logging level",
    )

    # Authentication
    auth_mode: Literal["disabled", "local", "oidc", "ldap"] = Field(
        default="disabled",
        description="Authentication mode: disabled, local, oidc, or ldap",
    )
    auth_secret_key: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        description="Secret key for JWT signing (change in production)",
    )
    auth_access_token_expire_minutes: int = Field(
        default=30,
        description="Access token expiration time in minutes",
    )
    auth_refresh_token_expire_days: int = Field(
        default=7,
        description="Refresh token expiration time in days",
    )
    auth_auto_register: bool = Field(
        default=False,
        description="Automatically register users on first login (for OIDC/LDAP)",
    )

    @property
    def resolved_database_url(self) -> str:
        """Get the database URL, with default if not explicitly set."""
        if self.database_url:
            return self.database_url
        return f"sqlite:///{self.data_dir}/datacompass.db"

    @property
    def resolved_config_file(self) -> Path:
        """Get the config file path, with default if not explicitly set."""
        if self.config_file:
            return self.config_file
        return self.data_dir / "config.yaml"

    def ensure_data_dir(self) -> None:
        """Create the data directory if it doesn't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
