"""Application settings.

Pydantic-settings reads from environment variables (with .env fallback).
All access to configuration goes through `get_settings()` which is cached.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: Literal["development", "staging", "production", "test"] = "development"
    app_name: str = "kepler-api"
    app_version: str = "0.1.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "console"] = "console"

    # HTTP
    http_host: str = "0.0.0.0"
    http_port: int = 8000
    http_cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    http_trusted_hosts: list[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1"])

    # Security
    secret_key_base: str = "change-me-in-production-this-is-a-development-only-default-key-32+chars"
    jwt_private_key_path: str = "./secrets/jwt_private.pem"
    jwt_public_key_path: str = "./secrets/jwt_public.pem"
    jwt_issuer: str = "kepler.api"
    jwt_audience_web: str = "kepler.web"
    jwt_audience_cli: str = "kepler.cli"
    jwt_audience_api: str = "kepler.api"
    access_token_ttl_seconds: int = 900  # 15 minutes
    refresh_token_ttl_seconds: int = 2_592_000  # 30 days
    mfa_challenge_ttl_seconds: int = 300  # 5 minutes

    # Rate limiting
    rate_limit_login_per_email: int = 5
    rate_limit_login_window_seconds: int = 900
    rate_limit_login_lockout_seconds: int = 900

    # Database
    database_url: str = "postgresql+asyncpg://kepler:kepler@localhost:5432/kepler"
    database_url_sync: str = "postgresql+psycopg2://kepler:kepler@localhost:5432/kepler"
    database_pool_size: int = 20
    database_max_overflow: int = 10
    database_echo: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_max_connections: int = 20

    # OpenTelemetry
    otel_enabled: bool = False
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "kepler-api"

    @field_validator("http_cors_origins", "http_trusted_hosts", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        """Allow comma-separated env values for list settings."""
        if isinstance(value, str) and not value.startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()


def reset_settings_cache() -> None:
    """Clear the settings cache (used in tests)."""
    get_settings.cache_clear()
